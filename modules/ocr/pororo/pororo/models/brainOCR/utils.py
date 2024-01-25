"""
This code is adapted from https://github.com/JaidedAI/EasyOCR/blob/8af936ba1b2f3c230968dc1022d0cd3e9ca1efbb/easyocr/utils.py
"""

import math
import os
from urllib.request import urlretrieve

import cv2
import numpy as np
import torch
from PIL import Image
from torch import Tensor

from .imgproc import load_image


def consecutive(data, mode: str = "first", stepsize: int = 1):
    group = np.split(data, np.where(np.diff(data) != stepsize)[0] + 1)
    group = [item for item in group if len(item) > 0]

    if mode == "first":
        result = [l[0] for l in group]
    elif mode == "last":
        result = [l[-1] for l in group]
    return result


def word_segmentation(
    mat,
    separator_idx={
        "th": [1, 2],
        "en": [3, 4]
    },
    separator_idx_list=[1, 2, 3, 4],
):
    result = []
    sep_list = []
    start_idx = 0
    sep_lang = ""
    for sep_idx in separator_idx_list:
        if sep_idx % 2 == 0:
            mode = "first"
        else:
            mode = "last"
        a = consecutive(np.argwhere(mat == sep_idx).flatten(), mode)
        new_sep = [[item, sep_idx] for item in a]
        sep_list += new_sep
    sep_list = sorted(sep_list, key=lambda x: x[0])

    for sep in sep_list:
        for lang in separator_idx.keys():
            if sep[1] == separator_idx[lang][0]:  # start lang
                sep_lang = lang
                sep_start_idx = sep[0]
            elif sep[1] == separator_idx[lang][1]:  # end lang
                if sep_lang == lang:  # check if last entry if the same start lang
                    new_sep_pair = [lang, [sep_start_idx + 1, sep[0] - 1]]
                    if sep_start_idx > start_idx:
                        result.append(["", [start_idx, sep_start_idx - 1]])
                    start_idx = sep[0] + 1
                    result.append(new_sep_pair)
                sep_lang = ""  # reset

    if start_idx <= len(mat) - 1:
        result.append(["", [start_idx, len(mat) - 1]])
    return result


# code is based from https://github.com/githubharald/CTCDecoder/blob/master/src/BeamSearch.py
class BeamEntry:
    "information about one single beam at specific time-step"

    def __init__(self):
        self.prTotal = 0  # blank and non-blank
        self.prNonBlank = 0  # non-blank
        self.prBlank = 0  # blank
        self.prText = 1  # LM score
        self.lmApplied = False  # flag if LM was already applied to this beam
        self.labeling = ()  # beam-labeling


class BeamState:
    "information about the beams at specific time-step"

    def __init__(self):
        self.entries = {}

    def norm(self):
        "length-normalise LM score"
        for (k, _) in self.entries.items():
            labelingLen = len(self.entries[k].labeling)
            self.entries[k].prText = self.entries[k].prText**(
                1.0 / (labelingLen if labelingLen else 1.0))

    def sort(self):
        "return beam-labelings, sorted by probability"
        beams = [v for (_, v) in self.entries.items()]
        sortedBeams = sorted(
            beams,
            reverse=True,
            key=lambda x: x.prTotal * x.prText,
        )
        return [x.labeling for x in sortedBeams]

    def wordsearch(self, classes, ignore_idx, maxCandidate, dict_list):
        beams = [v for (_, v) in self.entries.items()]
        sortedBeams = sorted(
            beams,
            reverse=True,
            key=lambda x: x.prTotal * x.prText,
        )
        if len(sortedBeams) > maxCandidate:
            sortedBeams = sortedBeams[:maxCandidate]

        for j, candidate in enumerate(sortedBeams):
            idx_list = candidate.labeling
            text = ""
            for i, l in enumerate(idx_list):
                if l not in ignore_idx and (
                        not (i > 0 and idx_list[i - 1] == idx_list[i])):
                    text += classes[l]

            if j == 0:
                best_text = text
            if text in dict_list:
                # print('found text: ', text)
                best_text = text
                break
            else:
                pass
                # print('not in dict: ', text)
        return best_text


