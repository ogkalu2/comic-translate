# 만화 번역

https://github.com/ogkalu2/comic-translate/assets/115248977/afb01782-71a7-4bb7-9869-4f45da5a7bb5

## 소개
자동 만화 번역기가 많이 있습니다. 하지만 다른 언어로 된 여러 종류의 코믹스를 제대로 지원하는 번역기는 많지 않습니다.
이 프로젝트는 전 세계의 코믹스를 번역하기 위해 GPT-4의 능력을 활용하여 만들어졌습니다. 현재 영어, 한국어, 일본어, 프랑스어, 간체 중국어, 번체 중국어, 러시아어, 독일어, 네덜란드어, 스페인어 및 이탈리아어로 번역을 지원합니다.

- [기계 번역의 현황](#기계-번역의-현황)
- [미리보기](#만화-샘플)
- [시작하기](#설치)
    - [설치](#설치)
        - [파이썬](#파이썬)
    - [사용법](#사용법)
        - [팁](#팁)
    - [API 키](#api-키)
        - [API 키 받기](#api-키-받기)
            - [Open AI](#open-ai-gpt)
            - [Google Cloud Vision](#google-cloud-vision)

- [작동 방식](#작동-방식)
    - [텍스트 감지](#텍스트-감지)
    - [OCR](#OCR)
    - [이미지 복원](#이미지-복원)
    - [번역](#번역)
    - [텍스트 렌더링](#텍스트-렌더링)

- [감사의 말](#감사의-말)

## 기계 번역의 현황
수십 개 언어에 대해 최고의 기계 번역기는 Google 번역도, 파파고도 아닌 GPT-4이고, 그것도 압도적으로 그렇습니다.
특히 한국어<->영어, 일본어<->영어와 같이 거리가 먼 언어 조합에서 기타 번역기들은 여전히 종종 터무니없는 말로 변하곤 합니다.

## 만화 샘플
번역기로서의 GPT-4-Vision.
참고: 이 중 일부는 공식 한국어 번역도 있습니다.

[바다의 불쌍한 사람들](https://www.drakoo.fr/bd/drakoo/les_damnes_du_grand_large/les_damnes_du_grand_large_-_histoire_complete/9782382330128)

<img src="https://i.imgur.com/75HwK4r.jpg" width="49%"> <img src="https://i.imgur.com/pUFKR5G.jpg" width="49%">

[서유기](https://ac.qq.com/Comic/comicInfo/id/541812)

<img src="https://i.imgur.com/zk7yiKe.jpg" width="49%"> <img src="https://i.imgur.com/A88mVJQ.jpg" width="49%">

[웜월드 사가](https://wormworldsaga.com/index.php)

<img src="https://i.imgur.com/cVVGVXp.jpg" width="49%"> <img src="https://i.imgur.com/KoRSvCv.jpg" width="49%">

[여행의 끝, 프리어렌](https://renta.papy.co.jp/renta/sc/frm/item/220775/title/742932/)

<img src="https://i.imgur.com/ANGHVhG.png" width="49%"> <img src="https://i.imgur.com/EijNCkq.png" width="49%">

[모래의 날들](https://9ekunst.nl/2021/05/20/nieuw-album-van-aimee-de-jongh-is-benauwend-als-een-zandstorm/)

<img src="https://i.imgur.com/m7PDiXN.jpg" width="49%"> <img src="https://i.imgur.com/OW41EOp.jpg" width="49%">

[탄소와 실리콘](https://www.amazon.com/Carbone-Silicium-French-Mathieu-Bablet-ebook/dp/B0C1LTGZ85/)

<img src="https://i.imgur.com/h51XJx4.jpg" width="49%"> <img src="https://i.imgur.com/AUZSdMs.jpg" width="49%">

## 설치
### 파이써
파이썬 설치 (<=3.10). 설치 중에 'python.exe를 PATH에 추가'를 선택하세요.
```bash
https://www.python.org/downloads/
```
현재 파이썬 3.11 이상에서는 PaddleOCR과 호환되지 않는 문제로 완전하게 작동하지 않습니다. 중국어를 기본 옵션(Paddle)으로 번역할 계획이 없다면, requirements.txt 파일에서
```bash
paddleocr==2.7.0.3
paddlepaddle==2.5.2
```
을
```bash
PyMuPDF==1.23.8
```
로 바꿔서 파이썬 3.11에서 사용할 수 있습니다.

레포(repo)를 클론하거나 폴더를 다운로드하고, 폴더로 이동합니다.
```bash
git clone https://github.com/ogkalu2/comic-translate
cd comic-translate
```
그리고 요구 사항을 설치합니다.
```bash
pip install -r requirements.txt
```

## 사용법
comic-translate 디렉토리에서 다음을 실행합니다.
```bash
python comic.py
```
이렇게 하면 GUI가 실행됩니다.

### 팁
* Import > 이미지를 선택하면 단일 이미지나 여러 이미지를 선택할 수 있습니다. CBR 파일이 있다면, Winrar나 7-Zip을 설치하고 설치된 폴더(e.g "C:\Program Files\WinRAR" for Windows)를 Path에 추가해야 합니다. 설치는 했지만 Path에 추가하지 않으면, 다음과 같은 에러가 발생할 수 있습니다.
```bash
raise RarCannotExec("Cannot find working tool")
```
이 경우 지시사항을 따라 [Windows](https://www.windowsdigitals.com/add-folder-to-path-environment-variable-in-windows-11-10/), [Linux](https://linuxize.com/post/how-to-add-directory-to-path-in-linux/), [Mac](https://techpp.com/2021/09/08/set-path-variable-in-macos-guide/)

* 설정 > 텍스트 렌더링 > 텍스트블록 조정으로 이동하여 렌더링에 사용되는 블록의 크기를 조정합니다. 텍스트가 너무 크게/작게 렌더링되는 상황을 위한 것입니다.
이는 페이지상의 모든 감지된 블록에 적용됩니다.
* 선택한 글꼴이 대상 언어의 문자를 지원하는지 확인하십시오. 

## API 키
다음 선택사항에는 폐쇄된 리소스에 대한 접근과, 이에 따른 API 키가 필요합니다:
* 번역을 위한 GPT-4-Vision, 4 또는 3.5 (유료, 4-Turbo에 대해 페이지당 약 $0.02 USD)
* DeepL 번역기 (월 500,000자까지 무료)
* OCR을 위한 GPT-4-Vision (프랑스어, 러시아어, 독일어, 네덜란드어, 스페인어, 이탈리아어를 충분히 인식할 경우 기본 옵션) (유료, 페이지당 약 $0.04 USD)
* OCR을 위한 Microsoft Azure Vision (월 5000 이미지까지 무료)
* OCR을 위한 Google Cloud Vision (월 1000 이미지까지 무료).
API 키를 설정하려면 설정 > 자격 증명 설정으로 이동하세요.

### API 키 받기
#### Open AI (GPT)
* OpenAI의 플랫폼 웹사이트 [platform.openai.com](https://platform.openai.com/)에 접속하여 OpenAI 계정으로 로그인하거나 계정을 생성합니다.
* 페이지의 오른쪽 태스크바에 마우스를 올리고 "API 키"를 선택합니다.
* "새 비밀 키 생성"을 클릭하여 새 API 키를 생성하고 복사해 보관하세요.

#### Google Cloud Vision 
* [Google Cloud](https://cloud.google.com/) 계정에 로그인/계정을 생성합니다. [Cloud Resource Manager](https://console.cloud.google.com/cloud-resource-manager)로 이동하여 "프로젝트 생성"을 클릭합니다. 프로젝트 이름을 설정합니다.
* [여기](https://console.cloud.google.com/welcome)에서 프로젝트를 선택한 다음 "결제"를 선택하고 "계정 생성"을 클릭합니다. 팝업에서 "결제 계정 활성화"를 선택하고 무료 체험 계정의 제안을 수락합니다. "계정 유형"은 개인이어야 합니다. 유효한 신용카드 정보를 입력하세요.
* [여기](https://console.cloud.google.com/apis/library/vision.googleapis.com)에서 프로젝트의 Google Cloud Vison을 활성화하세요.
* [Google Cloud 자격 증명](https://console.cloud.google.com/apis/credentials) 페이지에서 "자격 증명 생성"을 클릭한 다음 API 키를 선택합니다. 키를 복사해 보관하세요.

## 작동 방식
### 말풍선 감지 및 텍스트 분할
[speech-bubble-detector](https://huggingface.co/ogkalu/comic-speech-bubble-detector-yolov8m), [text-segmenter](https://huggingface.co/ogkalu/comic-text-segmenter-yolov8m). 각각 만화(만화, 웹툰, 서양 만화) 8천 개, 3천 개 이미지로 훈련된 두 개의 yolov8m 모델입니다.

### OCR
기본 설정으로:
* [EasyOCR](https://github.com/JaidedAI/EasyOCR) 영어용
* [manga-ocr](https://github.com/kha-white/manga-ocr) 일본어용
* [Pororo](https://github.com/yunwoong7/korean_ocr_using_pororo) 한국어용 
* [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) 중국어용 
* [GPT-4-Vision](https://platform.openai.com/docs/guides/vision) 프랑스어, 러시아어, 독일어, 네덜란드어, 스페인어, 이탈리아어용. 유료로 API 키가 필요합니다.

선택적으로:

이들은 지원되는 모든 언어에 사용할 수 있습니다. API 키가 필요합니다.

* [Google Cloud Vision](https://cloud.google.com/vision/docs/ocr)
* [Microsoft Azure Vision](https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/overview-ocr)

### 이미지 복원
분할기에 의해 감지된 텍스트를 제거하기 위해 [lama](https://github.com/advimman/lama) 체크포인트를 사용한 [망가/애니메이션 미세조정](https://huggingface.co/dreMaz/AnimeMangaInpainting) 입니다. [lama-cleaner](https://github.com/Sanster/lama-cleaner)의 구현에 감사드립니다.

### 번역
현재 GPT-4-Vision, GPT-4, GPT-3.5, DeepL, Google 번역을 사용할 수 있습니다.
모든 GPT 모델은 번역을 돕기 위해 해당 페이지 전체 텍스트의 맥락을 입력받습니다.
특히 GPT-4-Vision은 해당 언어를 능숙하게 인식하는 경우(프랑스어, 러시아어, 독일어, 네덜란드어, 스페인어, 이탈리아어) 원본 텍스트와 함께 페이지 이미지, 복원된 이미지도 제공받습니다.

### 텍스트 렌더링
말풍선 및 텍스트에서 얻은 경계 상자 내에 텍스트를 렌더링하는 PIL입니다.

## 감사의 글

* [https://github.com/hoffstadt/DearPyGui](https://github.com/hoffstadt/DearPyGui)
* [https://github.com/ultralytics/ultralytics](https://github.com/ultralytics/ultralytics)
* [https://github.com/Sanster/lama-cleaner](https://github.com/Sanster/lama-cleaner)
* [https://huggingface.co/dreMaz](https://huggingface.co/dreMaz)
* [https://github.com/yunwoong7/korean_ocr_using_pororo](https://github.com/yunwoong7/korean_ocr_using_pororo)
* [https://github.com/kha-white/manga-ocr](https://github.com/kha-white/manga-ocr)
* [https://github.com/JaidedAI/EasyOCR](https://github.com/JaidedAI/EasyOCR)
* [https://github.com/PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
