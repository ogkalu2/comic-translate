from collections import namedtuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.nn.init as init
from torchvision import models

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def init_weights(modules):
    for m in modules:
        if isinstance(m, nn.Conv2d):
            init.xavier_uniform_(m.weight.data)
            if m.bias is not None:
                m.bias.data.zero_()
        elif isinstance(m, nn.BatchNorm2d):
            m.weight.data.fill_(1)
            m.bias.data.zero_()
        elif isinstance(m, nn.Linear):
            m.weight.data.normal_(0, 0.01)
            m.bias.data.zero_()


class Vgg16BN(torch.nn.Module):

    def __init__(self, pretrained: bool = True, freeze: bool = True):
        super(Vgg16BN, self).__init__()
        vgg_pretrained_features = models.vgg16_bn(
            pretrained=pretrained).features
        self.slice1 = torch.nn.Sequential()
        self.slice2 = torch.nn.Sequential()
        self.slice3 = torch.nn.Sequential()
        self.slice4 = torch.nn.Sequential()
        self.slice5 = torch.nn.Sequential()
        for x in range(12):  # conv2_2
            self.slice1.add_module(str(x), vgg_pretrained_features[x])
        for x in range(12, 19):  # conv3_3
            self.slice2.add_module(str(x), vgg_pretrained_features[x])
        for x in range(19, 29):  # conv4_3
            self.slice3.add_module(str(x), vgg_pretrained_features[x])
        for x in range(29, 39):  # conv5_3
            self.slice4.add_module(str(x), vgg_pretrained_features[x])

        # fc6, fc7 without atrous conv
        self.slice5 = torch.nn.Sequential(
            nn.MaxPool2d(kernel_size=3, stride=1, padding=1),
            nn.Conv2d(512, 1024, kernel_size=3, padding=6, dilation=6),
            nn.Conv2d(1024, 1024, kernel_size=1),
        )

        if not pretrained:
            init_weights(self.slice1.modules())
            init_weights(self.slice2.modules())
            init_weights(self.slice3.modules())
            init_weights(self.slice4.modules())

        init_weights(
            self.slice5.modules())  # no pretrained model for fc6 and fc7

        if freeze:
            for param in self.slice1.parameters():  # only first conv
                param.requires_grad = False

    def forward(self, x):
        h = self.slice1(x)
        h_relu2_2 = h
        h = self.slice2(h)
        h_relu3_2 = h
        h = self.slice3(h)
        h_relu4_3 = h
        h = self.slice4(h)
        h_relu5_3 = h
        h = self.slice5(h)
        h_fc7 = h
        vgg_outputs = namedtuple(
            "VggOutputs", ["fc7", "relu5_3", "relu4_3", "relu3_2", "relu2_2"])
        out = vgg_outputs(h_fc7, h_relu5_3, h_relu4_3, h_relu3_2, h_relu2_2)
        return out


class VGGFeatureExtractor(nn.Module):
    """ FeatureExtractor of CRNN (https://arxiv.org/pdf/1507.05717.pdf) """

    def __init__(self, n_input_channels: int = 1, n_output_channels: int = 512):
        super(VGGFeatureExtractor, self).__init__()

        self.output_channel = [
            int(n_output_channels / 8),
            int(n_output_channels / 4),
            int(n_output_channels / 2),
            n_output_channels,
        ]  # [64, 128, 256, 512]
        self.ConvNet = nn.Sequential(
            nn.Conv2d(n_input_channels, self.output_channel[0], 3, 1, 1),
            nn.ReLU(True),
            nn.MaxPool2d(2, 2),  # 64x16x50
            nn.Conv2d(self.output_channel[0], self.output_channel[1], 3, 1, 1),
            nn.ReLU(True),
            nn.MaxPool2d(2, 2),  # 128x8x25
            nn.Conv2d(self.output_channel[1], self.output_channel[2], 3, 1, 1),
            nn.ReLU(True),  # 256x8x25
            nn.Conv2d(self.output_channel[2], self.output_channel[2], 3, 1, 1),
            nn.ReLU(True),
            nn.MaxPool2d((2, 1), (2, 1)),  # 256x4x25
            nn.Conv2d(
                self.output_channel[2],
                self.output_channel[3],
                3,
                1,
                1,
                bias=False,
            ),
            nn.BatchNorm2d(self.output_channel[3]),
            nn.ReLU(True),  # 512x4x25
            nn.Conv2d(
                self.output_channel[3],
                self.output_channel[3],
                3,
                1,
                1,
                bias=False,
            ),
            nn.BatchNorm2d(self.output_channel[3]),
            nn.ReLU(True),
            nn.MaxPool2d((2, 1), (2, 1)),  # 512x2x25
            nn.Conv2d(self.output_channel[3], self.output_channel[3], 2, 1, 0),
            nn.ReLU(True),
        )  # 512x1x24

    def forward(self, x):
        return self.ConvNet(x)


