"""
Self-contained implementation of the LaMa FFCResNetGenerator architecture.

Adapted from https://github.com/advimman/lama (saicinpainting.training.modules.ffc)
with all external dependencies inlined.

This module is used to load non-JIT checkpoints such as ``lama_large_512px.ckpt``
from dreMaz/AnimeMangaInpainting.
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


# ---------------------------------------------------------------------------
# Inlined helpers (originally from saicinpainting.training.modules.base)
# ---------------------------------------------------------------------------

def get_activation(kind: str = "relu", **kwargs) -> nn.Module:
    """Return an activation layer by name."""
    kind_lower = kind.lower()
    if kind_lower == "relu":
        return nn.ReLU(**kwargs)
    if kind_lower == "leakyrelu" or kind_lower == "leaky_relu":
        return nn.LeakyReLU(**kwargs)
    if kind_lower == "tanh":
        return nn.Tanh()
    if kind_lower == "sigmoid":
        return nn.Sigmoid()
    if kind_lower == "elu":
        return nn.ELU(**kwargs)
    if kind_lower == "none" or kind_lower == "identity":
        return nn.Identity()
    raise ValueError(f"Unknown activation kind: {kind}")


# ---------------------------------------------------------------------------
# Squeeze-and-Excitation (inlined from saicinpainting.training.modules.squeeze_excitation)
# ---------------------------------------------------------------------------

class SELayer(nn.Module):
    """Squeeze-and-Excitation block."""

    def __init__(self, channel: int, reduction: int = 16):
        super().__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Sequential(
            nn.Linear(channel, channel // reduction, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(channel // reduction, channel, bias=False),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, c, _, _ = x.size()
        y = self.avg_pool(x).view(b, c)
        y = self.fc(y).view(b, c, 1, 1)
        return x * y.expand_as(x)


# ---------------------------------------------------------------------------
# FFC building blocks
# ---------------------------------------------------------------------------

class FFCSE_block(nn.Module):
    """Squeeze-and-Excitation block adapted for split local/global FFC features."""

    def __init__(self, channels: int, ratio_g: float):
        super().__init__()
        in_cg = int(channels * ratio_g)
        in_cl = channels - in_cg
        r = 16

        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
        self.conv1 = nn.Conv2d(channels, channels // r, kernel_size=1, bias=True)
        self.relu1 = nn.ReLU(inplace=True)
        self.conv_a2l = None if in_cl == 0 else nn.Conv2d(channels // r, in_cl, kernel_size=1, bias=True)
        self.conv_a2g = None if in_cg == 0 else nn.Conv2d(channels // r, in_cg, kernel_size=1, bias=True)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        x = x if isinstance(x, tuple) else (x, 0)
        id_l, id_g = x

        x = id_l if isinstance(id_g, int) else torch.cat([id_l, id_g], dim=1)
        x = self.avgpool(x)
        x = self.relu1(self.conv1(x))

        x_l = 0 if self.conv_a2l is None else id_l * self.sigmoid(self.conv_a2l(x))
        x_g = 0 if self.conv_a2g is None else id_g * self.sigmoid(self.conv_a2g(x))
        return x_l, x_g


class FourierUnit(nn.Module):
    """Core Fourier convolution unit providing image-wide receptive field."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        groups: int = 1,
        spatial_scale_factor=None,
        spatial_scale_mode: str = "bilinear",
        spectral_pos_encoding: bool = False,
        use_se: bool = False,
        se_kwargs: dict | None = None,
        ffc3d: bool = False,
        fft_norm: str = "ortho",
    ):
        super().__init__()
        self.groups = groups

        self.conv_layer = nn.Conv2d(
            in_channels=in_channels * 2 + (2 if spectral_pos_encoding else 0),
            out_channels=out_channels * 2,
            kernel_size=1,
            stride=1,
            padding=0,
            groups=self.groups,
            bias=False,
        )
        self.bn = nn.BatchNorm2d(out_channels * 2)
        self.relu = nn.ReLU(inplace=True)

        self.use_se = use_se
        if use_se:
            if se_kwargs is None:
                se_kwargs = {}
            self.se = SELayer(self.conv_layer.in_channels, **se_kwargs)

        self.spatial_scale_factor = spatial_scale_factor
        self.spatial_scale_mode = spatial_scale_mode
        self.spectral_pos_encoding = spectral_pos_encoding
        self.ffc3d = ffc3d
        self.fft_norm = fft_norm

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch = x.shape[0]

        if self.spatial_scale_factor is not None:
            orig_size = x.shape[-2:]
            x = F.interpolate(
                x,
                scale_factor=self.spatial_scale_factor,
                mode=self.spatial_scale_mode,
                align_corners=False,
            )

        fft_dim = (-3, -2, -1) if self.ffc3d else (-2, -1)
        ffted = torch.fft.rfftn(x, dim=fft_dim, norm=self.fft_norm)
        ffted = torch.stack((ffted.real, ffted.imag), dim=-1)
        ffted = ffted.permute(0, 1, 4, 2, 3).contiguous()  # (batch, c, 2, h, w/2+1)
        ffted = ffted.view((batch, -1) + ffted.size()[3:])

        if self.spectral_pos_encoding:
            height, width = ffted.shape[-2:]
            coords_vert = (
                torch.linspace(0, 1, height)[None, None, :, None]
                .expand(batch, 1, height, width)
                .to(ffted)
            )
            coords_hor = (
                torch.linspace(0, 1, width)[None, None, None, :]
                .expand(batch, 1, height, width)
                .to(ffted)
            )
            ffted = torch.cat((coords_vert, coords_hor, ffted), dim=1)

        if self.use_se:
            ffted = self.se(ffted)

        ffted = self.conv_layer(ffted)  # (batch, c*2, h, w/2+1)
        ffted = self.relu(self.bn(ffted))

        ffted = (
            ffted.view((batch, -1, 2) + ffted.size()[2:])
            .permute(0, 1, 3, 4, 2)
            .contiguous()
        )  # (batch, c, h, w/2+1, 2)
        ffted = torch.complex(ffted[..., 0], ffted[..., 1])

        ifft_shape_slice = x.shape[-3:] if self.ffc3d else x.shape[-2:]
        output = torch.fft.irfftn(ffted, s=ifft_shape_slice, dim=fft_dim, norm=self.fft_norm)

        if self.spatial_scale_factor is not None:
            output = F.interpolate(
                output,
                size=orig_size,
                mode=self.spatial_scale_mode,
                align_corners=False,
            )

        return output


