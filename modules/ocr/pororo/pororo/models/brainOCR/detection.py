"""
This code is adapted from https://github.com/JaidedAI/EasyOCR/blob/master/easyocr/detection.py
"""

from collections import OrderedDict

import cv2
import numpy as np
import torch
import torch.backends.cudnn as cudnn
from torch.autograd import Variable

from .craft import CRAFT
from .craft_utils import adjust_result_coordinates, get_det_boxes
from .imgproc import normalize_mean_variance, resize_aspect_ratio


def copy_state_dict(state_dict):
    if list(state_dict.keys())[0].startswith("module"):
        start_idx = 1
    else:
        start_idx = 0
    new_state_dict = OrderedDict()
    for k, v in state_dict.items():
        name = ".".join(k.split(".")[start_idx:])
        new_state_dict[name] = v
    return new_state_dict


def test_net(image: np.ndarray, net, opt2val: dict):
    canvas_size = opt2val["canvas_size"]
    mag_ratio = opt2val["mag_ratio"]
    text_threshold = opt2val["text_threshold"]
    link_threshold = opt2val["link_threshold"]
    low_text = opt2val["low_text"]
    device = opt2val["device"]

    # resize
    img_resized, target_ratio, size_heatmap = resize_aspect_ratio(
        image, canvas_size, interpolation=cv2.INTER_LINEAR, mag_ratio=mag_ratio)
    ratio_h = ratio_w = 1 / target_ratio

    # preprocessing
    x = normalize_mean_variance(img_resized)
    x = torch.from_numpy(x).permute(2, 0, 1)  # [h, w, c] to [c, h, w]
    x = Variable(x.unsqueeze(0))  # [c, h, w] to [b, c, h, w]
    x = x.to(device)

    # forward pass
    with torch.no_grad():
        y, feature = net(x)

    # make score and link map
    score_text = y[0, :, :, 0].cpu().data.numpy()
    score_link = y[0, :, :, 1].cpu().data.numpy()

    # Post-processing
    boxes, polys = get_det_boxes(
        score_text,
        score_link,
        text_threshold,
        link_threshold,
        low_text,
    )

    # coordinate adjustment
    boxes = adjust_result_coordinates(boxes, ratio_w, ratio_h)
    polys = adjust_result_coordinates(polys, ratio_w, ratio_h)
    for k in range(len(polys)):
        if polys[k] is None:
            polys[k] = boxes[k]

    return boxes, polys


def get_detector(det_model_ckpt_fp: str, device: str = "cpu"):
    net = CRAFT()

    net.load_state_dict(
        copy_state_dict(torch.load(det_model_ckpt_fp, map_location=device)))
    if device == "cuda":
        net = torch.nn.DataParallel(net).to(device)
        cudnn.benchmark = False

    net.eval()
    return net


def get_textbox(detector, image: np.ndarray, opt2val: dict):
    bboxes, polys = test_net(image, detector, opt2val)
    result = []
    for i, box in enumerate(polys):
        poly = np.array(box).astype(np.int32).reshape((-1))
        result.append(poly)

    return result
