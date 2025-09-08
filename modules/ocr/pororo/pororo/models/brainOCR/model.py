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
        # NOTE (ONNX): Original implementation used AdaptiveAvgPool2d((None, 1)) on a permuted
        # tensor to collapse the last spatial dimension to 1 while preserving width steps.
        # ONNX export fails because output_size contains a dynamic None. We instead perform
        # an explicit mean reduction over the height dimension later in forward(), which is
        # mathematically equivalent for average pooling over that full dimension and is
        # ONNX-friendly (maps to ReduceMean).

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
            x)  # (b, 512, h, w)
        # Average over height dimension (original code permuted then adaptive-pooled width->1).
        # Here we reduce height directly, producing (b, 512, w), then permute to (b, w, 512).
        visual_feature = visual_feature.mean(dim=2)  # (b, 512, w)
        visual_feature = visual_feature.permute(0, 2, 1)  # (b, w, 512)

        # Sequence modeling stage
        self.SequenceModeling.eval()
        contextual_feature = self.SequenceModeling(visual_feature)

        # Prediction stage
        prediction = self.Prediction(
            contextual_feature.contiguous())  # (b, T, num_classes)

        return prediction
