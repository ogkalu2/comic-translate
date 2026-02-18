# Comic Translate
English | [한국어](docs/README_ko.md) | [Français](docs/README_fr.md) | [简体中文](docs/README_zh-CN.md)

<img src="https://i.imgur.com/QUVK6mK.png">

## Intro
Many Automatic Manga Translators exist. Very few properly support comics of other kinds in other languages. 
This project was created to utilize the ability of State of the Art (SOTA) Large Language Models (LLMs) like GPT and translate comics from all over the world. 

Currently, it supports translating comics from the following languages: English, Korean, Japanese, French, Simplified Chinese, Traditional Chinese, Russian, German, Dutch, Spanish and Italian. It can translate to the above mentioned and more. 

- [The State of Machine Translation](#the-state-of-machine-translation)
- [Preview](#comic-samples)
- [Getting Started](#installation)
    - [Installation](#installation)
        - [Download](#download)
        - [From Source](#from-source)
    - [Usage](#usage)
        - [Tips](#tips)

- [How it works](#how-it-works)
    - [Text Detection](#text-detection)
    - [OCR](#OCR)
    - [Inpainting](#inpainting)
    - [Translation](#translation)
    - [Text Rendering](#text-rendering)

- [Acknowledgements](#acknowledgements)

## The State of Machine Translation
For a couple dozen languages, the best Machine Translator is not Google Translate, Papago or even DeepL, but a SOTA LLM like GPT-4, and by far. 
This is very apparent for distant language pairs (Korean<->English, Japanese<->English etc) where other translators still often devolve into gibberish.
Excerpt from "The Walking Practice"(보행 연습) by Dolki Min(돌기민)
![Model](https://i.imgur.com/72jvLBa.png)

## Comic Samples
GPT-4 as Translator.
Note: Some of these also have Official English Translations

[The Wretched of the High Seas](https://www.drakoo.fr/bd/drakoo/les_damnes_du_grand_large/les_damnes_du_grand_large_-_histoire_complete/9782382330128)

<img src="https://i.imgur.com/75HwK4r.jpg" width="49%"> <img src="https://i.imgur.com/3oRt5fX.jpg" width="49%">

[Journey to the West](https://ac.qq.com/Comic/comicInfo/id/541812)

<img src="https://i.imgur.com/zk7yiKe.jpg" width="49%"> <img src="https://i.imgur.com/4ycSi8j.jpg" width="49%">

[The Wormworld Saga](https://wormworldsaga.com/index.php)

<img src="https://i.imgur.com/cVVGVXp.jpg" width="49%"> <img src="https://i.imgur.com/SSl81sb.jpg" width="49%">

[Frieren: Beyond Journey's End](https://renta.papy.co.jp/renta/sc/frm/item/220775/title/742932/)

<img src="https://i.imgur.com/ANGHVhG.png" width="49%"> <img src="https://i.imgur.com/r5YOE26.png" width="49%">

[Days of Sand](https://9ekunst.nl/2021/05/20/nieuw-album-van-aimee-de-jongh-is-benauwend-als-een-zandstorm/)

<img src="https://i.imgur.com/m7PDiXN.jpg" width="49%"> <img src="https://i.imgur.com/eUwTGnn.jpg" width="49%">

[Player (OH Hyeon-Jun)](https://comic.naver.com/webtoon/list?titleId=745876&page=1&sort=ASC&tab=fri)

<img src="https://i.imgur.com/KGwiHJh.jpg" width="49%"> <img src="https://i.imgur.com/B8RMbRQ.jpg" width="49%">

[Carbon & Silicon](https://www.amazon.com/Carbone-Silicium-French-Mathieu-Bablet-ebook/dp/B0C1LTGZ85/)

<img src="https://i.imgur.com/h51XJx4.jpg" width="49%"> <img src="https://i.imgur.com/sLitjUY.jpg" width="49%">

## Installation
### Download
Download and install Comic Translate for Windows and macOS from [here](https://www.comic-translate.com). 

>Ignore Smart Screen for Windows (Click More info > Run anyway). For macOS, after trying to open, go to Settings > Privacy and Security > Scroll down and click Open Anyway. 

> Note: GPU acceleration is currently only available when running from source.

### From Source
Alternatively, if you'd like to run the source code directly.

Install Python 3.12. Tick "Add python.exe to PATH" during the setup.
```bash
https://www.python.org/downloads/
```
Install git
```bash
https://git-scm.com/
```
Install uv
```
https://docs.astral.sh/uv/getting-started/installation/
```

Then, in the command line
```bash
git clone https://github.com/ogkalu2/comic-translate
cd comic-translate
uv init --python 3.12
```
and install the requirements
```bash
uv add -r requirements.txt --compile-bytecode
```

To Update, run this in the comic-translate folder
```bash
git pull
uv init --python 3.12 (Note: only run this line if you did not use uv for the first time installation)
uv add -r requirements.txt --compile-bytecode
```

If you have an NVIDIA GPU, then it is recommended to run
```bash
uv pip install onnxruntime-gpu
```

## Usage
In the comic-translate directory, run
```bash
uv run comic.py
```
This will launch the GUI

### Local Translation (Ollama)
If you want free, local translation without paid API credits, you can use Ollama.

1) Install Ollama
```bash
https://ollama.com/download
```

2) Download a model (recommended)
```bash
ollama pull gemma2:9b
```

3) Configure in the app
- Settings > Credentials > Ollama
    - Model: gemma2:9b
    - API URL: http://localhost:11434/v1
- Settings > Tools > Translator: Ollama
### Tips
* If you have a CBR file, you'll need to install Winrar or 7-Zip then add the folder it's installed to (e.g "C:\Program Files\WinRAR" for Windows) to Path. If it's installed but not to Path, you may get the error, 
```bash
raise RarCannotExec("Cannot find working tool")
```
In that case, Instructions for [Windows](https://www.windowsdigitals.com/add-folder-to-path-environment-variable-in-windows-11-10/), [Linux](https://linuxize.com/post/how-to-add-directory-to-path-in-linux/), [Mac](https://techpp.com/2021/09/08/set-path-variable-in-macos-guide/)

* Make sure the selected Font supports characters of the target language
* v2.0 introduces a Manual Mode. When you run into issues with Automatic Mode (No text detected, Incorrect OCR, Insufficient Cleaning etc), you are now able to make corrections. Simply Undo the Image and toggle Manual Mode.
* In Automatic Mode, Once an Image has been processed, it is loaded in the Viewer or stored to be loaded on switch so you can keep reading in the app as the other Images are being translated.
* Ctrl + Mouse Wheel to Zoom otherwise Vertical Scrolling
* The Usual Trackpad Gestures work for viewing the Image
* Right, Left Keys to Navigate Between Images

## How it works
### Speech Bubble Detection and Text Segmentation
[bubble-and-text-detector](https://huggingface.co/ogkalu/comic-text-and-bubble-detector). RT-DETR-v2 model trained on 11k images of comics (Manga, Webtoons, Western).
Algorithmic segmentation based on the boxes provided from the detection model.

<img src="https://i.imgur.com/TlzVH3j.jpg" width="49%"> <img src="https://i.imgur.com/h18XrYT.jpg" width="49%"> 

### OCR
By Default:
* [manga-ocr](https://github.com/kha-white/manga-ocr) for Japanese
* [Pororo](https://github.com/yunwoong7/korean_ocr_using_pororo) for Korean 
* [PPOCRv5](https://www.paddleocr.ai/main/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5.html) for Everything Else

Optional:

These can be used for any of the supported languages.

* Gemini 2.0 Flash
* Microsoft Azure Vision

### Inpainting
To remove the segmented text
* A [Manga/Anime finetuned](https://huggingface.co/dreMaz/AnimeMangaInpainting) [lama](https://github.com/advimman/lama) checkpoint. Implementation courtsey of [lama-cleaner](https://github.com/Sanster/lama-cleaner)
* [AOT-GAN](https://arxiv.org/abs/2104.01431) based model by [zyddnys](https://github.com/zyddnys)

<img src="https://i.imgur.com/cVVGVXp.jpg" width="49%"> <img src="https://i.imgur.com/bLkPyqG.jpg" width="49%">

### Translation
Currently, this supports using GPT-4.1, Claude-4.5, 
Gemini-2.5, and local Ollama models.

All LLMs are fed the entire page text to aid translations. 
There is also the Option to provide the Image itself for further context. 

### Text Rendering
Wrapped text in bounding boxes obtained from bubbles and text.

## Acknowledgements

* [https://github.com/Sanster/lama-cleaner](https://github.com/Sanster/lama-cleaner)
* [https://huggingface.co/dreMaz](https://huggingface.co/dreMaz)
* [https://github.com/yunwoong7/korean_ocr_using_pororo](https://github.com/yunwoong7/korean_ocr_using_pororo)
* [https://github.com/kha-white/manga-ocr](https://github.com/kha-white/manga-ocr)
* [https://github.com/JaidedAI/EasyOCR](https://github.com/JaidedAI/EasyOCR)
* [https://github.com/PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
* [https://github.com/RapidAI/RapidOCR](https://github.com/RapidAI/RapidOCR)
* [https://github.com/phenom-films/dayu_widgets](https://github.com/phenom-films/dayu_widgets)