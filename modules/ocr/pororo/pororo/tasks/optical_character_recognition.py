"""OCR related modeling class"""

from typing import Optional

from ...pororo.tasks import download_or_load
from ...pororo.tasks.utils.base import PororoFactoryBase, PororoSimpleBase


class PororoOcrFactory(PororoFactoryBase):
    """
    Recognize optical characters in image file
    Currently support Korean language

    English + Korean (`brainocr`)

        - dataset: Internal data + AI hub Font Image dataset
        - metric: TBU
        - ref: https://www.aihub.or.kr/aidata/133

    Examples:
        >>> ocr = Pororo(task="ocr", lang="ko")
        >>> ocr(IMAGE_PATH)
        ["사이렌'(' 신마'", "내가 말했잖아 속지열라고 이 손을 잡는 너는 위협해질 거라고"]

        >>> ocr = Pororo(task="ocr", lang="ko")
        >>> ocr(IMAGE_PATH, detail=True)
        {
            'description': ["사이렌'(' 신마', "내가 말했잖아 속지열라고 이 손을 잡는 너는 위협해질 거라고"],
            'bounding_poly': [
                {
                    'description': "사이렌'(' 신마'",
                    'vertices': [
                        {'x': 93, 'y': 7},
                        {'x': 164, 'y': 7},
                        {'x': 164, 'y': 21},
                        {'x': 93, 'y': 21}
                    ]
                },
                {
                    'description': "내가 말했잖아 속지열라고 이 손을 잡는 너는 위협해질 거라고",
                    'vertices': [
                        {'x': 0, 'y': 30},
                        {'x': 259, 'y': 30},
                        {'x': 259, 'y': 194},
                        {'x': 0, 'y': 194}]}
                    ]
                }
        }
    """

    def __init__(self, task: str, lang: str, model: Optional[str]):
        super().__init__(task, lang, model)
        self.detect_model = "craft"
        self.ocr_opt = "ocr-opt"

    @staticmethod
    def get_available_langs():
        return ["en", "ko"]

    @staticmethod
    def get_available_models():
        return {
            "en": ["brainocr"],
            "ko": ["brainocr"],
        }

    def load(self, device: str):
        """
        Load user-selected task-specific model

        Args:
            device (str): device information

        Returns:
            object: User-selected task-specific model

        """
        if self.config.n_model == "brainocr":
            from ...pororo.models.brainOCR import brainocr

            if self.config.lang not in self.get_available_langs():
                raise ValueError(
                    f"Unsupported Language : {self.config.lang}",
                    'Support Languages : ["en", "ko"]',
                )

            det_model_path = download_or_load(
                f"{self.detect_model}.pt",
                self.config.lang,
            )
            rec_model_path = download_or_load(
                f"{self.config.n_model}.pt",
                self.config.lang,
            )
            opt_fp = download_or_load(
                f"{self.ocr_opt}.txt",
                self.config.lang,
            )
            model = brainocr.Reader(
                self.config.lang,
                det_model_ckpt_fp=det_model_path,
                rec_model_ckpt_fp=rec_model_path,
                opt_fp=opt_fp,
                device=device,
            )
            model.detector.to(device)
            model.recognizer.to(device)
            return PororoOCR(model, self.config)


class PororoOCR(PororoSimpleBase):

    def __init__(self, model, config):
        super().__init__(config)
        self._model = model

    def _postprocess(self, ocr_results, detail: bool = False):
        """
        Post-process for OCR result

        Args:
            ocr_results (list): list contains result of OCR
            detail (bool): if True, returned to include details. (bounding poly, vertices, etc)

        """
        sorted_ocr_results = sorted(
            ocr_results,
            key=lambda x: (
                x[0][0][1],
                x[0][0][0],
            ),
        )

        if not detail:
            return [
                sorted_ocr_results[i][-1]
                for i in range(len(sorted_ocr_results))
            ]

        result_dict = {
            "description": list(),
            "bounding_poly": list(),
        }

        for ocr_result in sorted_ocr_results:
            vertices = list()

            for vertice in ocr_result[0]:
                vertices.append({
                    "x": vertice[0],
                    "y": vertice[1],
                })

            result_dict["description"].append(ocr_result[1])
            result_dict["bounding_poly"].append({
                "description": ocr_result[1],
                "vertices": vertices
            })

        return result_dict

    def predict(self, image_path: str, **kwargs):
        """
        Conduct Optical Character Recognition (OCR)

        Args:
            image_path (str): the image file path
            detail (bool): if True, returned to include details. (bounding poly, vertices, etc)

        """
        detail = kwargs.get("detail", False)

        return self._postprocess(
            self._model(
                image_path,
                skip_details=False,
                batch_size=1,
                paragraph=True,
            ),
            detail,
        )
