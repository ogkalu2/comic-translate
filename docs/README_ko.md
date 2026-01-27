# 만화 번역
[English](../README.md) | 한국어 | [Français](README_fr.md) | [简体中文](README_zh-CN.md)

<img src="https://i.imgur.com/QUVK6mK.png">

## 소개
자동 만화 번역기는 많이 존재합니다. 하지만 다른 언어로 된 다양한 종류의 만화를 제대로 지원하는 번역기는 거의 없습니다.
이 프로젝트는 GPT와 같은 최신(SOTA) 대규모 언어 모델(LLM)의 능력을 활용하여 전 세계의 만화를 번역하기 위해 만들어졌습니다.

현재 영어, 한국어, 일본어, 프랑스어, 중국어 간체, 중국어 번체, 러시아어, 독일어, 네덜란드어, 스페인어, 이탈리아어 만화의 번역을 지원합니다. 위에서 언급한 언어들을 포함하여 더 많은 언어로 번역할 수 있습니다.

- [기계 번역의 현황](#기계-번역의-현황)
- [미리보기](#만화-샘플)
- [시작하기](#설치)
    - [설치](#설치)
        - [다운로드](#다운로드)
        - [소스 코드에서 설치](#소스-코드에서-설치)
    - [사용법](#사용법)
        - [팁](#팁)

- [작동 방식](#작동-방식)
    - [텍스트 감지](#텍스트-감지)
    - [OCR](#OCR)
    - [이미지 복원](#이미지-복원)
    - [번역](#번역)
    - [텍스트 렌더링](#텍스트-렌더링)

- [감사의 말](#감사의-말)

## 기계 번역의 현황
수십 개의 언어에 대해 최고의 기계 번역기는 구글 번역도, 파파고도, 심지어 DeepL도 아닌 SOTA LLM인 GPT-4이며, 그 차이는 압도적입니다.
이는 한국어<->영어, 일본어<->영어 등과 같이 언어적 거리가 먼 경우에 더욱 분명하게 드러나는데, 다른 번역기들은 여전히 종종 무의미한 결과물을 내놓곤 합니다.

## 만화 샘플
GPT-4를 번역기로 사용.
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
### 다운로드
Windows 및 macOS용 Comic Translate를 [여기](https://www.comic-translate.com/download/). 
> 참고: GPU 가속은 현재 소스 코드에서 실행할 때만 사용할 수 있습니다.

### 소스 코드에서 설치
또는 소스 코드를 직접 실행하고 싶다면 다음과 같이 하세요.

Python 3.12를 설치합니다. 설치 중에 "Add python.exe to PATH"를 체크하세요.
```bash
https://www.python.org/downloads/
```
Git 설치
```bash
https://git-scm.com/
```
uv 설치
```
https://docs.astral.sh/uv/getting-started/installation/
```

그 후, 명령 프롬프트에서 다음을 실행합니다.
```bash
git clone https://github.com/ogkalu2/comic-translate
cd comic-translate
uv init --python 3.12
```
그리고 요구 사항을 설치합니다.
```bash
uv add -r requirements.txt --compile-bytecode
```

업데이트하려면 comic-translate 폴더에서 다음을 실행하세요.
```bash
git pull
uv init --python 3.12 (참고: 처음 설치할 때 uv를 사용하지 않았다면 이 줄만 실행하세요)
uv add -r requirements.txt --compile-bytecode
```

NVIDIA GPU가 있는 경우 다음을 실행하는 것이 좋습니다.
```bash
uv pip install onnxruntime-gpu
```

## 사용법
comic-translate 디렉토리에서 다음을 실행하세요.
```bash
uv run comic.py
```
이렇게 하면 GUI가 실행됩니다.

### 팁
* CBR 파일이 있는 경우 Winrar 또는 7-Zip을 설치한 다음 설치된 폴더(예: Windows의 경우 "C:\Program Files\WinRAR")를 Path에 추가해야 합니다. 설치되었지만 Path에 없으면 다음과 같은 오류가 발생할 수 있습니다.
```bash
raise RarCannotExec("Cannot find working tool")
```
이 경우 [Windows](https://www.windowsdigitals.com/add-folder-to-path-environment-variable-in-windows-11-10/), [Linux](https://linuxize.com/post/how-to-add-directory-to-path-in-linux/), [Mac](https://techpp.com/2021/09/08/set-path-variable-in-macos-guide/)용 지침을 따르세요.

* 선택한 글꼴이 대상 언어의 문자를 지원하는지 확인하세요.
* v2.0에는 수동 모드가 도입되었습니다. 자동 모드에서 문제가 발생할 경우(텍스트 감지 실패, 잘못된 OCR, 불충분한 클리닝 등) 이제 수정할 수 있습니다. 이미지를 실행 취소하고 수동 모드로 전환하기만 하면 됩니다.
* 자동 모드에서는 이미지가 처리되면 뷰어에 로드되거나 전환 시 로드되도록 저장되므로 다른 이미지가 번역되는 동안 앱에서 계속 읽을 수 있습니다.
* Ctrl + 마우스 휠로 확대/축소, 그렇지 않으면 수직 스크롤입니다.
* 이미지 보기에는 일반적인 트랙패드 제스처가 작동합니다.
* 오른쪽, 왼쪽 키로 이미지 간 이동이 가능합니다.

## 작동 방식
### 말풍선 감지 및 텍스트 분할
[bubble-and-text-detector](https://huggingface.co/ogkalu/comic-text-and-bubble-detector). 11,000장의 만화(망가, 웹툰, 서양 만화) 이미지로 훈련된 RT-DETR-v2 모델입니다.
감지 모델에서 제공된 상자를 기반으로 한 알고리즘 분할을 사용합니다.

<img src="https://i.imgur.com/TlzVH3j.jpg" width="49%"> <img src="https://i.imgur.com/h18XrYT.jpg" width="49%"> 

### OCR
기본값:
* 일본어는 [manga-ocr](https://github.com/kha-white/manga-ocr)
* 한국어는 [Pororo](https://github.com/yunwoong7/korean_ocr_using_pororo)
* 그 외 모든 언어는 [PPOCRv5](https://www.paddleocr.ai/main/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5.html)

선택 사항:

지원되는 모든 언어에 사용할 수 있습니다.

* Gemini 2.0 Flash
* Microsoft Azure Vision

### 이미지 복원
분할된 텍스트를 제거하기 위해
* [망가/애니메이션 미세 조정](https://huggingface.co/dreMaz/AnimeMangaInpainting)된 [lama](https://github.com/advimman/lama) 체크포인트. 구현은 [lama-cleaner](https://github.com/Sanster/lama-cleaner) 덕분입니다.
* [zyddnys](https://github.com/zyddnys)의 [AOT-GAN](https://arxiv.org/abs/2104.01431) 기반 모델

<img src="https://i.imgur.com/cVVGVXp.jpg" width="49%"> <img src="https://i.imgur.com/bLkPyqG.jpg" width="49%">

### 번역
현재 GPT-4.1, Claude-4.5,
Gemini-2.5를 지원합니다.

모든 LLM은 번역을 돕기 위해 전체 페이지 텍스트를 입력받습니다.
추가적인 맥락을 위해 이미지 자체를 제공하는 옵션도 있습니다.

### 텍스트 렌더링
말풍선과 텍스트에서 얻은 경계 상자에 텍스트를 줄바꿈하여 넣습니다.

## 감사의 말

* [https://github.com/Sanster/lama-cleaner](https://github.com/Sanster/lama-cleaner)
* [https://huggingface.co/dreMaz](https://huggingface.co/dreMaz)
* [https://github.com/yunwoong7/korean_ocr_using_pororo](https://github.com/yunwoong7/korean_ocr_using_pororo)
* [https://github.com/kha-white/manga-ocr](https://github.com/kha-white/manga-ocr)
* [https://github.com/JaidedAI/EasyOCR](https://github.com/JaidedAI/EasyOCR)
* [https://github.com/PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
* [https://github.com/RapidAI/RapidOCR](https://github.com/RapidAI/RapidOCR)
* [https://github.com/phenom-films/dayu_widgets](https://github.com/phenom-films/dayu_widgets)