class BidirectionalLSTM(nn.Module):

    def __init__(self, input_size: int, hidden_size: int, output_size: int):
        super(BidirectionalLSTM, self).__init__()
        self.rnn = nn.LSTM(
            input_size,
            hidden_size,
            bidirectional=True,
            batch_first=True,
        )
        self.linear = nn.Linear(hidden_size * 2, output_size)

    def forward(self, x):
        """
        x : visual feature [batch_size x T x input_size]
        output : contextual feature [batch_size x T x output_size]
        """
        self.rnn.flatten_parameters()
        recurrent, _ = self.rnn(
            x
        )  # batch_size x T x input_size -> batch_size x T x (2*hidden_size)
        output = self.linear(recurrent)  # batch_size x T x output_size
        return output


class ResNetFeatureExtractor(nn.Module):
    """
    FeatureExtractor of FAN
    (http://openaccess.thecvf.com/content_ICCV_2017/papers/Cheng_Focusing_Attention_Towards_ICCV_2017_paper.pdf)

    """

    def __init__(self, n_input_channels: int = 1, n_output_channels: int = 512):
        super(ResNetFeatureExtractor, self).__init__()
        self.ConvNet = ResNet(
            n_input_channels,
            n_output_channels,
            BasicBlock,
            [1, 2, 5, 3],
        )

    def forward(self, inputs):
        return self.ConvNet(inputs)


class BasicBlock(nn.Module):
    expansion = 1

    def __init__(self,
                 inplanes: int,
                 planes: int,
                 stride: int = 1,
                 downsample=None):
        super(BasicBlock, self).__init__()
        self.conv1 = self._conv3x3(inplanes, planes)
        self.bn1 = nn.BatchNorm2d(planes)
        self.conv2 = self._conv3x3(planes, planes)
        self.bn2 = nn.BatchNorm2d(planes)
        self.relu = nn.ReLU(inplace=True)
        self.downsample = downsample
        self.stride = stride

    def _conv3x3(self, in_planes, out_planes, stride=1):
        "3x3 convolution with padding"
        return nn.Conv2d(
            in_planes,
            out_planes,
            kernel_size=3,
            stride=stride,
            padding=1,
            bias=False,
        )

    def forward(self, x):
        residual = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)

        if self.downsample is not None:
            residual = self.downsample(x)
        out += residual
        out = self.relu(out)

        return out


