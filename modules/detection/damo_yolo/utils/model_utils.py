#!/usr/bin/env python3
# Copyright (c) Megvii Inc. All rights reserved.
# Copyright (C) Alibaba Group Holding Limited. All rights reserved.

import time
from copy import deepcopy

import torch
import torch.nn as nn

__all__ = [
    'fuse_conv_and_bn',
    'fuse_model',
    'replace_module',
    'make_divisible'
]

def make_divisible(v, divisor=8, min_value=None):
    if min_value is None:
        min_value = divisor
    new_v = max(min_value, int(v + divisor / 2) // divisor * divisor)
    if new_v < 0.9 * v:
        new_v += divisor
    return new_v


def get_latency(model, inp, iters=500, warmup=2):

    start = time.time()
    for i in range(iters):
        out = model(inp)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        if i <= warmup:
            start = time.time()
    latency = (time.time() - start) / (iters - warmup)

    return out, latency


def fuse_conv_and_bn(conv, bn):
    # Fuse convolution and batchnorm layers
    # https://tehnokv.com/posts/fusing-batchnorm-and-conv/
    fusedconv = (nn.Conv2d(
        conv.in_channels,
        conv.out_channels,
        kernel_size=conv.kernel_size,
        stride=conv.stride,
        padding=conv.padding,
        groups=conv.groups,
        bias=True,
    ).requires_grad_(False).to(conv.weight.device))

    # prepare filters
    w_conv = conv.weight.clone().view(conv.out_channels, -1)
    w_bn = torch.diag(bn.weight.div(torch.sqrt(bn.eps + bn.running_var)))
    fusedconv.weight.copy_(torch.mm(w_bn, w_conv).view(fusedconv.weight.shape))

    # prepare spatial bias
    b_conv = (torch.zeros(conv.weight.size(0), device=conv.weight.device)
              if conv.bias is None else conv.bias)
    b_bn = bn.bias - bn.weight.mul(bn.running_mean).div(
        torch.sqrt(bn.running_var + bn.eps))
    fusedconv.bias.copy_(
        torch.mm(w_bn, b_conv.reshape(-1, 1)).reshape(-1) + b_bn)

    return fusedconv


def fuse_model(model):
    from ..base_models.core.ops import ConvBNAct
    from ..base_models.backbones.tinynas_res import ConvKXBN

    for m in model.modules():
        if type(m) is ConvBNAct and hasattr(m, 'bn'):
            m.conv = fuse_conv_and_bn(m.conv, m.bn)  # update conv
            delattr(m, 'bn')  # remove batchnorm
            m.forward = m.fuseforward  # update forward
        elif type(m) is ConvKXBN and hasattr(m, 'bn1'):
            m.conv1 = fuse_conv_and_bn(m.conv1, m.bn1)  # update conv
            delattr(m, 'bn1')  # remove batchnorm
            m.forward = m.fuseforward  # update forward

    return model


def replace_module(module,
                   replaced_module_type,
                   new_module_type,
                   replace_func=None):
    """
    Replace given type in module to a new type. mostly used in deploy.

    Args:
        module (nn.Module): model to apply replace operation.
        replaced_module_type (Type): module type to be replaced.
        new_module_type (Type)
        replace_func (function): python function to describe replace logic.
                                 Defalut value None.

    Returns:
        model (nn.Module): module that already been replaced.
    """
    def default_replace_func(replaced_module_type, new_module_type):
        return new_module_type()

    if replace_func is None:
        replace_func = default_replace_func

    model = module
    if isinstance(module, replaced_module_type):
        model = replace_func(replaced_module_type, new_module_type)
    else:  # recurrsively replace
        for name, child in module.named_children():
            new_child = replace_module(child, replaced_module_type,
                                       new_module_type)
            if new_child is not child:  # child is already replaced
                model.add_module(name, new_child)

    return model