def applyLM(parentBeam, childBeam, classes, lm_model, lm_factor: float = 0.01):
    "calculate LM score of child beam by taking score from parent beam and bigram probability of last two chars"
    if lm_model is not None and not childBeam.lmApplied:
        history = parentBeam.labeling
        history = " ".join(
            classes[each].replace(" ", "▁") for each in history if each != 0)

        current_char = classes[childBeam.labeling[-1]].replace(" ", "▁")
        if current_char == "[blank]":
            lmProb = 1
        else:
            text = history + " " + current_char
            lmProb = 10**lm_model.score(text, bos=True) * lm_factor

        childBeam.prText = lmProb  # probability of char sequence
        childBeam.lmApplied = True  # only apply LM once per beam entry


def simplify_label(labeling, blankIdx: int = 0):
    labeling = np.array(labeling)

    # collapse blank
    idx = np.where(~((np.roll(labeling, 1) == labeling) &
                     (labeling == blankIdx)))[0]
    labeling = labeling[idx]

    # get rid of blank between different characters
    idx = np.where(~((np.roll(labeling, 1) != np.roll(labeling, -1)) &
                     (labeling == blankIdx)))[0]

    if len(labeling) > 0:
        last_idx = len(labeling) - 1
        if last_idx not in idx:
            idx = np.append(idx, [last_idx])
    labeling = labeling[idx]

    return tuple(labeling)


def addBeam(beamState, labeling):
    "add beam if it does not yet exist"
    if labeling not in beamState.entries:
        beamState.entries[labeling] = BeamEntry()


def ctcBeamSearch(
    mat,
    classes: list,
    ignore_idx: int,
    lm_model,
    lm_factor: float = 0.01,
    beam_width: int = 5,
):
    blankIdx = 0
    maxT, maxC = mat.shape

    # initialise beam state
    last = BeamState()
    labeling = ()
    last.entries[labeling] = BeamEntry()
    last.entries[labeling].prBlank = 1
    last.entries[labeling].prTotal = 1

    # go over all time-steps
    for t in range(maxT):
        # print("t=", t)
        curr = BeamState()
        # get beam-labelings of best beams
        bestLabelings = last.sort()[0:beam_width]
        # go over best beams
        for labeling in bestLabelings:
            # print("labeling:", labeling)
            # probability of paths ending with a non-blank
            prNonBlank = 0
            # in case of non-empty beam
            if labeling:
                # probability of paths with repeated last char at the end
                prNonBlank = last.entries[labeling].prNonBlank * mat[
                    t, labeling[-1]]

            # probability of paths ending with a blank
            prBlank = (last.entries[labeling].prTotal) * mat[t, blankIdx]

            # add beam at current time-step if needed
            labeling = simplify_label(labeling, blankIdx)
            addBeam(curr, labeling)

            # fill in data
            curr.entries[labeling].labeling = labeling
            curr.entries[labeling].prNonBlank += prNonBlank
            curr.entries[labeling].prBlank += prBlank
            curr.entries[labeling].prTotal += prBlank + prNonBlank
            curr.entries[labeling].prText = last.entries[labeling].prText
            # beam-labeling not changed, therefore also LM score unchanged from

            curr.entries[labeling].lmApplied = (
                True  # LM already applied at previous time-step for this beam-labeling
            )

            # extend current beam-labeling
            # char_highscore = np.argpartition(mat[t, :], -5)[-5:] # run through 5 highest probability
            char_highscore = np.where(
                mat[t, :] >= 0.5 /
                maxC)[0]  # run through all probable characters
            for c in char_highscore:
                # for c in range(maxC - 1):
                # add new char to current beam-labeling
                newLabeling = labeling + (c,)
                newLabeling = simplify_label(newLabeling, blankIdx)

                # if new labeling contains duplicate char at the end, only consider paths ending with a blank
                if labeling and labeling[-1] == c:
                    prNonBlank = mat[t, c] * last.entries[labeling].prBlank
                else:
                    prNonBlank = mat[t, c] * last.entries[labeling].prTotal

                # add beam at current time-step if needed
                addBeam(curr, newLabeling)

                # fill in data
                curr.entries[newLabeling].labeling = newLabeling
                curr.entries[newLabeling].prNonBlank += prNonBlank
                curr.entries[newLabeling].prTotal += prNonBlank

                # apply LM
                applyLM(
                    curr.entries[labeling],
                    curr.entries[newLabeling],
                    classes,
                    lm_model,
                    lm_factor,
                )

        # set new beam state

        last = curr

    # normalise LM scores according to beam-labeling-length
    last.norm()

    bestLabeling = last.sort()[0]  # get most probable labeling
    res = ""
    for i, l in enumerate(bestLabeling):
        # removing repeated characters and blank.
        if l != ignore_idx and (not (i > 0 and
                                     bestLabeling[i - 1] == bestLabeling[i])):
            res += classes[l]

    return res


