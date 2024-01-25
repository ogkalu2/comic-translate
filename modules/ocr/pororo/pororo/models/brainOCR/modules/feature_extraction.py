import torch.nn as nn


class VGGFeatureExtractor(nn.Module):
    """ FeatureExtractor of CRNN (https://arxiv.org/pdf/1507.05717.pdf) """

    def __init__(self,
                 n_input_channels: int = 1,
                 n_output_channels: int = 512,
                 opt2val=None):
        super(VGGFeatureExtractor, self).__init__()

        self.output_channel = [
            int(n_output_channels / 8),
            int(n_output_channels / 4),
            int(n_output_channels / 2),
            n_output_channels,
        ]  # [64, 128, 256, 512]

        rec_model_ckpt_fp = opt2val["rec_model_ckpt_fp"]
        if "baseline" in rec_model_ckpt_fp:
            self.ConvNet = nn.Sequential(
                nn.Conv2d(n_input_channels, self.output_channel[0], 3, 1, 1),
                nn.ReLU(True),
                nn.MaxPool2d(2, 2),  # 64x16x50
                nn.Conv2d(self.output_channel[0], self.output_channel[1], 3, 1,
                          1),
                nn.ReLU(True),
                nn.MaxPool2d(2, 2),  # 128x8x25
                nn.Conv2d(self.output_channel[1], self.output_channel[2], 3, 1,
                          1),
                nn.ReLU(True),  # 256x8x25
                nn.Conv2d(self.output_channel[2], self.output_channel[2], 3, 1,
                          1),
                nn.ReLU(True),
                nn.MaxPool2d((2, 1), (2, 1)),  # 256x4x25
                nn.Conv2d(self.output_channel[2],
                          self.output_channel[3],
                          3,
                          1,
                          1,
                          bias=False),
                nn.BatchNorm2d(self.output_channel[3]),
                nn.ReLU(True),  # 512x4x25
                nn.Conv2d(self.output_channel[3],
                          self.output_channel[3],
                          3,
                          1,
                          1,
                          bias=False),
                nn.BatchNorm2d(self.output_channel[3]),
                nn.ReLU(True),
                nn.MaxPool2d((2, 1), (2, 1)),  # 512x2x25
                # nn.Conv2d(self.output_channel[3], self.output_channel[3], 2, 1, 0), nn.ReLU(True))  # 512x1x24
                nn.ConvTranspose2d(self.output_channel[3],
                                   self.output_channel[3], 2, 2),
                nn.ReLU(True),
            )  # 512x4x50
        else:
            self.ConvNet = nn.Sequential(
                nn.Conv2d(n_input_channels, self.output_channel[0], 3, 1, 1),
                nn.ReLU(True),
                nn.MaxPool2d(2, 2),  # 64x16x50
                nn.Conv2d(self.output_channel[0], self.output_channel[1], 3, 1,
                          1),
                nn.ReLU(True),
                nn.MaxPool2d(2, 2),  # 128x8x25
                nn.Conv2d(self.output_channel[1], self.output_channel[2], 3, 1,
                          1),
                nn.ReLU(True),  # 256x8x25
                nn.Conv2d(self.output_channel[2], self.output_channel[2], 3, 1,
                          1),
                nn.ReLU(True),
                nn.MaxPool2d((2, 1), (2, 1)),  # 256x4x25
                nn.Conv2d(self.output_channel[2],
                          self.output_channel[3],
                          3,
                          1,
                          1,
                          bias=False),
                nn.BatchNorm2d(self.output_channel[3]),
                nn.ReLU(True),  # 512x4x25
                nn.Conv2d(self.output_channel[3],
                          self.output_channel[3],
                          3,
                          1,
                          1,
                          bias=False),
                nn.BatchNorm2d(self.output_channel[3]),
                nn.ReLU(True),
                nn.MaxPool2d((2, 1), (2, 1)),  # 512x2x25
                # nn.Conv2d(self.output_channel[3], self.output_channel[3], 2, 1, 0), nn.ReLU(True))  # 512x1x24
                nn.ConvTranspose2d(self.output_channel[3],
                                   self.output_channel[3], 2, 2),
                nn.ReLU(True),  # 512x4x50
                nn.ConvTranspose2d(self.output_channel[3],
                                   self.output_channel[3], 2, 2),
                nn.ReLU(True),
            )  # 512x4x50

    def forward(self, x):
        return self.ConvNet(x)


class ResNetFeatureExtractor(nn.Module):
    """
    FeatureExtractor of FAN
    (http://openaccess.thecvf.com/content_ICCV_2017/papers/Cheng_Focusing_Attention_Towards_ICCV_2017_paper.pdf)
    """

    def __init__(self, n_input_channels: int = 1, n_output_channels: int = 512):
        super(ResNetFeatureExtractor, self).__init__()
        self.ConvNet = ResNet(n_input_channels, n_output_channels, BasicBlock,
                              [1, 2, 5, 3])

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
        return nn.Conv2d(in_planes,
                         out_planes,
                         kernel_size=3,
                         stride=stride,
                         padding=1,
                         bias=False)

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

    def __init__(self, n_input_channels: int, n_output_channels: int, block,
                 layers):
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
        self.layer1 = self._make_layer(block, self.output_channel_blocks[0],
                                       layers[0])
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
        self.layer2 = self._make_layer(block,
                                       self.output_channel_blocks[1],
                                       layers[1],
                                       stride=1)
        self.conv2 = nn.Conv2d(
            self.output_channel_blocks[1],
            self.output_channel_blocks[1],
            kernel_size=3,
            stride=1,
            padding=1,
            bias=False,
        )
        self.bn2 = nn.BatchNorm2d(self.output_channel_blocks[1])

        self.maxpool3 = nn.MaxPool2d(kernel_size=2,
                                     stride=(2, 1),
                                     padding=(0, 1))
        self.layer3 = self._make_layer(block,
                                       self.output_channel_blocks[2],
                                       layers[2],
                                       stride=1)
        self.conv3 = nn.Conv2d(
            self.output_channel_blocks[2],
            self.output_channel_blocks[2],
            kernel_size=3,
            stride=1,
            padding=1,
            bias=False,
        )
        self.bn3 = nn.BatchNorm2d(self.output_channel_blocks[2])

        self.layer4 = self._make_layer(block,
                                       self.output_channel_blocks[3],
                                       layers[3],
                                       stride=1)
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
