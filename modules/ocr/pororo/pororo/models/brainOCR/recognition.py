"""
This code is adapted from https://github.com/JaidedAI/EasyOCR/blob/8af936ba1b2f3c230968dc1022d0cd3e9ca1efbb/easyocr/recognition.py
"""

import math

import numpy as np
import torch
import torch.nn.functional as F
import torch.utils.data
import torchvision.transforms as transforms
from PIL import Image

from .model import Model
from .utils import CTCLabelConverter


def contrast_grey(img):
    high = np.percentile(img, 90)
    low = np.percentile(img, 10)
    return (high - low) / np.maximum(10, high + low), high, low


def adjust_contrast_grey(img, target: float = 0.4):
    contrast, high, low = contrast_grey(img)
    if contrast < target:
        img = img.astype(int)
        ratio = 200.0 / np.maximum(10, high - low)
        img = (img - low + 25) * ratio
        img = np.maximum(
            np.full(img.shape, 0),
            np.minimum(
                np.full(img.shape, 255),
                img,
            ),
        ).astype(np.uint8)
    return img


class NormalizePAD(object):

    def __init__(self, max_size, PAD_type: str = "right"):
        self.toTensor = transforms.ToTensor()
        self.max_size = max_size
        self.max_width_half = math.floor(max_size[2] / 2)
        self.PAD_type = PAD_type

    def __call__(self, img):
        img = self.toTensor(img)
        img.sub_(0.5).div_(0.5)
        c, h, w = img.size()
        Pad_img = torch.FloatTensor(*self.max_size).fill_(0)
        Pad_img[:, :, :w] = img  # right pad
        if self.max_size[2] != w:  # add border Pad
            Pad_img[:, :, w:] = (img[:, :, w - 1].unsqueeze(2).expand(
                c,
                h,
                self.max_size[2] - w,
            ))

        return Pad_img


class ListDataset(torch.utils.data.Dataset):

    def __init__(self, image_list: list):
        self.image_list = image_list
        self.nSamples = len(image_list)

    def __len__(self):
        return self.nSamples

    def __getitem__(self, index):
        img = self.image_list[index]
        return Image.fromarray(img, "L")


class AlignCollate(object):

    def __init__(self, imgH: int, imgW: int, adjust_contrast: float):
        self.imgH = imgH
        self.imgW = imgW
        self.keep_ratio_with_pad = True  # Do Not Change
        self.adjust_contrast = adjust_contrast

    def __call__(self, batch):
        batch = filter(lambda x: x is not None, batch)
        images = batch

        resized_max_w = self.imgW
        input_channel = 1
        transform = NormalizePAD((input_channel, self.imgH, resized_max_w))

        resized_images = []
        for image in images:
            w, h = image.size
            # augmentation here - change contrast
            if self.adjust_contrast > 0:
                image = np.array(image.convert("L"))
                image = adjust_contrast_grey(image, target=self.adjust_contrast)
                image = Image.fromarray(image, "L")

            ratio = w / float(h)
            if math.ceil(self.imgH * ratio) > self.imgW:
                resized_w = self.imgW
            else:
                resized_w = math.ceil(self.imgH * ratio)

            resized_image = image.resize((resized_w, self.imgH), Image.BICUBIC)
            resized_images.append(transform(resized_image))

        image_tensors = torch.cat([t.unsqueeze(0) for t in resized_images], 0)
        return image_tensors


