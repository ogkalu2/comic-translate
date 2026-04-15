"""
CUHK MangaInpainting Architecture Components
=============================================

Full architecture implementation ported from:
    https://github.com/msxie92/MangaInpainting

    "Seamless Manga Inpainting with Semantics Awareness"
    Minshan Xie et al., SIGGRAPH 2021

All components are made device-agnostic (removed hardcoded .cuda() calls)
and adapted for integration with the Comic-Translate inpainting pipeline.

Components:
    - Utility functions (patch extraction, padding, reduction)
    - Morphological operations (Dilation2d, Erosion2d)
    - ScreenVAE encoder (ResnetGenerator)
    - SemanticInpaintGenerator (dual-head encoder-decoder)
    - MangaInpaintGenerator (two-branch with ContextualAttention)
"""

from __future__ import annotations

import math
import functools
import numpy as np

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.nn.utils import spectral_norm as spectral_norm_fn
from torch.nn.utils import weight_norm as weight_norm_fn
from torch.nn.modules.normalization import LayerNorm


# =============================================================================
# Utility Functions (from utils/tools.py)
# =============================================================================

def same_padding(images: torch.Tensor, ksizes, strides, rates) -> torch.Tensor:
    """Apply same-padding to a batch of images for patch extraction."""
    assert len(images.size()) == 4
    batch_size, channel, rows, cols = images.size()
    out_rows = (rows + strides[0] - 1) // strides[0]
    out_cols = (cols + strides[1] - 1) // strides[1]
    effective_k_row = (ksizes[0] - 1) * rates[0] + 1
    effective_k_col = (ksizes[1] - 1) * rates[1] + 1
    padding_rows = max(0, (out_rows - 1) * strides[0] + effective_k_row - rows)
    padding_cols = max(0, (out_cols - 1) * strides[1] + effective_k_col - cols)
    padding_top = int(padding_rows / 2.)
    padding_left = int(padding_cols / 2.)
    padding_bottom = padding_rows - padding_top
    padding_right = padding_cols - padding_left
    paddings = (padding_left, padding_right, padding_top, padding_bottom)
    images = torch.nn.ZeroPad2d(paddings)(images)
    return images


def extract_image_patches(images: torch.Tensor, ksizes, strides, rates,
                          padding: str = 'same') -> torch.Tensor:
    """Extract patches from images and flatten into the channel dimension.

    Args:
        images: [B, C, H, W]
        ksizes: [kH, kW]
        strides: [sH, sW]
        rates: [dH, dW]
        padding: 'same' or 'valid'

    Returns:
        Tensor of shape [B, C*kH*kW, L] where L is the number of patches.
    """
    assert len(images.size()) == 4
    assert padding in ['same', 'valid']

    if padding == 'same':
        images = same_padding(images, ksizes, strides, rates)

    unfold = torch.nn.Unfold(
        kernel_size=ksizes, dilation=rates, padding=0, stride=strides
    )
    return unfold(images)


def reduce_mean(x: torch.Tensor, axis=None, keepdim: bool = False) -> torch.Tensor:
    """Reduce mean over specified axes."""
    if not axis:
        axis = range(len(x.shape))
    for i in sorted(axis, reverse=True):
        x = torch.mean(x, dim=i, keepdim=keepdim)
    return x


def reduce_sum(x: torch.Tensor, axis=None, keepdim: bool = False) -> torch.Tensor:
    """Reduce sum over specified axes."""
    if not axis:
        axis = range(len(x.shape))
    for i in sorted(axis, reverse=True):
        x = torch.sum(x, dim=i, keepdim=keepdim)
    return x


# =============================================================================
# Morphological Operations (from src/morphology.py)
# =============================================================================

def _fixed_padding(inputs: torch.Tensor, kernel_size: int, dilation: int = 1) -> torch.Tensor:
    """Apply symmetric padding for morphological operations."""
    kernel_size_effective = kernel_size + (kernel_size - 1) * (dilation - 1)
    pad_total = kernel_size_effective - 1
    pad_beg = pad_total // 2
    pad_end = pad_total - pad_beg
    return F.pad(inputs, (pad_beg, pad_end, pad_beg, pad_end), mode='replicate')