class CTCLabelConverter(object):
    """ Convert between text-label and text-index """

    def __init__(self, vocab: list):
        self.char2idx = {char: idx for idx, char in enumerate(vocab)}
        self.idx2char = {idx: char for idx, char in enumerate(vocab)}
        self.ignored_index = 0
        self.vocab = vocab

    def encode(self, texts: list):
        """
        Convert input texts into indices
        texts (list): text labels of each image. [batch_size]

        Returns
            text: concatenated text index for CTCLoss.
                    [sum(text_lengths)] = [text_index_0 + text_index_1 + ... + text_index_(n - 1)]
            length: length of each text. [batch_size]
        """
        lengths = [len(text) for text in texts]
        concatenated_text = "".join(texts)
        indices = [self.char2idx[char] for char in concatenated_text]

        return torch.IntTensor(indices), torch.IntTensor(lengths)

    def decode_greedy(self, indices: Tensor, lengths: Tensor):
        """convert text-index into text-label.

        :param indices (1D int32 Tensor): [N*length,]
        :param lengths (1D int32 Tensor): [N,]
        :return:
        """
        texts = []
        index = 0
        for length in lengths:
            text = indices[index:index + length]

            chars = []
            for i in range(length):
                if (text[i] != self.ignored_index) and (
                        not (i > 0 and text[i - 1] == text[i])
                ):  # removing repeated characters and blank (and separator).
                    chars.append(self.idx2char[text[i].item()])
            texts.append("".join(chars))
            index += length
        return texts

    def decode_beamsearch(self, mat, lm_model, lm_factor, beam_width: int = 5):
        texts = []
        for i in range(mat.shape[0]):
            text = ctcBeamSearch(
                mat[i],
                self.vocab,
                self.ignored_index,
                lm_model,
                lm_factor,
                beam_width,
            )
            texts.append(text)
        return texts


def four_point_transform(image, rect):
    (tl, tr, br, bl) = rect

    widthA = np.sqrt(((br[0] - bl[0])**2) + ((br[1] - bl[1])**2))
    widthB = np.sqrt(((tr[0] - tl[0])**2) + ((tr[1] - tl[1])**2))
    maxWidth = max(int(widthA), int(widthB))

    # compute the height of the new image, which will be the
    # maximum distance between the top-right and bottom-right
    # y-coordinates or the top-left and bottom-left y-coordinates
    heightA = np.sqrt(((tr[0] - br[0])**2) + ((tr[1] - br[1])**2))
    heightB = np.sqrt(((tl[0] - bl[0])**2) + ((tl[1] - bl[1])**2))
    maxHeight = max(int(heightA), int(heightB))

    dst = np.array(
        [[0, 0], [maxWidth - 1, 0], [maxWidth - 1, maxHeight - 1],
         [0, maxHeight - 1]],
        dtype="float32",
    )

    # compute the perspective transform matrix and then apply it
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))

    return warped


