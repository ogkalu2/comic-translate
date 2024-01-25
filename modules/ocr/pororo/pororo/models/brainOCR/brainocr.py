"""
This code is primarily based on the following:
https://github.com/JaidedAI/EasyOCR/blob/8af936ba1b2f3c230968dc1022d0cd3e9ca1efbb/easyocr/easyocr.py

Basic usage:
>>> from pororo import Pororo
>>> ocr = Pororo(task="ocr", lang="ko")
>>> ocr("IMAGE_FILE")
"""

import ast
from logging import getLogger
from typing import List

import cv2
import numpy as np
from PIL import Image

from .detection import get_detector, get_textbox
from .recognition import get_recognizer, get_text
from .utils import (
    diff,
    get_image_list,
    get_paragraph,
    group_text_box,
    reformat_input,
)

LOGGER = getLogger(__name__)


class Reader(object):

    def __init__(
        self,
        lang: str,
        det_model_ckpt_fp: str,
        rec_model_ckpt_fp: str,
        opt_fp: str,
        device: str,
    ) -> None:
        """
        TODO @karter: modify this such that you download the pretrained checkpoint files
        Parameters:
            lang: language code. e.g, "en" or "ko"
            det_model_ckpt_fp: Detection model's checkpoint path e.g., 'craft_mlt_25k.pth'
            rec_model_ckpt_fp: Recognition model's checkpoint path
            opt_fp: option file path
        """
        # Plug options in the dictionary
        opt2val = self.parse_options(opt_fp)  # e.g., {"imgH": 64, ...}
        opt2val["vocab"] = self.build_vocab(opt2val["character"])
        opt2val["vocab_size"] = len(opt2val["vocab"])
        opt2val["device"] = device
        opt2val["lang"] = lang
        opt2val["det_model_ckpt_fp"] = det_model_ckpt_fp
        opt2val["rec_model_ckpt_fp"] = rec_model_ckpt_fp

        # Get model objects
        self.detector = get_detector(det_model_ckpt_fp, opt2val["device"])
        self.recognizer, self.converter = get_recognizer(opt2val)
        self.opt2val = opt2val

    @staticmethod
    def parse_options(opt_fp: str) -> dict:
        opt2val = dict()
        for line in open(opt_fp, "r", encoding="utf8"):
            line = line.strip()
            if ": " in line:
                opt, val = line.split(": ", 1)
                try:
                    opt2val[opt] = ast.literal_eval(val)
                except:
                    opt2val[opt] = val

        return opt2val

    @staticmethod
    def build_vocab(character: str) -> List[str]:
        """Returns vocabulary (=list of characters)"""
        vocab = ["[blank]"] + list(
            character)  # dummy '[blank]' token for CTCLoss (index 0)
        return vocab

    def detect(self, img: np.ndarray, opt2val: dict):
        """
        :return:
            horizontal_list (list): e.g., [[613, 1496, 51, 190], [136, 1544, 134, 508]]
            free_list (list): e.g., []
        """
        text_box = get_textbox(self.detector, img, opt2val)
        horizontal_list, free_list = group_text_box(
            text_box,
            opt2val["slope_ths"],
            opt2val["ycenter_ths"],
            opt2val["height_ths"],
            opt2val["width_ths"],
            opt2val["add_margin"],
        )

        min_size = opt2val["min_size"]
        if min_size:
            horizontal_list = [
                i for i in horizontal_list
                if max(i[1] - i[0], i[3] - i[2]) > min_size
            ]
            free_list = [
                i for i in free_list
                if max(diff([c[0] for c in i]), diff([c[1]
                                                      for c in i])) > min_size
            ]

        return horizontal_list, free_list

    def recognize(
        self,
        img_cv_grey: np.ndarray,
        horizontal_list: list,
        free_list: list,
        opt2val: dict,
    ):
        """
        Read text in the image
        :return:
            result (list): bounding box, text and confident score
                e.g., [([[189, 75], [469, 75], [469, 165], [189, 165]], '愚园路', 0.3754989504814148),
                 ([[86, 80], [134, 80], [134, 128], [86, 128]], '西', 0.40452659130096436),
                 ([[517, 81], [565, 81], [565, 123], [517, 123]], '东', 0.9989598989486694),
                 ([[78, 126], [136, 126], [136, 156], [78, 156]], '315', 0.8125889301300049),
                 ([[514, 126], [574, 126], [574, 156], [514, 156]], '309', 0.4971577227115631),
                 ([[226, 170], [414, 170], [414, 220], [226, 220]], 'Yuyuan Rd.', 0.8261902332305908),
                 ([[79, 173], [125, 173], [125, 213], [79, 213]], 'W', 0.9848111271858215),
                 ([[529, 173], [569, 173], [569, 213], [529, 213]], 'E', 0.8405593633651733)]
             or list of texts (if skip_details is True)
                e.g., ['愚园路', '西', '东', '315', '309', 'Yuyuan Rd.', 'W', 'E']
        """
        imgH = opt2val["imgH"]
        paragraph = opt2val["paragraph"]
        skip_details = opt2val["skip_details"]

        if (horizontal_list is None) and (free_list is None):
            y_max, x_max = img_cv_grey.shape
            ratio = x_max / y_max
            max_width = int(imgH * ratio)
            crop_img = cv2.resize(
                img_cv_grey,
                (max_width, imgH),
                interpolation=Image.LANCZOS,
            )
            image_list = [([[0, 0], [x_max, 0], [x_max, y_max],
                            [0, y_max]], crop_img)]
        else:
            image_list, max_width = get_image_list(
                horizontal_list,
                free_list,
                img_cv_grey,
                model_height=imgH,
            )

        result = get_text(image_list, self.recognizer, self.converter, opt2val)

        if paragraph:
            result = get_paragraph(result, mode="ltr")

        if skip_details:  # texts only
            return [item[1] for item in result]
        else:  # full outputs: bounding box, text and confident score
            return result

    def __call__(
        self,
        image,
        batch_size: int = 1,
        n_workers: int = 0,
        skip_details: bool = False,
        paragraph: bool = False,
        min_size: int = 20,
        contrast_ths: float = 0.1,
        adjust_contrast: float = 0.5,
        filter_ths: float = 0.003,
        text_threshold: float = 0.7,
        low_text: float = 0.4,
        link_threshold: float = 0.4,
        canvas_size: int = 2560,
        mag_ratio: float = 1.0,
        slope_ths: float = 0.1,
        ycenter_ths: float = 0.5,
        height_ths: float = 0.5,
        width_ths: float = 0.5,
        add_margin: float = 0.1,
    ):
        """
        Detect text in the image and then recognize it.
        :param image: file path or numpy-array or a byte stream object
        :param batch_size:
        :param n_workers:
        :param skip_details:
        :param paragraph:
        :param min_size:
        :param contrast_ths:
        :param adjust_contrast:
        :param filter_ths:
        :param text_threshold:
        :param low_text:
        :param link_threshold:
        :param canvas_size:
        :param mag_ratio:
        :param slope_ths:
        :param ycenter_ths:
        :param height_ths:
        :param width_ths:
        :param add_margin:
        :return:
        """
        # update `opt2val`
        self.opt2val["batch_size"] = batch_size
        self.opt2val["n_workers"] = n_workers
        self.opt2val["skip_details"] = skip_details
        self.opt2val["paragraph"] = paragraph
        self.opt2val["min_size"] = min_size
        self.opt2val["contrast_ths"] = contrast_ths
        self.opt2val["adjust_contrast"] = adjust_contrast
        self.opt2val["filter_ths"] = filter_ths
        self.opt2val["text_threshold"] = text_threshold
        self.opt2val["low_text"] = low_text
        self.opt2val["link_threshold"] = link_threshold
        self.opt2val["canvas_size"] = canvas_size
        self.opt2val["mag_ratio"] = mag_ratio
        self.opt2val["slope_ths"] = slope_ths
        self.opt2val["ycenter_ths"] = ycenter_ths
        self.opt2val["height_ths"] = height_ths
        self.opt2val["width_ths"] = width_ths
        self.opt2val["add_margin"] = add_margin

        img, img_cv_grey = reformat_input(image)  # img, img_cv_grey: array

        horizontal_list, free_list = self.detect(img, self.opt2val)
        result = self.recognize(
            img_cv_grey,
            horizontal_list,
            free_list,
            self.opt2val,
        )

        return result