class Morphology(nn.Module):
    """Base class for differentiable morphological operators.

    Supports stride=1, dilation=1, square kernels, and 'same' padding.
    """

    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 5,
                 soft_max: bool = True, beta: float = 15, op_type: str = 'dilation2d'):
        super().__init__()
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.kernel_size = kernel_size
        self.soft_max = soft_max
        self.beta = beta
        self.op_type = op_type
        self.unfold = nn.Unfold(kernel_size, dilation=1, padding=0, stride=1)

    def forward(self, x: torch.Tensor, iterations: int = 1) -> torch.Tensor:
        for _ in range(iterations):
            x = self._one_iter(x)
        return x

    def _one_iter(self, x: torch.Tensor) -> torch.Tensor:
        H, W = x.shape[-2:]
        x = _fixed_padding(x, self.kernel_size, dilation=1)
        x = self.unfold(x)           # (B, Cin*kH*kW, L)
        x = x.unsqueeze(1)           # (B, 1, Cin*kH*kW, L)

        if self.op_type == 'erosion2d':
            x = -1 * x
        elif self.op_type != 'dilation2d':
            raise ValueError(f"Unknown op_type: {self.op_type}")

        if not self.soft_max:
            x, _ = torch.max(x, dim=2, keepdim=False)
        else:
            x = torch.logsumexp(x * self.beta, dim=2, keepdim=False) / self.beta

        if self.op_type == 'erosion2d':
            x = -1 * x

        return x.view(-1, self.out_channels, H, W)


class Dilation2d(Morphology):
    """Differentiable 2D dilation operator."""

    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 5,
                 soft_max: bool = True, beta: float = 20):
        super().__init__(in_channels, out_channels, kernel_size, soft_max, beta, 'dilation2d')


class Erosion2d(Morphology):
    """Differentiable 2D erosion operator."""

    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 5,
                 soft_max: bool = True, beta: float = 20):
        super().__init__(in_channels, out_channels, kernel_size, soft_max, beta, 'erosion2d')


# =============================================================================
# Layer Helpers (from src/networks.py)
# =============================================================================

class LayerNormWrapper(nn.Module):
    """Device-agnostic LayerNorm wrapper.

    Original CUHK code hardcodes .cuda() — this version uses F.layer_norm
    which is inherently device-agnostic.
    """

    def __init__(self, num_features: int):
        super().__init__()
        self.num_features = int(num_features)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        shape = [self.num_features, x.size(2), x.size(3)]
        return F.layer_norm(x, shape)


def _spectral_norm(module: nn.Module, mode: bool = True) -> nn.Module:
    """Conditionally apply spectral normalization."""
    if mode:
        return nn.utils.spectral_norm(module)
    return module


# =============================================================================
# Conv2dBlock & ResnetBlock (from src/networks.py — CUHK variant)
# =============================================================================

class Conv2dBlock(nn.Module):
    """Convolutional block with configurable padding, normalization, and activation.

    Used by MangaInpaintGenerator for gen_conv / gen_deconv operations.
    """

    def __init__(self, input_dim: int, output_dim: int, kernel_size: int,
                 stride: int, padding: int = 0, conv_padding: int = 0,
                 dilation: int = 1, weight_norm: str = 'none', norm: str = 'none',
                 activation: str = 'relu', pad_type: str = 'replicate',
                 transpose: bool = False):
        super().__init__()
        self.use_bias = True

        # External padding module
        if pad_type == 'reflect':
            self.pad = nn.ReflectionPad2d(padding) if padding > 0 else None
        elif pad_type == 'replicate':
            self.pad = nn.ReplicationPad2d(padding) if padding > 0 else None
        elif pad_type == 'zero':
            self.pad = nn.ZeroPad2d(padding) if padding > 0 else None
        elif pad_type == 'none':
            self.pad = None
        else:
            raise ValueError(f"Unsupported padding type: {pad_type}")

        # Normalization
        if norm == 'bn':
            self.norm = nn.BatchNorm2d(output_dim)
        elif norm == 'in':
            self.norm = nn.InstanceNorm2d(output_dim)
        elif norm == 'ln':
            self.norm = LayerNormWrapper(output_dim)
        elif norm == 'none':
            self.norm = None
        else:
            raise ValueError(f"Unsupported normalization: {norm}")

        # Weight normalization
        if weight_norm == 'sn':
            self.weight_norm_fn = spectral_norm_fn
        elif weight_norm == 'wn':
            self.weight_norm_fn = weight_norm_fn
        elif weight_norm == 'none':
            self.weight_norm_fn = None
        else:
            raise ValueError(f"Unsupported weight norm: {weight_norm}")

        # Activation
        if activation == 'relu':
            self.activation = nn.ReLU(inplace=True)
        elif activation == 'elu':
            self.activation = nn.ELU(inplace=True)
        elif activation == 'lrelu':
            self.activation = nn.LeakyReLU(0.2, inplace=True)
        elif activation == 'prelu':
            self.activation = nn.PReLU()
        elif activation == 'selu':
            self.activation = nn.SELU(inplace=True)
        elif activation == 'tanh':
            self.activation = nn.Tanh()
        elif activation == 'none':
            self.activation = None
        else:
            raise ValueError(f"Unsupported activation: {activation}")

        # Convolution
        if transpose:
            self.conv = nn.ConvTranspose2d(
                input_dim, output_dim, kernel_size, stride,
                padding=conv_padding, output_padding=conv_padding,
                dilation=dilation, bias=self.use_bias
            )
        else:
            self.conv = nn.Conv2d(
                input_dim, output_dim, kernel_size, stride,
                padding=conv_padding, dilation=dilation, bias=self.use_bias
            )

        if self.weight_norm_fn:
            self.conv = self.weight_norm_fn(self.conv)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.pad:
            x = self.conv(self.pad(x))
        else:
            x = self.conv(x)
        if self.norm:
            x = self.norm(x)
        if self.activation:
            x = self.activation(x)
        return x