class ResNet(nn.Module):

    def __init__(
        self,
        n_input_channels: int,
        n_output_channels: int,
        block,
        layers,
    ):
        """
        :param n_input_channels (int): The number of input channels of the feature extractor
        :param n_output_channels (int): The number of output channels of the feature extractor
        :param block:
        :param layers:
        """
        super(ResNet, self).__init__()

        self.output_channel_blocks = [
            int(n_output_channels / 4),
            int(n_output_channels / 2),
            n_output_channels,
            n_output_channels,
        ]

        self.inplanes = int(n_output_channels / 8)
        self.conv0_1 = nn.Conv2d(
            n_input_channels,
            int(n_output_channels / 16),
            kernel_size=3,
            stride=1,
            padding=1,
            bias=False,
        )
        self.bn0_1 = nn.BatchNorm2d(int(n_output_channels / 16))
        self.conv0_2 = nn.Conv2d(
            int(n_output_channels / 16),
            self.inplanes,
            kernel_size=3,
            stride=1,
            padding=1,
            bias=False,
        )
        self.bn0_2 = nn.BatchNorm2d(self.inplanes)
        self.relu = nn.ReLU(inplace=True)

        self.maxpool1 = nn.MaxPool2d(kernel_size=2, stride=2, padding=0)
        self.layer1 = self._make_layer(
            block,
            self.output_channel_blocks[0],
            layers[0],
        )
        self.conv1 = nn.Conv2d(
            self.output_channel_blocks[0],
            self.output_channel_blocks[0],
            kernel_size=3,
            stride=1,
            padding=1,
            bias=False,
        )
        self.bn1 = nn.BatchNorm2d(self.output_channel_blocks[0])

        self.maxpool2 = nn.MaxPool2d(kernel_size=2, stride=2, padding=0)
        self.layer2 = self._make_layer(
            block,
            self.output_channel_blocks[1],
            layers[1],
            stride=1,
        )
        self.conv2 = nn.Conv2d(
            self.output_channel_blocks[1],
            self.output_channel_blocks[1],
            kernel_size=3,
            stride=1,
            padding=1,
            bias=False,
        )
        self.bn2 = nn.BatchNorm2d(self.output_channel_blocks[1])

        self.maxpool3 = nn.MaxPool2d(
            kernel_size=2,
            stride=(2, 1),
            padding=(0, 1),
        )
        self.layer3 = self._make_layer(
            block,
            self.output_channel_blocks[2],
            layers[2],
            stride=1,
        )
        self.conv3 = nn.Conv2d(
            self.output_channel_blocks[2],
            self.output_channel_blocks[2],
            kernel_size=3,
            stride=1,
            padding=1,
            bias=False,
        )
        self.bn3 = nn.BatchNorm2d(self.output_channel_blocks[2])

        self.layer4 = self._make_layer(
            block,
            self.output_channel_blocks[3],
            layers[3],
            stride=1,
        )
        self.conv4_1 = nn.Conv2d(
            self.output_channel_blocks[3],
            self.output_channel_blocks[3],
            kernel_size=2,
            stride=(2, 1),
            padding=(0, 1),
            bias=False,
        )
        self.bn4_1 = nn.BatchNorm2d(self.output_channel_blocks[3])
        self.conv4_2 = nn.Conv2d(
            self.output_channel_blocks[3],
            self.output_channel_blocks[3],
            kernel_size=2,
            stride=1,
            padding=0,
            bias=False,
        )
        self.bn4_2 = nn.BatchNorm2d(self.output_channel_blocks[3])

    def _make_layer(self, block, planes, blocks, stride=1):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(
                nn.Conv2d(
                    self.inplanes,
                    planes * block.expansion,
                    kernel_size=1,
                    stride=stride,
                    bias=False,
                ),
                nn.BatchNorm2d(planes * block.expansion),
            )

        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample))
        self.inplanes = planes * block.expansion
        for i in range(1, blocks):
            layers.append(block(self.inplanes, planes))

        return nn.Sequential(*layers)

    def forward(self, x):
        x = self.conv0_1(x)
        x = self.bn0_1(x)
        x = self.relu(x)
        x = self.conv0_2(x)
        x = self.bn0_2(x)
        x = self.relu(x)

        x = self.maxpool1(x)
        x = self.layer1(x)
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)

        x = self.maxpool2(x)
        x = self.layer2(x)
        x = self.conv2(x)
        x = self.bn2(x)
        x = self.relu(x)

        x = self.maxpool3(x)
        x = self.layer3(x)
        x = self.conv3(x)
        x = self.bn3(x)
        x = self.relu(x)

        x = self.layer4(x)
        x = self.conv4_1(x)
        x = self.bn4_1(x)
        x = self.relu(x)
        x = self.conv4_2(x)
        x = self.bn4_2(x)
        x = self.relu(x)

        return x


class TpsSpatialTransformerNetwork(nn.Module):
    """ Rectification Network of RARE, namely TPS based STN """

    def __init__(self, F, I_size, I_r_size, I_channel_num: int = 1):
        """Based on RARE TPS
        input:
            batch_I: Batch Input Image [batch_size x I_channel_num x I_height x I_width]
            I_size : (height, width) of the input image I
            I_r_size : (height, width) of the rectified image I_r
            I_channel_num : the number of channels of the input image I
        output:
            batch_I_r: rectified image [batch_size x I_channel_num x I_r_height x I_r_width]
        """
        super(TpsSpatialTransformerNetwork, self).__init__()
        self.F = F
        self.I_size = I_size
        self.I_r_size = I_r_size  # = (I_r_height, I_r_width)
        self.I_channel_num = I_channel_num
        self.LocalizationNetwork = LocalizationNetwork(
            self.F,
            self.I_channel_num,
        )
        self.GridGenerator = GridGenerator(self.F, self.I_r_size)

    def forward(self, batch_I):
        batch_C_prime = self.LocalizationNetwork(batch_I)  # batch_size x K x 2
        build_P_prime = self.GridGenerator.build_P_prime(
            batch_C_prime)  # batch_size x n (= I_r_width x I_r_height) x 2
        build_P_prime_reshape = build_P_prime.reshape(
            [build_P_prime.size(0), self.I_r_size[0], self.I_r_size[1], 2])

        batch_I_r = F.grid_sample(
            batch_I,
            build_P_prime_reshape,
            padding_mode="border",
        )

        return batch_I_r