class SpectralTransform(nn.Module):
    """Wraps FourierUnit with pre/post convolutions and optional LFU."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        stride: int = 1,
        groups: int = 1,
        enable_lfu: bool = True,
        **fu_kwargs,
    ):
        super().__init__()
        self.enable_lfu = enable_lfu
        if stride == 2:
            self.downsample = nn.AvgPool2d(kernel_size=(2, 2), stride=2)
        else:
            self.downsample = nn.Identity()

        self.stride = stride
        self.conv1 = nn.Sequential(
            nn.Conv2d(in_channels, out_channels // 2, kernel_size=1, groups=groups, bias=False),
            nn.BatchNorm2d(out_channels // 2),
            nn.ReLU(inplace=True),
        )
        self.fu = FourierUnit(out_channels // 2, out_channels // 2, groups, **fu_kwargs)
        if self.enable_lfu:
            self.lfu = FourierUnit(out_channels // 2, out_channels // 2, groups)
        self.conv2 = nn.Conv2d(
            out_channels // 2, out_channels, kernel_size=1, groups=groups, bias=False
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.downsample(x)
        x = self.conv1(x)
        output = self.fu(x)

        if self.enable_lfu:
            n, c, h, w = x.shape
            split_no = 2
            split_s = h // split_no
            xs = torch.cat(torch.split(x[:, : c // 4], split_s, dim=-2), dim=1).contiguous()
            xs = torch.cat(torch.split(xs, split_s, dim=-1), dim=1).contiguous()
            xs = self.lfu(xs)
            xs = xs.repeat(1, 1, split_no, split_no).contiguous()
        else:
            xs = 0

        output = self.conv2(x + output + xs)
        return output


class FFC(nn.Module):
    """Fast Fourier Convolution combining local and global branches."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        ratio_gin: float,
        ratio_gout: float,
        stride: int = 1,
        padding: int = 0,
        dilation: int = 1,
        groups: int = 1,
        bias: bool = False,
        enable_lfu: bool = True,
        padding_type: str = "reflect",
        gated: bool = False,
        **spectral_kwargs,
    ):
        super().__init__()

        assert stride == 1 or stride == 2, "Stride should be 1 or 2."
        self.stride = stride

        in_cg = int(in_channels * ratio_gin)
        in_cl = in_channels - in_cg
        out_cg = int(out_channels * ratio_gout)
        out_cl = out_channels - out_cg

        self.ratio_gin = ratio_gin
        self.ratio_gout = ratio_gout
        self.global_in_num = in_cg

        module = nn.Identity if in_cl == 0 or out_cl == 0 else nn.Conv2d
        self.convl2l = module(
            in_cl, out_cl, kernel_size, stride, padding, dilation, groups, bias,
            padding_mode=padding_type,
        )
        module = nn.Identity if in_cl == 0 or out_cg == 0 else nn.Conv2d
        self.convl2g = module(
            in_cl, out_cg, kernel_size, stride, padding, dilation, groups, bias,
            padding_mode=padding_type,
        )
        module = nn.Identity if in_cg == 0 or out_cl == 0 else nn.Conv2d
        self.convg2l = module(
            in_cg, out_cl, kernel_size, stride, padding, dilation, groups, bias,
            padding_mode=padding_type,
        )
        module = nn.Identity if in_cg == 0 or out_cg == 0 else SpectralTransform
        self.convg2g = module(
            in_cg, out_cg, stride, 1 if groups == 1 else groups // 2, enable_lfu,
            **spectral_kwargs,
        )

        self.gated = gated
        module = nn.Identity if in_cg == 0 or out_cl == 0 or not self.gated else nn.Conv2d
        self.gate = module(in_channels, 2, 1)

    def forward(self, x):
        x_l, x_g = x if isinstance(x, tuple) else (x, 0)
        out_xl, out_xg = 0, 0

        if self.gated:
            total_input_parts = [x_l]
            if torch.is_tensor(x_g):
                total_input_parts.append(x_g)
            total_input = torch.cat(total_input_parts, dim=1)

            gates = torch.sigmoid(self.gate(total_input))
            g2l_gate, l2g_gate = gates.chunk(2, dim=1)
        else:
            g2l_gate, l2g_gate = 1, 1

        if self.ratio_gout != 1:
            out_xl = self.convl2l(x_l) + self.convg2l(x_g) * g2l_gate
        if self.ratio_gout != 0:
            out_xg = self.convl2g(x_l) * l2g_gate + self.convg2g(x_g)

        return out_xl, out_xg