class CUHKResnetBlock(nn.Module):
    """Residual block used by SemanticInpaintGenerator.

    Distinct from the ScreenVAE ResnetBlock — uses spectral norm and
    LayerNormWrapper instead of configurable norm layers.
    """

    def __init__(self, dim: int, dilation: int = 1,
                 use_spectral_norm: bool = False, use_instance: bool = False):
        super().__init__()
        if use_instance:
            self.conv_block = nn.Sequential(
                nn.ReflectionPad2d(dilation),
                _spectral_norm(nn.Conv2d(
                    dim, dim, kernel_size=3, padding=0,
                    dilation=dilation, bias=not use_spectral_norm
                ), use_spectral_norm),
                LayerNormWrapper(dim),
                nn.ReLU(True),
                nn.ReflectionPad2d(1),
                _spectral_norm(nn.Conv2d(
                    dim, dim, kernel_size=3, padding=0,
                    dilation=1, bias=not use_spectral_norm
                ), use_spectral_norm),
                LayerNormWrapper(dim),
            )
        else:
            self.conv_block = nn.Sequential(
                nn.ReflectionPad2d(dilation),
                _spectral_norm(nn.Conv2d(
                    dim, dim, kernel_size=3, padding=0,
                    dilation=dilation, bias=not use_spectral_norm
                ), use_spectral_norm),
                nn.ReLU(True),
                nn.ReflectionPad2d(1),
                _spectral_norm(nn.Conv2d(
                    dim, dim, kernel_size=3, padding=0,
                    dilation=1, bias=not use_spectral_norm
                ), use_spectral_norm),
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.conv_block(x)


def gen_conv(input_dim: int, output_dim: int, kernel_size: int = 3,
             stride: int = 1, padding: int = 0, rate: int = 1,
             activation: str = 'elu') -> Conv2dBlock:
    """Create a standard convolutional block for MangaInpaintGenerator."""
    return Conv2dBlock(
        input_dim, output_dim, kernel_size, stride,
        padding=padding, dilation=rate, activation=activation
    )


def gen_deconv(input_dim: int, output_dim: int, kernel_size: int = 3,
               stride: int = 1, padding: int = 0, rate: int = 1,
               activation: str = 'elu') -> Conv2dBlock:
    """Create a transposed convolutional block for MangaInpaintGenerator."""
    return Conv2dBlock(
        input_dim, output_dim, kernel_size, stride,
        conv_padding=padding, dilation=rate,
        activation=activation, transpose=True
    )


# =============================================================================
# Contextual Attention (from src/networks.py)
# =============================================================================

class ContextualAttention(nn.Module):
    """Patch-based contextual attention for texture borrowing.

    From: "Generative Image Inpainting with Contextual Attention", Yu et al.
    Adapted for device-agnostic operation.
    """

    def __init__(self, ksize: int = 3, stride: int = 1, rate: int = 1,
                 fuse_k: int = 3, softmax_scale: float = 10, fuse: bool = False):
        super().__init__()
        self.ksize = ksize
        self.stride = stride
        self.rate = rate
        self.fuse_k = fuse_k
        self.softmax_scale = softmax_scale
        self.fuse = fuse

    def forward(self, f: torch.Tensor, b: torch.Tensor,
                mask: torch.Tensor | None = None) -> tuple[torch.Tensor, torch.Tensor]:
        """Contextual attention forward pass.

        Args:
            f: Foreground features [B, C, H, W]
            b: Background features [B, C, H, W]
            mask: Binary mask [B, 1, H_orig, W_orig]

        Returns:
            (attended_features, offsets)
        """
        raw_int_fs = list(f.size())
        raw_int_bs = list(b.size())

        # Extract patches from background at original scale (for reconstruction)
        kernel = 2 * self.rate
        raw_w = extract_image_patches(
            b, ksizes=[kernel, kernel],
            strides=[self.rate * self.stride, self.rate * self.stride],
            rates=[1, 1], padding='same'
        )
        raw_w = raw_w.view(raw_int_bs[0], raw_int_bs[1], kernel, kernel, -1)
        raw_w = raw_w.permute(0, 4, 1, 2, 3)
        raw_w_groups = torch.split(raw_w, 1, dim=0)

        # Downscale foreground and background for matching
        f = F.interpolate(f, scale_factor=1. / self.rate, mode='nearest')
        b = F.interpolate(b, scale_factor=1. / self.rate, mode='nearest')
        int_fs = list(f.size())
        int_bs = list(b.size())
        f_groups = torch.split(f, 1, dim=0)

        # Extract patches from downscaled background (for matching)
        w = extract_image_patches(
            b, ksizes=[self.ksize, self.ksize],
            strides=[self.stride, self.stride],
            rates=[1, 1], padding='same'
        )
        w = w.view(int_bs[0], int_bs[1], self.ksize, self.ksize, -1)
        w = w.permute(0, 4, 1, 2, 3)
        w_groups = torch.split(w, 1, dim=0)

        # Process mask
        if mask is None:
            mask = torch.zeros([int_bs[0], 1, int_bs[2], int_bs[3]], device=f.device)
        else:
            mask = F.interpolate(mask, scale_factor=1. / (4 * self.rate), mode='nearest')

        int_ms = list(mask.size())
        m = extract_image_patches(
            mask, ksizes=[self.ksize, self.ksize],
            strides=[self.stride, self.stride],
            rates=[1, 1], padding='same'
        )
        m = m.view(int_ms[0], int_ms[1], self.ksize, self.ksize, -1)
        m = m.permute(0, 4, 1, 2, 3)
        m = m[0]
        mm = (reduce_mean(m, axis=[1, 2, 3], keepdim=True) == 0.).to(torch.float32)
        mm = mm.permute(1, 0, 2, 3)

        y = []
        offsets = []
        k = self.fuse_k
        scale = self.softmax_scale
        fuse_weight = torch.eye(k, device=f.device).view(1, 1, k, k)

        for xi, wi, raw_wi in zip(f_groups, w_groups, raw_w_groups):
            escape_NaN = torch.FloatTensor([1e-4]).to(f.device)
            wi = wi[0]
            max_wi = torch.sqrt(
                reduce_sum(torch.pow(wi, 2) + escape_NaN, axis=[1, 2, 3], keepdim=True)
            )
            wi_normed = wi / max_wi

            xi = same_padding(xi, [self.ksize, self.ksize], [1, 1], [1, 1])
            yi = F.conv2d(xi, wi_normed, stride=1)

            if self.fuse:
                yi = yi.view(1, 1, int_bs[2] * int_bs[3], int_fs[2] * int_fs[3])
                yi = same_padding(yi, [k, k], [1, 1], [1, 1])
                yi = F.conv2d(yi, fuse_weight, stride=1)
                yi = yi.contiguous().view(1, int_bs[2], int_bs[3], int_fs[2], int_fs[3])
                yi = yi.permute(0, 2, 1, 4, 3)
                yi = yi.contiguous().view(1, 1, int_bs[2] * int_bs[3], int_fs[2] * int_fs[3])
                yi = same_padding(yi, [k, k], [1, 1], [1, 1])
                yi = F.conv2d(yi, fuse_weight, stride=1)
                yi = yi.contiguous().view(1, int_bs[3], int_bs[2], int_fs[3], int_fs[2])
                yi = yi.permute(0, 2, 1, 4, 3).contiguous()

            yi = yi.view(1, int_bs[2] * int_bs[3], int_fs[2], int_fs[3])

            # Softmax matching with mask exclusion
            yi = yi * mm
            yi = F.softmax(yi * scale, dim=1)
            yi = yi * mm

            offset = torch.argmax(yi, dim=1, keepdim=True)
            if int_bs != int_fs:
                times = float(int_fs[2] * int_fs[3]) / float(int_bs[2] * int_bs[3])
                offset = ((offset + 1).float() * times - 1).to(torch.int64)
            offset = torch.cat([offset // int_fs[3], offset % int_fs[3]], dim=1)

            # Reconstruct using original-scale patches
            wi_center = raw_wi[0]
            yi = F.conv_transpose2d(yi, wi_center, stride=self.rate, padding=1) / 4.
            y.append(yi)
            offsets.append(offset)

        y = torch.cat(y, dim=0)
        y.contiguous().view(raw_int_fs)

        offsets = torch.cat(offsets, dim=0)
        offsets = offsets.view(int_fs[0], 2, *int_fs[2:])

        return y, offsets


# =============================================================================
# SemanticInpaintGenerator (from src/networks.py)
# =============================================================================

class BaseNetwork(nn.Module):
    """Base class with weight initialization for CUHK networks."""

    def __init__(self):
        super().__init__()

    def init_weights(self, init_type: str = 'normal', gain: float = 0.02):
        def init_func(m):
            classname = m.__class__.__name__
            if hasattr(m, 'weight') and (classname.find('Conv') != -1 or classname.find('Linear') != -1):
                if init_type == 'normal':
                    nn.init.normal_(m.weight.data, 0.0, gain)
                elif init_type == 'xavier':
                    nn.init.xavier_normal_(m.weight.data, gain=gain)
                elif init_type == 'kaiming':
                    nn.init.kaiming_normal_(m.weight.data, a=0, mode='fan_in')
                elif init_type == 'orthogonal':
                    nn.init.orthogonal_(m.weight.data, gain=gain)
                if hasattr(m, 'bias') and m.bias is not None:
                    nn.init.constant_(m.bias.data, 0.0)
            elif classname.find('BatchNorm2d') != -1:
                nn.init.normal_(m.weight.data, 1.0, gain)
                nn.init.constant_(m.bias.data, 0.0)

        self.apply(init_func)


class SemanticInpaintGenerator(BaseNetwork):
    """Dual-head encoder-decoder for structural line and screentone inpainting.

    Input: 7 channels (screen_masked[4] + lines_masked[1] + mask[1] + noise[1])
    Output: (screentone_map[4], structural_lines[1])

    Architecture: Encoder (4 stages) → ResNet middle → Two parallel decoders
      - Screentone decoder (bilinear upsampling)
      - Line decoder (transposed convolutions with skip connections)
    """

    def __init__(self, in_channels: int = 3, out_channels: int = 4,
                 residual_blocks: int = 6, init_weights: bool = True):
        super().__init__()

        self.encoder1 = nn.Sequential(
            nn.ReflectionPad2d(3),
            _spectral_norm(nn.Conv2d(in_channels, 64, kernel_size=7, padding=0)),
            LayerNormWrapper(64),
            nn.ReLU(True)
        )
        self.encoder2 = nn.Sequential(
            _spectral_norm(nn.Conv2d(64, 128, kernel_size=4, stride=2, padding=1)),
            LayerNormWrapper(128),
            nn.ReLU(True)
        )
        self.encoder3 = nn.Sequential(
            _spectral_norm(nn.Conv2d(128, 256, kernel_size=4, stride=2, padding=1)),
            LayerNormWrapper(256),
            nn.ReLU(True)
        )
        self.encoder4 = nn.Sequential(
            _spectral_norm(nn.Conv2d(256, 256, kernel_size=4, stride=2, padding=1)),
            LayerNormWrapper(256),
            nn.ReLU(True)
        )

        blocks = []
        for _ in range(residual_blocks):
            blocks.append(CUHKResnetBlock(256, 2, use_instance=True))
        self.middle = nn.Sequential(*blocks)

        # Screentone decoder (bilinear upsampling path)
        self.decoder_scr4 = nn.Sequential(
            nn.UpsamplingBilinear2d(scale_factor=2),
            _spectral_norm(nn.Conv2d(256, 256, kernel_size=3, stride=1, padding=1)),
            nn.ReLU(True)
        )
        self.decoder_scr3 = nn.Sequential(
            nn.UpsamplingBilinear2d(scale_factor=2),
            _spectral_norm(nn.Conv2d(256, 128, kernel_size=3, stride=1, padding=1)),
            nn.ReLU(True)
        )
        self.decoder_scr2 = nn.Sequential(
            nn.UpsamplingBilinear2d(scale_factor=2),
            _spectral_norm(nn.Conv2d(128, 64, kernel_size=3, stride=1, padding=1)),
            nn.ReLU(True)
        )
        self.decoder_scr1 = nn.Sequential(
            nn.ReflectionPad2d(3),
            nn.Conv2d(64, out_channels, kernel_size=7, padding=0),
        )

        # Line decoder (transposed convolution with skip connections)
        self.decoder_l4 = nn.Sequential(
            _spectral_norm(nn.ConvTranspose2d(256, 256, kernel_size=4, stride=2, padding=1)),
            LayerNormWrapper(256),
            nn.ReLU(True)
        )
        self.decoder_l3 = nn.Sequential(
            _spectral_norm(nn.ConvTranspose2d(256, 128, kernel_size=4, stride=2, padding=1)),
            LayerNormWrapper(128),
            nn.ReLU(True)
        )
        self.decoder_l2 = nn.Sequential(
            _spectral_norm(nn.ConvTranspose2d(128, 64, kernel_size=4, stride=2, padding=1)),
            LayerNormWrapper(64),
            nn.ReLU(True)
        )
        self.decoder_l1 = nn.Sequential(
            nn.ReflectionPad2d(3),
            nn.Conv2d(64, 1, kernel_size=7, padding=0),
        )

        if init_weights:
            self.init_weights()

    def forward(self, xin: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Forward pass.

        Args:
            xin: [B, in_channels, H, W]

        Returns:
            (screentone_map [B, 4, H, W], structural_lines [B, 1, H, W])
        """
        x1 = self.encoder1(xin)
        x2 = self.encoder2(x1)
        x3 = self.encoder3(x2)
        x4 = self.encoder4(x3)
        x = self.middle(x4)

        # Screentone decoder
        scr = self.decoder_scr4(x)
        scr = self.decoder_scr3(scr)
        scr = self.decoder_scr2(scr)
        scr = self.decoder_scr1(scr)
        scr = torch.clamp(scr, -1., 1.)

        # Line decoder with skip connections
        line = self.decoder_l4(x + x4)
        line = self.decoder_l3(line + x3)
        line = self.decoder_l2(line + x2)
        line = self.decoder_l1(line + x1)
        line = torch.clamp(line, -1., 1.)

        return scr, line


# =============================================================================
# MangaInpaintGenerator (from src/networks.py)
# =============================================================================

class MangaInpaintGenerator(BaseNetwork):
    """Two-branch appearance synthesis generator with contextual attention.

    Branch 1: Dilated convolutions (hallucination)
    Branch 2: Contextual attention (texture borrowing)
    Merged via concatenation + decoder

    Input: (masked_image[1] + hints[5] + ones[1] + mask[1]) = 8 channels
    Output: grayscale inpainted region [1 channel]
    """

    def __init__(self, input_dim: int = 6, cnum: int = 32, output_dim: int = 1,
                 init_weights: bool = True):
        super().__init__()

        # Dilated convolution branch
        self.conv1 = gen_conv(input_dim + 2, cnum, 5, 1, 2)
        self.conv2_downsample = gen_conv(cnum, cnum, 3, 2, 1)
        self.conv3 = gen_conv(cnum, cnum * 2, 3, 1, 1)
        self.conv4_downsample = gen_conv(cnum * 2, cnum * 2, 3, 2, 1)
        self.conv5 = gen_conv(cnum * 2, cnum * 4, 3, 1, 1)
        self.conv6_downsample = gen_conv(cnum * 4, cnum * 4, 3, 1, 1)

        self.conv7_atrous = gen_conv(cnum * 4, cnum * 4, 3, 1, 2, rate=2)
        self.conv8_atrous = gen_conv(cnum * 4, cnum * 4, 3, 1, 4, rate=4)
        self.conv9_atrous = gen_conv(cnum * 4, cnum * 4, 3, 1, 8, rate=8)
        self.conv10_atrous = gen_conv(cnum * 4, cnum * 4, 3, 1, 16, rate=16)

        # Contextual attention branch
        self.pmconv1 = gen_conv(input_dim + 2, cnum, 5, 1, 2)
        self.pmconv2_downsample = gen_conv(cnum, cnum, 3, 2, 1)
        self.pmconv3 = gen_conv(cnum, cnum * 2, 3, 1, 1)
        self.pmconv4_downsample = gen_conv(cnum * 2, cnum * 4, 3, 2, 1)
        self.pmconv5 = gen_conv(cnum * 4, cnum * 4, 3, 1, 1)
        self.pmconv6 = gen_conv(cnum * 4, cnum * 4, 3, 1, 1, activation='relu')
        self.contextul_attention = ContextualAttention(
            ksize=3, stride=1, rate=2, fuse_k=3, softmax_scale=10, fuse=True
        )
        self.pmconv9 = gen_conv(cnum * 4, cnum * 4, 3, 1, 1)
        self.pmconv10 = gen_conv(cnum * 4, cnum * 4, 3, 1, 1)

        # Merge + decoder
        self.allconv11 = gen_conv(cnum * 8, cnum * 4, 3, 1, 1)
        self.allconv12 = gen_conv(cnum * 4, cnum * 4, 3, 1, 1)
        self.allconv13 = gen_deconv(cnum * 4, cnum * 2, 3, 2, 1)
        self.allconv14 = gen_conv(cnum * 2, cnum * 2, 3, 1, 1)
        self.allconv15 = gen_deconv(cnum * 2, cnum, 3, 2, 1)
        self.allconv16 = gen_conv(cnum, cnum // 2, 3, 1, 1)
        self.allconv17 = gen_conv(cnum // 2, output_dim, 5, 1, 2, activation='none')

        if init_weights:
            self.init_weights()

    def forward(self, xin: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            xin: [B, input_dim, H, W] (masked_image + hints)
            mask: [B, 1, H, W]

        Returns:
            [B, 1, H, W] inpainted grayscale output
        """
        ones = torch.ones_like(mask)
        xnow = torch.cat([xin, ones, mask], dim=1)

        # Dilated conv branch
        x = self.conv1(xnow)
        x = self.conv2_downsample(x)
        x = self.conv3(x)
        x = self.conv4_downsample(x)
        x = self.conv5(x)
        x = self.conv6_downsample(x)
        x = self.conv7_atrous(x)
        x = self.conv8_atrous(x)
        x = self.conv9_atrous(x)
        x = self.conv10_atrous(x)
        x_hallu = x

        # Contextual attention branch
        x = self.pmconv1(xnow)
        x = self.pmconv2_downsample(x)
        x = self.pmconv3(x)
        x = self.pmconv4_downsample(x)
        x = self.pmconv5(x)
        x = self.pmconv6(x)
        x, _offset_flow = self.contextul_attention(x, x, mask)
        x = self.pmconv9(x)
        x = self.pmconv10(x)

        # Merge branches
        x = torch.cat([x_hallu, x], dim=1)
        x = self.allconv11(x)
        x = self.allconv12(x)
        x = self.allconv13(x)
        x = self.allconv14(x)
        x = self.allconv15(x)
        x = self.allconv16(x)
        x = self.allconv17(x)

        return torch.clamp(x, -1., 1.)


# =============================================================================
# ScreenVAE Encoder Architecture (from src/svae.py)
# =============================================================================

class SVAELayerNormWrapper(nn.Module):
    """Device-agnostic LayerNorm for ScreenVAE components.

    The original ScreenVAE uses a separate LayerNormWarpper (with typo)
    that also hardcodes .cuda(). Fixed here.
    """

    def __init__(self, num_features: int):
        super().__init__()
        self.num_features = int(num_features)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        shape = [self.num_features, x.size(2), x.size(3)]
        return F.layer_norm(x, shape)


def _get_svae_norm_layer(norm_type: str = 'instance'):
    """Return a normalization layer factory for ScreenVAE components."""
    if norm_type == 'batch':
        return functools.partial(nn.BatchNorm2d, affine=True, track_running_stats=True)
    elif norm_type == 'instance':
        return functools.partial(nn.InstanceNorm2d, affine=False, track_running_stats=False)
    elif norm_type == 'layer':
        return functools.partial(SVAELayerNormWrapper)
    elif norm_type == 'none':
        return None
    else:
        raise NotImplementedError(f'normalization layer [{norm_type}] is not found')


def _get_non_linearity(layer_type: str = 'relu'):
    """Return an activation layer factory."""
    if layer_type == 'relu':
        return functools.partial(nn.ReLU, inplace=True)
    elif layer_type == 'lrelu':
        return functools.partial(nn.LeakyReLU, negative_slope=0.2, inplace=True)
    elif layer_type == 'elu':
        return functools.partial(nn.ELU, inplace=True)
    elif layer_type == 'selu':
        return functools.partial(nn.SELU, inplace=True)
    elif layer_type == 'prelu':
        return functools.partial(nn.PReLU)
    else:
        raise NotImplementedError(f'nonlinearity [{layer_type}] is not found')


class SVAEResnetBlock(nn.Module):
    """Residual block for ScreenVAE's ResnetGenerator encoder."""

    def __init__(self, dim: int, padding_type: str, norm_layer, use_dropout: bool, use_bias: bool):
        super().__init__()
        self.conv_block = self._build(dim, padding_type, norm_layer, use_dropout, use_bias)

    def _build(self, dim, padding_type, norm_layer, use_dropout, use_bias):
        conv_block = []
        p = 0
        if padding_type == 'reflect':
            conv_block += [nn.ReflectionPad2d(1)]
        elif padding_type == 'replicate':
            conv_block += [nn.ReplicationPad2d(1)]
        elif padding_type == 'zero':
            p = 1
        else:
            raise NotImplementedError(f'padding [{padding_type}] is not implemented')

        conv_block += [nn.Conv2d(dim, dim, kernel_size=3, padding=p, bias=use_bias)]
        if norm_layer is not None:
            conv_block += [norm_layer(dim)]
        conv_block += [nn.ReLU(True)]

        p = 0
        if padding_type == 'reflect':
            conv_block += [nn.ReflectionPad2d(1)]
        elif padding_type == 'replicate':
            conv_block += [nn.ReplicationPad2d(1)]
        elif padding_type == 'zero':
            p = 1

        conv_block += [nn.Conv2d(dim, dim, kernel_size=3, padding=p, bias=use_bias)]
        if norm_layer is not None:
            conv_block += [norm_layer(dim)]

        return nn.Sequential(*conv_block)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.conv_block(x)


class ScreenVAEEncoder(nn.Module):
    """ResNet-6blocks encoder for ScreenVAE.

    Encodes (grayscale_manga[1] + structural_lines[1]) → screentone_representation[8]
    where output is split into (mean[4], logvar[4]).

    Architecture: ReflPad → Conv7x7 → 3x Conv↓ → 6x ResBlock → 3x Upsample → Conv7x7
    """

    def __init__(self, input_nc: int = 2, output_nc: int = 8, ngf: int = 24,
                 norm_type: str = 'layer', n_downsampling: int = 3, n_blocks: int = 6,
                 padding_type: str = 'replicate'):
        super().__init__()

        norm_layer = _get_svae_norm_layer(norm_type)
        use_bias = True
        if norm_layer is not None:
            if type(norm_layer) == functools.partial:
                use_bias = norm_layer.func != nn.BatchNorm2d
            else:
                use_bias = norm_layer != nn.BatchNorm2d

        # Initial conv
        model = [
            nn.ReplicationPad2d(3),
            nn.Conv2d(input_nc, ngf, kernel_size=7, padding=0, bias=use_bias)
        ]
        if norm_layer is not None:
            model += [norm_layer(ngf)]
        model += [nn.ReLU(True)]

        # Downsampling
        for i in range(n_downsampling):
            mult = 2 ** i
            model += [
                nn.ReplicationPad2d(1),
                nn.Conv2d(ngf * mult, ngf * mult * 2, kernel_size=3,
                          stride=2, padding=0, bias=use_bias)
            ]
            if norm_layer is not None:
                model += [norm_layer(ngf * mult * 2)]
            model += [nn.ReLU(True)]

        # Residual blocks
        mult = 2 ** n_downsampling
        for _ in range(n_blocks):
            model += [SVAEResnetBlock(
                ngf * mult, padding_type=padding_type,
                norm_layer=norm_layer, use_dropout=True, use_bias=use_bias
            )]

        # Upsampling
        for i in range(n_downsampling):
            mult = 2 ** (n_downsampling - i)
            # Bilinear upsample + conv
            model += [
                nn.Upsample(scale_factor=2, mode='bilinear', align_corners=True),
                nn.Conv2d(ngf * mult, int(ngf * mult / 2), kernel_size=1, stride=1, padding=0)
            ]
            if norm_layer is not None:
                model += [norm_layer(int(ngf * mult / 2))]
            model += [nn.ReLU(True)]
            model += [
                nn.ReplicationPad2d(1),
                nn.Conv2d(int(ngf * mult / 2), int(ngf * mult / 2), kernel_size=3, padding=0)
            ]
            if norm_layer is not None:
                model += [norm_layer(ngf * mult / 2)]
            model += [nn.ReLU(True)]

        # Final output conv
        model += [nn.ReplicationPad2d(3)]
        model += [nn.Conv2d(ngf, output_nc, kernel_size=7, padding=0)]

        self.model = nn.Sequential(*model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.model(x)


# =============================================================================
# Builder Functions
# =============================================================================

def build_screenvae_encoder(device: str | torch.device = 'cpu') -> ScreenVAEEncoder:
    """Build the ScreenVAE encoder network.

    Input: 2ch (grayscale + lines) → Output: 8ch (4ch screentone mean + 4ch logvar)
    """
    encoder = ScreenVAEEncoder(
        input_nc=2, output_nc=8, ngf=24,
        norm_type='layer', n_downsampling=3, n_blocks=6,
        padding_type='replicate'
    )
    encoder.to(device)
    encoder.eval()
    return encoder


def build_semantic_generator(device: str | torch.device = 'cpu') -> SemanticInpaintGenerator:
    """Build the SemanticInpaintGenerator.

    Input: 7ch (screen_masked[4] + lines_masked[1] + mask[1] + noise[1])
    Output: (screentone[4], lines[1])
    """
    gen = SemanticInpaintGenerator(in_channels=7, init_weights=False)
    gen.to(device)
    gen.eval()
    return gen


def build_manga_generator(device: str | torch.device = 'cpu') -> MangaInpaintGenerator:
    """Build the MangaInpaintGenerator.

    Input: 6ch (masked_image[1] + hints[5]) + 2ch (ones + mask) appended in forward
    Output: 1ch grayscale
    """
    gen = MangaInpaintGenerator(input_dim=6, cnum=32, init_weights=False)
    gen.to(device)
    gen.eval()
    return gen