def recognizer_predict(model, converter, test_loader, opt2val: dict):
    device = opt2val["device"]

    model.eval()
    result = []
    with torch.no_grad():
        for image_tensors in test_loader:
            batch_size = image_tensors.size(0)
            inputs = image_tensors.to(device)
            preds = model(inputs)  # (N, length, num_classes)

            # rebalance
            preds_prob = F.softmax(preds, dim=2)
            preds_prob = preds_prob.cpu().detach().numpy()
            pred_norm = preds_prob.sum(axis=2)
            preds_prob = preds_prob / np.expand_dims(pred_norm, axis=-1)
            preds_prob = torch.from_numpy(preds_prob).float().to(device)

            # Select max probabilty (greedy decoding), then decode index to character
            preds_lengths = torch.IntTensor([preds.size(1)] *
                                            batch_size)  # (N,)
            _, preds_indices = preds_prob.max(2)  # (N, length)
            preds_indices = preds_indices.view(-1)  # (N*length)
            preds_str = converter.decode_greedy(preds_indices, preds_lengths)

            preds_max_prob, _ = preds_prob.max(dim=2)

            for pred, pred_max_prob in zip(preds_str, preds_max_prob):
                confidence_score = pred_max_prob.cumprod(dim=0)[-1]
                result.append([pred, confidence_score.item()])

    return result


def get_recognizer(opt2val: dict):
    """
    :return:
        recognizer: recognition net
        converter: CTCLabelConverter
    """
    # converter
    vocab = opt2val["vocab"]
    converter = CTCLabelConverter(vocab)

    # recognizer
    recognizer = Model(opt2val)

    # state_dict
    rec_model_ckpt_fp = opt2val["rec_model_ckpt_fp"]
    device = opt2val["device"]
    state_dict = torch.load(rec_model_ckpt_fp, map_location=device)

    if device == "cuda":
        recognizer = torch.nn.DataParallel(recognizer).to(device)
    else:
        # TODO temporary: multigpu 학습한 뒤 ckpt loading 문제
        from collections import OrderedDict

        def _sync_tensor_name(state_dict):
            state_dict_ = OrderedDict()
            for name, val in state_dict.items():
                name = name.replace("module.", "")
                state_dict_[name] = val
            return state_dict_

        state_dict = _sync_tensor_name(state_dict)

    recognizer.load_state_dict(state_dict)

    return recognizer, converter


def get_text(image_list, recognizer, converter, opt2val: dict):
    imgW = opt2val["imgW"]
    imgH = opt2val["imgH"]
    adjust_contrast = opt2val["adjust_contrast"]
    batch_size = opt2val["batch_size"]
    n_workers = opt2val["n_workers"]
    contrast_ths = opt2val["contrast_ths"]

    # TODO: figure out what is this for
    # batch_max_length = int(imgW / 10)

    coord = [item[0] for item in image_list]
    img_list = [item[1] for item in image_list]
    AlignCollate_normal = AlignCollate(imgH, imgW, adjust_contrast)
    test_data = ListDataset(img_list)
    test_loader = torch.utils.data.DataLoader(
        test_data,
        batch_size=batch_size,
        shuffle=False,
        num_workers=n_workers,
        collate_fn=AlignCollate_normal,
        pin_memory=True,
    )

    # predict first round
    result1 = recognizer_predict(recognizer, converter, test_loader, opt2val)

    # predict second round
    low_confident_idx = [
        i for i, item in enumerate(result1) if (item[1] < contrast_ths)
    ]
    if len(low_confident_idx) > 0:
        img_list2 = [img_list[i] for i in low_confident_idx]
        AlignCollate_contrast = AlignCollate(imgH, imgW, adjust_contrast)
        test_data = ListDataset(img_list2)
        test_loader = torch.utils.data.DataLoader(
            test_data,
            batch_size=batch_size,
            shuffle=False,
            num_workers=n_workers,
            collate_fn=AlignCollate_contrast,
            pin_memory=True,
        )
        result2 = recognizer_predict(recognizer, converter, test_loader,
                                     opt2val)

    result = []
    for i, zipped in enumerate(zip(coord, result1)):
        box, pred1 = zipped
        if i in low_confident_idx:
            pred2 = result2[low_confident_idx.index(i)]
            if pred1[1] > pred2[1]:
                result.append((box, pred1[0], pred1[1]))
            else:
                result.append((box, pred2[0], pred2[1]))
        else:
            result.append((box, pred1[0], pred1[1]))

    return result