class FFC_BN_ACT(nn.Module):
    """FFC followed by BatchNorm and activation on both branches."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        ratio_gin: float,
        ratio_gout: float,
        stride: int = 1,
        padding: int = 0,
        dilation: int = 1,
        groups: int = 1,
        bias: bool = False,
        norm_layer=nn.BatchNorm2d,
        activation_layer=nn.Identity,
        padding_type: str = "reflect",
        enable_lfu: bool = True,
        **kwargs,
    ):
        super().__init__()
        self.ffc = FFC(
            in_channels, out_channels, kernel_size,
            ratio_gin, ratio_gout, stride, padding, dilation,
            groups, bias, enable_lfu, padding_type=padding_type, **kwargs,
        )
        lnorm = nn.Identity if ratio_gout == 1 else norm_layer
        gnorm = nn.Identity if ratio_gout == 0 else norm_layer
        global_channels = int(out_channels * ratio_gout)
        self.bn_l = lnorm(out_channels - global_channels)
        self.bn_g = gnorm(global_channels)

        lact = nn.Identity if ratio_gout == 1 else activation_layer
        gact = nn.Identity if ratio_gout == 0 else activation_layer
        self.act_l = lact(inplace=True)
        self.act_g = gact(inplace=True)

    def forward(self, x):
        x_l, x_g = self.ffc(x)
        x_l = self.act_l(self.bn_l(x_l))
        x_g = self.act_g(self.bn_g(x_g))
        return x_l, x_g


class FFCResnetBlock(nn.Module):
    """Residual block using FFC convolutions."""

    def __init__(
        self,
        dim: int,
        padding_type: str,
        norm_layer,
        activation_layer=nn.ReLU,
        dilation: int = 1,
        inline: bool = False,
        **conv_kwargs,
    ):
        super().__init__()
        self.conv1 = FFC_BN_ACT(
            dim, dim, kernel_size=3, padding=dilation, dilation=dilation,
            norm_layer=norm_layer, activation_layer=activation_layer,
            padding_type=padding_type, **conv_kwargs,
        )
        self.conv2 = FFC_BN_ACT(
            dim, dim, kernel_size=3, padding=dilation, dilation=dilation,
            norm_layer=norm_layer, activation_layer=activation_layer,
            padding_type=padding_type, **conv_kwargs,
        )
        self.inline = inline

    def forward(self, x):
        if self.inline:
            x_l, x_g = x[:, : -self.conv1.ffc.global_in_num], x[:, -self.conv1.ffc.global_in_num :]
        else:
            x_l, x_g = x if isinstance(x, tuple) else (x, 0)

        id_l, id_g = x_l, x_g

        x_l, x_g = self.conv1((x_l, x_g))
        x_l, x_g = self.conv2((x_l, x_g))

        x_l, x_g = id_l + x_l, id_g + x_g
        out = x_l, x_g
        if self.inline:
            out = torch.cat(out, dim=1)
        return out


class ConcatTupleLayer(nn.Module):
    """Concatenate the local and global branches of an FFC feature tuple."""

    def forward(self, x):
        assert isinstance(x, tuple)
        x_l, x_g = x
        assert torch.is_tensor(x_l) or torch.is_tensor(x_g)
        if not torch.is_tensor(x_g):
            return x_l
        return torch.cat(x, dim=1)


class FFCResNetGenerator(nn.Module):
    """Full LaMa generator using Fast Fourier Convolution ResNet blocks.

    This is the architecture used in:
      "Resolution-robust Large Mask Inpainting with Fourier Convolutions"
      (Suvorov et al., WACV 2022)

    The ``big-lama`` configuration:
        input_nc=4, output_nc=3, ngf=64, n_downsampling=3, n_blocks=18,
        add_out_act='sigmoid'

    Args:
        input_nc: Number of input channels (typically 4: RGB image + mask).
        output_nc: Number of output channels (typically 3: RGB).
        ngf: Base number of generator filters.
        n_downsampling: Number of downsampling layers in the encoder.
        n_blocks: Number of FFC ResNet blocks in the bottleneck.
        norm_layer: Normalization layer constructor.
        padding_type: Padding type for convolutions.
        activation_layer: Activation layer constructor.
        up_norm_layer: Normalization layer for upsampling path.
        up_activation: Activation module instance for upsampling path.
        init_conv_kwargs: Kwargs for the initial convolution FFC.
        downsample_conv_kwargs: Kwargs for downsampling FFC layers.
        resnet_conv_kwargs: Kwargs for residual FFC blocks.
        add_out_act: Output activation — True for 'tanh', or a string name.
        max_features: Maximum number of feature channels.
        out_ffc: Whether to add an FFC block after upsampling.
        out_ffc_kwargs: Kwargs for the output FFC block.
    """

    def __init__(
        self,
        input_nc: int,
        output_nc: int,
        ngf: int = 64,
        n_downsampling: int = 3,
        n_blocks: int = 9,
        norm_layer=nn.BatchNorm2d,
        padding_type: str = "reflect",
        activation_layer=nn.ReLU,
        up_norm_layer=nn.BatchNorm2d,
        up_activation=nn.ReLU(True),
        init_conv_kwargs: dict | None = None,
        downsample_conv_kwargs: dict | None = None,
        resnet_conv_kwargs: dict | None = None,
        add_out_act=True,
        max_features: int = 1024,
        out_ffc: bool = False,
        out_ffc_kwargs: dict | None = None,
    ):
        assert n_blocks >= 0
        super().__init__()

        if init_conv_kwargs is None:
            init_conv_kwargs = {}
        if downsample_conv_kwargs is None:
            downsample_conv_kwargs = {}
        if resnet_conv_kwargs is None:
            resnet_conv_kwargs = {}
        if out_ffc_kwargs is None:
            out_ffc_kwargs = {}

        model = [
            nn.ReflectionPad2d(3),
            FFC_BN_ACT(
                input_nc, ngf, kernel_size=7, padding=0,
                norm_layer=norm_layer, activation_layer=activation_layer,
                **init_conv_kwargs,
            ),
        ]

        # Downsample
        for i in range(n_downsampling):
            mult = 2 ** i
            if i == n_downsampling - 1:
                cur_conv_kwargs = dict(downsample_conv_kwargs)
                cur_conv_kwargs["ratio_gout"] = resnet_conv_kwargs.get("ratio_gin", 0)
            else:
                cur_conv_kwargs = downsample_conv_kwargs
            model += [
                FFC_BN_ACT(
                    min(max_features, ngf * mult),
                    min(max_features, ngf * mult * 2),
                    kernel_size=3, stride=2, padding=1,
                    norm_layer=norm_layer, activation_layer=activation_layer,
                    **cur_conv_kwargs,
                )
            ]

        mult = 2 ** n_downsampling
        feats_num_bottleneck = min(max_features, ngf * mult)

        # ResNet blocks
        for i in range(n_blocks):
            cur_resblock = FFCResnetBlock(
                feats_num_bottleneck,
                padding_type=padding_type,
                activation_layer=activation_layer,
                norm_layer=norm_layer,
                **resnet_conv_kwargs,
            )
            model += [cur_resblock]

        model += [ConcatTupleLayer()]

        # Upsample
        for i in range(n_downsampling):
            mult = 2 ** (n_downsampling - i)
            model += [
                nn.ConvTranspose2d(
                    min(max_features, ngf * mult),
                    min(max_features, int(ngf * mult / 2)),
                    kernel_size=3, stride=2, padding=1, output_padding=1,
                ),
                up_norm_layer(min(max_features, int(ngf * mult / 2))),
                up_activation,
            ]

        if out_ffc:
            model += [
                FFCResnetBlock(
                    ngf, padding_type=padding_type, activation_layer=activation_layer,
                    norm_layer=norm_layer, inline=True, **out_ffc_kwargs,
                )
            ]

        model += [nn.ReflectionPad2d(3), nn.Conv2d(ngf, output_nc, kernel_size=7, padding=0)]
        if add_out_act:
            model.append(get_activation("tanh" if add_out_act is True else add_out_act))
        self.model = nn.Sequential(*model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.model(x)


# ---------------------------------------------------------------------------
# Factory for the big-lama / lama_large_512px configuration
# ---------------------------------------------------------------------------

def build_lama_large_generator() -> FFCResNetGenerator:
    """Instantiate an ``FFCResNetGenerator`` with the big-lama config
    used by ``lama_large_512px.ckpt`` (dreMaz/AnimeMangaInpainting).

    Config:
        input_nc=4, output_nc=3, ngf=64, n_downsampling=3, n_blocks=18,
        add_out_act='sigmoid',
        init_conv:     ratio_gin=0,    ratio_gout=0,    enable_lfu=False
        downsample:    ratio_gin=0,    ratio_gout=0,    enable_lfu=False
        resnet:        ratio_gin=0.75, ratio_gout=0.75, enable_lfu=False
    """
    return FFCResNetGenerator(
        input_nc=4,
        output_nc=3,
        ngf=64,
        n_downsampling=3,
        n_blocks=18,
        norm_layer=nn.BatchNorm2d,
        padding_type="reflect",
        activation_layer=nn.ReLU,
        up_norm_layer=nn.BatchNorm2d,
        up_activation=nn.ReLU(True),
        init_conv_kwargs={"ratio_gin": 0, "ratio_gout": 0, "enable_lfu": False},
        downsample_conv_kwargs={"ratio_gin": 0, "ratio_gout": 0, "enable_lfu": False},
        resnet_conv_kwargs={"ratio_gin": 0.75, "ratio_gout": 0.75, "enable_lfu": False},
        add_out_act="sigmoid",
        max_features=1024,
        out_ffc=False,
        out_ffc_kwargs={},
    )