class LocalizationNetwork(nn.Module):
    """ Localization Network of RARE, which predicts C' (K x 2) from I (I_width x I_height) """

    def __init__(self, F, I_channel_num: int):
        super(LocalizationNetwork, self).__init__()
        self.F = F
        self.I_channel_num = I_channel_num
        self.conv = nn.Sequential(
            nn.Conv2d(
                in_channels=self.I_channel_num,
                out_channels=64,
                kernel_size=3,
                stride=1,
                padding=1,
                bias=False,
            ),
            nn.BatchNorm2d(64),
            nn.ReLU(True),
            nn.MaxPool2d(2, 2),  # batch_size x 64 x I_height/2 x I_width/2
            nn.Conv2d(64, 128, 3, 1, 1, bias=False),
            nn.BatchNorm2d(128),
            nn.ReLU(True),
            nn.MaxPool2d(2, 2),  # batch_size x 128 x I_height/4 x I_width/4
            nn.Conv2d(128, 256, 3, 1, 1, bias=False),
            nn.BatchNorm2d(256),
            nn.ReLU(True),
            nn.MaxPool2d(2, 2),  # batch_size x 256 x I_height/8 x I_width/8
            nn.Conv2d(256, 512, 3, 1, 1, bias=False),
            nn.BatchNorm2d(512),
            nn.ReLU(True),
            nn.AdaptiveAvgPool2d(1),  # batch_size x 512
        )

        self.localization_fc1 = nn.Sequential(nn.Linear(512, 256),
                                              nn.ReLU(True))
        self.localization_fc2 = nn.Linear(256, self.F * 2)

        # Init fc2 in LocalizationNetwork
        self.localization_fc2.weight.data.fill_(0)

        # see RARE paper Fig. 6 (a)
        ctrl_pts_x = np.linspace(-1.0, 1.0, int(F / 2))
        ctrl_pts_y_top = np.linspace(0.0, -1.0, num=int(F / 2))
        ctrl_pts_y_bottom = np.linspace(1.0, 0.0, num=int(F / 2))
        ctrl_pts_top = np.stack([ctrl_pts_x, ctrl_pts_y_top], axis=1)
        ctrl_pts_bottom = np.stack([ctrl_pts_x, ctrl_pts_y_bottom], axis=1)
        initial_bias = np.concatenate([ctrl_pts_top, ctrl_pts_bottom], axis=0)
        self.localization_fc2.bias.data = (
            torch.from_numpy(initial_bias).float().view(-1))

    def forward(self, batch_I):
        """
        :param batch_I : Batch Input Image [batch_size x I_channel_num x I_height x I_width]
        :return: batch_C_prime : Predicted coordinates of fiducial points for input batch [batch_size x F x 2]
        """
        batch_size = batch_I.size(0)
        features = self.conv(batch_I).view(batch_size, -1)
        batch_C_prime = self.localization_fc2(
            self.localization_fc1(features)).view(batch_size, self.F, 2)
        return batch_C_prime


