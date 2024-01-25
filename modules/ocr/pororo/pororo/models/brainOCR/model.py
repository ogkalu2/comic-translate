"""
This code is adapted from
https://github.com/clovaai/deep-text-recognition-benchmark/blob/master/model.py
"""

import torch.nn as nn
from torch import Tensor

from .modules.feature_extraction import (
    ResNetFeatureExtractor,
    VGGFeatureExtractor,
)
from .modules.prediction import Attention
from .modules.sequence_modeling import BidirectionalLSTM
from .modules.transformation import TpsSpatialTransformerNetwork


class Model(nn.Module):

    def __init__(self, opt2val: dict):
        super(Model, self).__init__()

        input_channel = opt2val["input_channel"]
        output_channel = opt2val["output_channel"]
        hidden_size = opt2val["hidden_size"]
        vocab_size = opt2val["vocab_size"]
        num_fiducial = opt2val["num_fiducial"]
        imgH = opt2val["imgH"]
        imgW = opt2val["imgW"]
        FeatureExtraction = opt2val["FeatureExtraction"]
        Transformation = opt2val["Transformation"]
        SequenceModeling = opt2val["SequenceModeling"]
        Prediction = opt2val["Prediction"]

        # Transformation
        if Transformation == "TPS":
            self.Transformation = TpsSpatialTransformerNetwork(
                F=num_fiducial,
                I_size=(imgH, imgW),
                I_r_size=(imgH, imgW),
                I_channel_num=input_channel,
            )
        else:
            print("No Transformation module specified")

        # FeatureExtraction
        if FeatureExtraction == "VGG":
            extractor = VGGFeatureExtractor
        else:  # ResNet
            extractor = ResNetFeatureExtractor
        self.FeatureExtraction = extractor(
            input_channel,
            output_channel,
            opt2val,
        )
        self.FeatureExtraction_output = output_channel  # int(imgH/16-1) * 512
        self.AdaptiveAvgPool = nn.AdaptiveAvgPool2d(
            (None, 1))  # Transform final (imgH/16-1) -> 1

        # Sequence modeling
        if SequenceModeling == "BiLSTM":
            self.SequenceModeling = nn.Sequential(
                BidirectionalLSTM(
                    self.FeatureExtraction_output,
                    hidden_size,
                    hidden_size,
                ),
                BidirectionalLSTM(hidden_size, hidden_size, hidden_size),
            )
            self.SequenceModeling_output = hidden_size
        else:
            print("No SequenceModeling module specified")
            self.SequenceModeling_output = self.FeatureExtraction_output

        # Prediction
        if Prediction == "CTC":
            self.Prediction = nn.Linear(
                self.SequenceModeling_output,
                vocab_size,
            )
        elif Prediction == "Attn":
            self.Prediction = Attention(
                self.SequenceModeling_output,
                hidden_size,
                vocab_size,
            )
        elif Prediction == "Transformer":  # TODO
            pass
        else:
            raise Exception("Prediction is neither CTC or Attn")

    def forward(self, x: Tensor):
        """
        :param x: (batch, input_channel, height, width)
        :return:
        """
        # Transformation stage
        x = self.Transformation(x)

        # Feature extraction stage
        visual_feature = self.FeatureExtraction(
            x)  # (b, output_channel=512, h=3, w)
        visual_feature = self.AdaptiveAvgPool(visual_feature.permute(
            0, 3, 1, 2))  # (b, w, channel=512, h=1)
        visual_feature = visual_feature.squeeze(3)  # (b, w, channel=512)

        # Sequence modeling stage
        self.SequenceModeling.eval()
        contextual_feature = self.SequenceModeling(visual_feature)

        # Prediction stage
        prediction = self.Prediction(
            contextual_feature.contiguous())  # (b, T, num_classes)

        return prediction
