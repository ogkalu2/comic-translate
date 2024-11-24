import cv2
from .pororo import Pororo
from .pororo.pororo import SUPPORTED_TASKS
#from .utils.image_util import plt_imshow, put_text
import warnings

warnings.filterwarnings('ignore')


class PororoOcr:
    def __init__(self, model: str = "brainocr", lang: str = "ko", **kwargs):
        self.model = model
        self.lang = lang
        self._ocr = Pororo(task="ocr", lang=lang, model=model, **kwargs)
        self.img_path = None
        self.ocr_result = {}

    def run_ocr(self, img_path: str, debug: bool = False):
        self.img_path = img_path
        self.ocr_result = self._ocr(img_path, detail=True)

        if self.ocr_result['description']:
            ocr_text = self.ocr_result["description"]
        else:
            ocr_text = "No text detected."

        if debug:
            self.show_img_with_ocr()

        return ocr_text

    @staticmethod
    def get_available_langs():
        return SUPPORTED_TASKS["ocr"].get_available_langs()

    @staticmethod
    def get_available_models():
        return SUPPORTED_TASKS["ocr"].get_available_models()

    def get_ocr_result(self):
        return self.ocr_result

    def get_img_path(self):
        return self.img_path

    # def show_img(self):
    #     plt_imshow(img=self.img_path)

    # def show_img_with_ocr(self):
    #     if isinstance(self.img_path, str):
    #         img = cv2.imread(self.img_path)
    #     else:
    #         img = self.img_path
    #     roi_img = img.copy()

    #     for text_result in self.ocr_result['bounding_poly']:
    #         text = text_result['description']
    #         tlX = text_result['vertices'][0]['x']
    #         tlY = text_result['vertices'][0]['y']
    #         trX = text_result['vertices'][1]['x']
    #         trY = text_result['vertices'][1]['y']
    #         brX = text_result['vertices'][2]['x']
    #         brY = text_result['vertices'][2]['y']
    #         blX = text_result['vertices'][3]['x']
    #         blY = text_result['vertices'][3]['y']

    #         pts = ((tlX, tlY), (trX, trY), (brX, brY), (blX, blY))

    #         topLeft = pts[0]
    #         topRight = pts[1]
    #         bottomRight = pts[2]
    #         bottomLeft = pts[3]

    #         cv2.line(roi_img, topLeft, topRight, (0, 255, 0), 2)
    #         cv2.line(roi_img, topRight, bottomRight, (0, 255, 0), 2)
    #         cv2.line(roi_img, bottomRight, bottomLeft, (0, 255, 0), 2)
    #         cv2.line(roi_img, bottomLeft, topLeft, (0, 255, 0), 2)
    #         roi_img = put_text(roi_img, text, topLeft[0], topLeft[1] - 20, font_size=15)

    #         # print(text)

    #     plt_imshow(["Original", "ROI"], [img, roi_img], figsize=(16, 10))


if __name__ == "__main__":
    ocr = PororoOcr()
    image_path = input("Enter image path: ")
    text = ocr.run_ocr(image_path, debug=True)
    print('Result :', text)