def group_text_box(
    polys,
    slope_ths: float = 0.1,
    ycenter_ths: float = 0.5,
    height_ths: float = 0.5,
    width_ths: float = 1.0,
    add_margin: float = 0.05,
):
    # poly top-left, top-right, low-right, low-left
    horizontal_list, free_list, combined_list, merged_list = [], [], [], []

    for poly in polys:
        slope_up = (poly[3] - poly[1]) / np.maximum(10, (poly[2] - poly[0]))
        slope_down = (poly[5] - poly[7]) / np.maximum(10, (poly[4] - poly[6]))
        if max(abs(slope_up), abs(slope_down)) < slope_ths:
            x_max = max([poly[0], poly[2], poly[4], poly[6]])
            x_min = min([poly[0], poly[2], poly[4], poly[6]])
            y_max = max([poly[1], poly[3], poly[5], poly[7]])
            y_min = min([poly[1], poly[3], poly[5], poly[7]])
            horizontal_list.append([
                x_min, x_max, y_min, y_max, 0.5 * (y_min + y_max), y_max - y_min
            ])
        else:
            height = np.linalg.norm([poly[6] - poly[0], poly[7] - poly[1]])
            margin = int(1.44 * add_margin * height)

            theta13 = abs(
                np.arctan(
                    (poly[1] - poly[5]) / np.maximum(10, (poly[0] - poly[4]))))
            theta24 = abs(
                np.arctan(
                    (poly[3] - poly[7]) / np.maximum(10, (poly[2] - poly[6]))))
            # do I need to clip minimum, maximum value here?
            x1 = poly[0] - np.cos(theta13) * margin
            y1 = poly[1] - np.sin(theta13) * margin
            x2 = poly[2] + np.cos(theta24) * margin
            y2 = poly[3] - np.sin(theta24) * margin
            x3 = poly[4] + np.cos(theta13) * margin
            y3 = poly[5] + np.sin(theta13) * margin
            x4 = poly[6] - np.cos(theta24) * margin
            y4 = poly[7] + np.sin(theta24) * margin

            free_list.append([[x1, y1], [x2, y2], [x3, y3], [x4, y4]])
    horizontal_list = sorted(horizontal_list, key=lambda item: item[4])

    # combine box
    new_box = []
    for poly in horizontal_list:

        if len(new_box) == 0:
            b_height = [poly[5]]
            b_ycenter = [poly[4]]
            new_box.append(poly)
        else:
            # comparable height and comparable y_center level up to ths*height
            if (abs(np.mean(b_height) - poly[5]) < height_ths *
                    np.mean(b_height)) and (abs(np.mean(b_ycenter) - poly[4]) <
                                            ycenter_ths * np.mean(b_height)):
                b_height.append(poly[5])
                b_ycenter.append(poly[4])
                new_box.append(poly)
            else:
                b_height = [poly[5]]
                b_ycenter = [poly[4]]
                combined_list.append(new_box)
                new_box = [poly]
    combined_list.append(new_box)

    # merge list use sort again
    for boxes in combined_list:
        if len(boxes) == 1:  # one box per line
            box = boxes[0]
            margin = int(add_margin * box[5])
            merged_list.append([
                box[0] - margin, box[1] + margin, box[2] - margin,
                box[3] + margin
            ])
        else:  # multiple boxes per line
            boxes = sorted(boxes, key=lambda item: item[0])

            merged_box, new_box = [], []
            for box in boxes:
                if len(new_box) == 0:
                    x_max = box[1]
                    new_box.append(box)
                else:
                    if abs(box[0] - x_max) < width_ths * (
                            box[3] - box[2]):  # merge boxes
                        x_max = box[1]
                        new_box.append(box)
                    else:
                        x_max = box[1]
                        merged_box.append(new_box)
                        new_box = [box]
            if len(new_box) > 0:
                merged_box.append(new_box)

            for mbox in merged_box:
                if len(mbox) != 1:  # adjacent box in same line
                    # do I need to add margin here?
                    x_min = min(mbox, key=lambda x: x[0])[0]
                    x_max = max(mbox, key=lambda x: x[1])[1]
                    y_min = min(mbox, key=lambda x: x[2])[2]
                    y_max = max(mbox, key=lambda x: x[3])[3]

                    margin = int(add_margin * (y_max - y_min))

                    merged_list.append([
                        x_min - margin, x_max + margin, y_min - margin,
                        y_max + margin
                    ])
                else:  # non adjacent box in same line
                    box = mbox[0]

                    margin = int(add_margin * (box[3] - box[2]))
                    merged_list.append([
                        box[0] - margin,
                        box[1] + margin,
                        box[2] - margin,
                        box[3] + margin,
                    ])
    # may need to check if box is really in image
    return merged_list, free_list