class GridGenerator(nn.Module):
    """ Grid Generator of RARE, which produces P_prime by multipling T with P """

    def __init__(self, F, I_r_size):
        """ Generate P_hat and inv_delta_C for later """
        super(GridGenerator, self).__init__()
        self.eps = 1e-6
        self.I_r_height, self.I_r_width = I_r_size
        self.F = F
        self.C = self._build_C(self.F)  # F x 2
        self.P = self._build_P(self.I_r_width, self.I_r_height)

        # for multi-gpu, you need register buffer
        self.register_buffer(
            "inv_delta_C",
            torch.tensor(self._build_inv_delta_C(
                self.F,
                self.C,
            )).float(),
        )  # F+3 x F+3
        self.register_buffer(
            "P_hat",
            torch.tensor(self._build_P_hat(
                self.F,
                self.C,
                self.P,
            )).float(),
        )  # n x F+3

    def _build_C(self, F):
        """ Return coordinates of fiducial points in I_r; C """
        ctrl_pts_x = np.linspace(-1.0, 1.0, int(F / 2))
        ctrl_pts_y_top = -1 * np.ones(int(F / 2))
        ctrl_pts_y_bottom = np.ones(int(F / 2))
        ctrl_pts_top = np.stack([ctrl_pts_x, ctrl_pts_y_top], axis=1)
        ctrl_pts_bottom = np.stack([ctrl_pts_x, ctrl_pts_y_bottom], axis=1)
        C = np.concatenate([ctrl_pts_top, ctrl_pts_bottom], axis=0)
        return C  # F x 2

    def _build_inv_delta_C(self, F, C):
        """ Return inv_delta_C which is needed to calculate T """
        hat_C = np.zeros((F, F), dtype=float)  # F x F
        for i in range(0, F):
            for j in range(i, F):
                r = np.linalg.norm(C[i] - C[j])
                hat_C[i, j] = r
                hat_C[j, i] = r
        np.fill_diagonal(hat_C, 1)
        hat_C = (hat_C**2) * np.log(hat_C)
        # print(C.shape, hat_C.shape)
        delta_C = np.concatenate(  # F+3 x F+3
            [
                np.concatenate([np.ones((F, 1)), C, hat_C], axis=1),  # F x F+3
                np.concatenate([np.zeros(
                    (2, 3)), np.transpose(C)], axis=1),  # 2 x F+3
                np.concatenate([np.zeros(
                    (1, 3)), np.ones((1, F))], axis=1),  # 1 x F+3
            ],
            axis=0,
        )
        inv_delta_C = np.linalg.inv(delta_C)
        return inv_delta_C  # F+3 x F+3

    def _build_P(self, I_r_width, I_r_height):
        I_r_grid_x = (np.arange(-I_r_width, I_r_width, 2) +
                      1.0) / I_r_width  # self.I_r_width
        I_r_grid_y = (np.arange(-I_r_height, I_r_height, 2) +
                      1.0) / I_r_height  # self.I_r_height
        P = np.stack(  # self.I_r_width x self.I_r_height x 2
            np.meshgrid(I_r_grid_x, I_r_grid_y),
            axis=2)
        return P.reshape([-1, 2])  # n (= self.I_r_width x self.I_r_height) x 2

    def _build_P_hat(self, F, C, P):
        n = P.shape[0]  # n (= self.I_r_width x self.I_r_height)
        P_tile = np.tile(np.expand_dims(P, axis=1),
                         (1, F, 1))  # n x 2 -> n x 1 x 2 -> n x F x 2
        C_tile = np.expand_dims(C, axis=0)  # 1 x F x 2
        P_diff = P_tile - C_tile  # n x F x 2
        rbf_norm = np.linalg.norm(
            P_diff,
            ord=2,
            axis=2,
            keepdims=False,
        )  # n x F
        rbf = np.multiply(
            np.square(rbf_norm),
            np.log(rbf_norm + self.eps),
        )  # n x F
        P_hat = np.concatenate([np.ones((n, 1)), P, rbf], axis=1)
        return P_hat  # n x F+3

    def build_P_prime(self, batch_C_prime):
        """ Generate Grid from batch_C_prime [batch_size x F x 2] """
        batch_size = batch_C_prime.size(0)
        batch_inv_delta_C = self.inv_delta_C.repeat(batch_size, 1, 1)
        batch_P_hat = self.P_hat.repeat(batch_size, 1, 1)
        batch_C_prime_with_zeros = torch.cat(
            (batch_C_prime, torch.zeros(batch_size, 3, 2).float().to(device)),
            dim=1)  # batch_size x F+3 x 2
        batch_T = torch.bmm(
            batch_inv_delta_C,
            batch_C_prime_with_zeros,
        )  # batch_size x F+3 x 2
        batch_P_prime = torch.bmm(batch_P_hat, batch_T)  # batch_size x n x 2
        return batch_P_prime  # batch_size x n x 2
