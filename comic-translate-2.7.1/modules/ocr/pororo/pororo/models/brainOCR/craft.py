"""
This code is adapted from https://github.com/clovaai/CRAFT-pytorch/blob/master/craft.py.
Copyright (c) 2019-present NAVER Corp.
MIT License
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor

from ._modules import Vgg16BN, init_weights


class DoubleConv(nn.Module):

    def __init__(self, in_ch: int, mid_ch: int, out_ch: int) -> None:
        super(DoubleConv, self).__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_ch + mid_ch, mid_ch, kernel_size=1),
            nn.BatchNorm2d(mid_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(mid_ch, out_ch, kernel_size=3, padding=1),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: Tensor):
        x = self.conv(x)
        return x


class CRAFT(nn.Module):

    def __init__(self, pretrained: bool = False, freeze: bool = False) -> None:
        super(CRAFT, self).__init__()

        # Base network
        self.basenet = Vgg16BN(pretrained, freeze)

        # U network
        self.upconv1 = DoubleConv(1024, 512, 256)
        self.upconv2 = DoubleConv(512, 256, 128)
        self.upconv3 = DoubleConv(256, 128, 64)
        self.upconv4 = DoubleConv(128, 64, 32)

        num_class = 2
        self.conv_cls = nn.Sequential(
            nn.Conv2d(32, 32, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 32, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 16, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(16, 16, kernel_size=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(16, num_class, kernel_size=1),
        )

        init_weights(self.upconv1.modules())
        init_weights(self.upconv2.modules())
        init_weights(self.upconv3.modules())
        init_weights(self.upconv4.modules())
        init_weights(self.conv_cls.modules())

    def forward(self, x: Tensor):
        # Base network
        sources = self.basenet(x)

        # U network
        y = torch.cat([sources[0], sources[1]], dim=1)
        y = self.upconv1(y)

        y = F.interpolate(
            y,
            size=sources[2].size()[2:],
            mode="bilinear",
            align_corners=False,
        )
        y = torch.cat([y, sources[2]], dim=1)
        y = self.upconv2(y)

        y = F.interpolate(
            y,
            size=sources[3].size()[2:],
            mode="bilinear",
            align_corners=False,
        )
        y = torch.cat([y, sources[3]], dim=1)
        y = self.upconv3(y)

        y = F.interpolate(
            y,
            size=sources[4].size()[2:],
            mode="bilinear",
            align_corners=False,
        )
        y = torch.cat([y, sources[4]], dim=1)
        feature = self.upconv4(y)

        y = self.conv_cls(feature)

        return y.permute(0, 2, 3, 1), feature