def get_image_list(horizontal_list: list,
                   free_list: list,
                   img: np.ndarray,
                   model_height: int = 64):
    image_list = []
    maximum_y, maximum_x = img.shape

    max_ratio_hori, max_ratio_free = 1, 1
    for box in free_list:
        rect = np.array(box, dtype="float32")
        transformed_img = four_point_transform(img, rect)
        ratio = transformed_img.shape[1] / transformed_img.shape[0]
        crop_img = cv2.resize(
            transformed_img,
            (int(model_height * ratio), model_height),
            interpolation=Image.LANCZOS,
        )
        # box : [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
        image_list.append((box, crop_img))
        max_ratio_free = max(ratio, max_ratio_free)

    max_ratio_free = math.ceil(max_ratio_free)

    for box in horizontal_list:
        x_min = max(0, box[0])
        x_max = min(box[1], maximum_x)
        y_min = max(0, box[2])
        y_max = min(box[3], maximum_y)
        crop_img = img[y_min:y_max, x_min:x_max]
        width = x_max - x_min
        height = y_max - y_min
        ratio = width / height
        crop_img = cv2.resize(
            crop_img,
            (int(model_height * ratio), model_height),
            interpolation=Image.LANCZOS,
        )
        image_list.append((
            [
                [x_min, y_min],
                [x_max, y_min],
                [x_max, y_max],
                [x_min, y_max],
            ],
            crop_img,
        ))
        max_ratio_hori = max(ratio, max_ratio_hori)

    max_ratio_hori = math.ceil(max_ratio_hori)
    max_ratio = max(max_ratio_hori, max_ratio_free)
    max_width = math.ceil(max_ratio) * model_height

    image_list = sorted(
        image_list, key=lambda item: item[0][0][1])  # sort by vertical position
    return image_list, max_width


def diff(input_list):
    return max(input_list) - min(input_list)


def get_paragraph(raw_result,
                  x_ths: int = 1,
                  y_ths: float = 0.5,
                  mode: str = "ltr"):
    # create basic attributes
    box_group = []
    for box in raw_result:
        all_x = [int(coord[0]) for coord in box[0]]
        all_y = [int(coord[1]) for coord in box[0]]
        min_x = min(all_x)
        max_x = max(all_x)
        min_y = min(all_y)
        max_y = max(all_y)
        height = max_y - min_y
        box_group.append([
            box[1], min_x, max_x, min_y, max_y, height, 0.5 * (min_y + max_y), 0
        ])  # last element indicates group
    # cluster boxes into paragraph
    current_group = 1
    while len([box for box in box_group if box[7] == 0]) > 0:
        # group0 = non-group
        box_group0 = [box for box in box_group if box[7] == 0]
        # new group
        if len([box for box in box_group if box[7] == current_group]) == 0:
            # assign first box to form new group
            box_group0[0][7] = current_group
        # try to add group
        else:
            current_box_group = [
                box for box in box_group if box[7] == current_group
            ]
            mean_height = np.mean([box[5] for box in current_box_group])
            # yapf: disable
            min_gx = min([box[1] for box in current_box_group]) - x_ths * mean_height
            max_gx = max([box[2] for box in current_box_group]) + x_ths * mean_height
            min_gy = min([box[3] for box in current_box_group]) - y_ths * mean_height
            max_gy = max([box[4] for box in current_box_group]) + y_ths * mean_height
            add_box = False
            for box in box_group0:
                same_horizontal_level = (min_gx <= box[1] <= max_gx) or (min_gx <= box[2] <= max_gx)
                same_vertical_level = (min_gy <= box[3] <= max_gy) or (min_gy <= box[4] <= max_gy)
                if same_horizontal_level and same_vertical_level:
                    box[7] = current_group
                    add_box = True
                    break
            # cannot add more box, go to next group
            if not add_box:
                current_group += 1
            # yapf: enable
    # arrage order in paragraph
    result = []
    for i in set(box[7] for box in box_group):
        current_box_group = [box for box in box_group if box[7] == i]
        mean_height = np.mean([box[5] for box in current_box_group])
        min_gx = min([box[1] for box in current_box_group])
        max_gx = max([box[2] for box in current_box_group])
        min_gy = min([box[3] for box in current_box_group])
        max_gy = max([box[4] for box in current_box_group])

        text = ""
        while len(current_box_group) > 0:
            highest = min([box[6] for box in current_box_group])
            candidates = [
                box for box in current_box_group
                if box[6] < highest + 0.4 * mean_height
            ]
            # get the far left
            if mode == "ltr":
                most_left = min([box[1] for box in candidates])
                for box in candidates:
                    if box[1] == most_left:
                        best_box = box
            elif mode == "rtl":
                most_right = max([box[2] for box in candidates])
                for box in candidates:
                    if box[2] == most_right:
                        best_box = box
            text += " " + best_box[0]
            current_box_group.remove(best_box)

        result.append([
            [
                [min_gx, min_gy],
                [max_gx, min_gy],
                [max_gx, max_gy],
                [min_gx, max_gy],
            ],
            text[1:],
        ])

    return result


def printProgressBar(
    prefix="",
    suffix="",
    decimals: int = 1,
    length: int = 100,
    fill: str = "█",
    printEnd: str = "\r",
):
    """
    Call in a loop to create terminal progress bar
    @params:
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
    """

    def progress_hook(count, blockSize, totalSize):
        progress = count * blockSize / totalSize
        percent = ("{0:." + str(decimals) + "f}").format(progress * 100)
        filledLength = int(length * progress)
        bar = fill * filledLength + "-" * (length - filledLength)
        print(f"\r{prefix} |{bar}| {percent}% {suffix}", end=printEnd)

    return progress_hook


def reformat_input(image):
    """
    :param image: image file path or bytes or array
    :return:
        img (array): (original_image_height, original_image_width, 3)
        img_cv_grey (array): (original_image_height, original_image_width, 3)
    """
    if type(image) == str:
        if image.startswith("http://") or image.startswith("https://"):
            tmp, _ = urlretrieve(
                image,
                reporthook=printProgressBar(
                    prefix="Progress:",
                    suffix="Complete",
                    length=50,
                ),
            )
            img_cv_grey = cv2.imread(tmp, cv2.IMREAD_GRAYSCALE)
            os.remove(tmp)
        else:
            img_cv_grey = cv2.imread(image, cv2.IMREAD_GRAYSCALE)
            image = os.path.expanduser(image)
        img = load_image(image)  # can accept URL
    elif type(image) == bytes:
        nparr = np.frombuffer(image, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_cv_grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    elif type(image) == np.ndarray:
        if len(image.shape) == 2:  # grayscale
            img_cv_grey = image
            img = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        elif len(image.shape) == 3 and image.shape[2] == 3:  # BGRscale
            img = image
            img_cv_grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        elif len(image.shape) == 3 and image.shape[2] == 4:  # RGBAscale
            img = image[:, :, :3]
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            img_cv_grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    return img, img_cv_grey
