# Comic Translate
English | [한국어](docs/README_ko.md) | [Français](docs/README_fr.md) 

https://github.com/ogkalu2/comic-translate/assets/115248977/b57360d3-eaad-4a93-bc46-94c01d38927c

## Intro
Many Automatic Manga Translators exist. Very few properly support comics of other kinds in other languages. 
This project was created to utilize the ability of GPT-4 and translate comics from all over the world. Currently, it supports translating to and from English, Korean, Japanese, French, Simplified Chinese, Traditional Chinese, Russian, German, Dutch, Spanish and Italian.

- [The State of Machine Translation](#the-state-of-machine-translation)
- [Preview](#comic-samples)
- [Getting Started](#installation)
    - [Installation](#installation)
        - [Python](#python)
    - [Usage](#usage)
        - [Tips](#tips)
    - [API keys](#api-keys)
        - [Getting API Keys](#getting-api-keys)
            - [Open AI](#open-ai-gpt)
            - [Google Cloud Vision](#google-cloud-vision)
            - [Google Gemini](#google-gemini)

- [How it works](#how-it-works)
    - [Text Detection](#text-detection)
    - [OCR](#OCR)
    - [Inpainting](#inpainting)
    - [Translation](#translation)
    - [Text Rendering](#text-rendering)

- [Acknowledgements](#acknowledgements)

## The State of Machine Translation
For a couple dozen languages, the best Machine Translator is not Google Translate, Papago or even DeepL, but GPT-4, and by far. 
This is very apparent for distant language pairs (Korean<->English, Japanese<->English etc) where other translators still often devolve into gibberish.
Excerpt from "The Walking Practice"(보행 연습) by Dolki Min(돌기민)
![Model](https://i.imgur.com/e1aeLej.png)

## Comic Samples
GPT-4-Vision as Translator.
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
### Python
Install Python (<=3.10). Tick "Add python.exe to PATH" during the setup.
```bash
https://www.python.org/downloads/
```
Currently, this doesn't work fully on python 3.11 or higher because of issues with PaddleOCR. If you have no intention of translating from Chinese with the Default Option(Paddle), you can use this with 3.11 by replacing
```bash
paddleocr==2.7.0.3
paddlepaddle==2.5.2
```
with 
```bash
PyMuPDF==1.23.8
```
in the requirements.txt file.

Clone the repo (or download the folder), navigate to the folder
```bash
git clone https://github.com/ogkalu2/comic-translate
cd comic-translate
```
and install the requirements
```bash
pip install -r requirements.txt
```

If you have an NVIDIA GPU, then it is recommended to run
```bash
pip uninstall torch torchvision
pip install torch==2.1.0+cu121 -f https://download.pytorch.org/whl/torch_stable.html
pip install torchvision==0.16.0+cu121 -f https://download.pytorch.org/whl/torch_stable.html
```
Note: The 121 in +cu121 represents the CUDA version - 12.1. Replace 121 with your CUDA version. E.g 118 if you are running CUDA 11.8

## Usage
In the comic-translate directory, run
```bash
python comic.py
```
This will launch the GUI

### Tips
* Import > Images to select a Single or multiple Images. If you have a CBR file, you'll need to install Winrar or 7-Zip then add the folder it's installed to (e.g "C:\Program Files\WinRAR" for Windows) to Path. If it's installed but not to Path, you may get the error, 
```bash
raise RarCannotExec("Cannot find working tool")
```
In that case, Instructions for [Windows](https://www.windowsdigitals.com/add-folder-to-path-environment-variable-in-windows-11-10/), [Linux](https://linuxize.com/post/how-to-add-directory-to-path-in-linux/), [Mac](https://techpp.com/2021/09/08/set-path-variable-in-macos-guide/)

* Go to Settings > Text Rendering > Adjust Textblocks to adjust the dimensions of the blocks used for rendering. For situations where text is rendered too big/small. 
It will apply to all detcted blocks on the page
* Make sure the selected Font supports characters of the target language

## API Keys
To following selections will require access to closed resources and subsequently, API Keys:
* GPT-4-Vision, 4 or 3.5 for Translation (Paid, about $0.02 USD/Page for 4-Turbo)
* DeepL Translator (Free for 500,000 characters/month)
* GPT-4-Vision for OCR (Default Option for French, Russian, German, Dutch, Spanish, Italian) (Paid, about $0.04 USD/Page)
* Microsoft Azure Vision for OCR (Free for 5000 images/month)
* Google Cloud Vision for OCR (Free for 1000 images/month)
* Google Gemini for translation (Free for 1500 images per day) (Paid, about $0.001 USD/Page)
You can set your API Keys by going to Settings > Set Credentials

### Getting API Keys
#### Open AI (GPT)
* Go to OpenAI's Platform website at [platform.openai.com](https://platform.openai.com/) and sign in with (or create) an OpenAI account.
* Hover your Mouse over the right taskbar of the page and select "API Keys."
* Click "Create New Secret Key" to generate a new API key. Copy and store it.

#### Google Cloud Vision 
* Sign in/Create a [Google Cloud](https://cloud.google.com/) account. Go to [Cloud Resource Manager](https://console.cloud.google.com/cloud-resource-manager) and click "Create Project". Set your project name. 
* [Select your project here](https://console.cloud.google.com/welcome) then select "Billing" then "Create Account". In the pop-up, "Enable billing account", and accept the offer of a free trial account. Your "Account type" should be individual. Fill in a valid credit card.
* Enable Google Cloud Vison for your project [here](https://console.cloud.google.com/apis/library/vision.googleapis.com)
* In the [Google Cloud Credentials](https://console.cloud.google.com/apis/credentials) page, click "Create Credentials" then API Key. Copy and store it.
  
#### Google Gemini
* Go to the Google AI Studio website at [aistudio.google.com](https://aistudio.google.com/app/apikey). Once there, locate the option to create an API key and click on it. The API key will then be displayed. Make sure to save this API key in a secure location for future use."

## How it works
### Speech Bubble Detection and Text Segmentation
[speech-bubble-detector](https://huggingface.co/ogkalu/comic-speech-bubble-detector-yolov8m), [text-segmenter](https://huggingface.co/ogkalu/comic-text-segmenter-yolov8m). Two yolov8m models trained on 8k and 3k images of comics (Manga, Webtoons, Western) respectively. 

<img src="https://i.imgur.com/TlzVH3j.jpg" width="49%"> <img src="https://i.imgur.com/h18XrYT.jpg" width="49%"> 

### OCR
By Default:
* [EasyOCR](https://github.com/JaidedAI/EasyOCR) for English
* [manga-ocr](https://github.com/kha-white/manga-ocr) for Japanese
* [Pororo](https://github.com/yunwoong7/korean_ocr_using_pororo) for Korean 
* [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) for Chinese 
* [GPT-4-Vision](https://platform.openai.com/docs/guides/vision) for French, Russian, German, Dutch, Spanish and Italian. Paid, Requires an API Key.

Optional:

These can be used for any of the supported languages. An API Key is required.

* [Google Cloud Vision](https://cloud.google.com/vision/docs/ocr)
* [Microsoft Azure Vision](https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/overview-ocr)

### Inpainting
A [Manga/Anime finetuned](https://huggingface.co/dreMaz/AnimeMangaInpainting) [lama](https://github.com/advimman/lama) checkpoint to remove text detected by the segmenter. Implementation courtsey of [lama-cleaner](https://github.com/Sanster/lama-cleaner)

<img src="https://i.imgur.com/cVVGVXp.jpg" width="49%"> <img src="https://i.imgur.com/bLkPyqG.jpg" width="49%">

### Translation
Currently, this supports using GPT-4-Vision, GPT-4, GPT-3.5, DeepL and Google Translate.
All GPT models are fed the context of the entire page text to aid translations. 
GPT-4-Vision specifically is also provided the image of the page, the page with the original text for
languages it is competent at recognizing (French, Russian, German, Dutch, Spanish, Italian) and the Inpainted Image for the rest. 

### Text Rendering
PIL for rendering wrapped text in bounding boxes obtained from bubbles and text.

## Acknowledgements

* [https://github.com/hoffstadt/DearPyGui](https://github.com/hoffstadt/DearPyGui)
* [https://github.com/ultralytics/ultralytics](https://github.com/ultralytics/ultralytics)
* [https://github.com/Sanster/lama-cleaner](https://github.com/Sanster/lama-cleaner)
* [https://huggingface.co/dreMaz](https://huggingface.co/dreMaz)
* [https://github.com/yunwoong7/korean_ocr_using_pororo](https://github.com/yunwoong7/korean_ocr_using_pororo)
* [https://github.com/kha-white/manga-ocr](https://github.com/kha-white/manga-ocr)
* [https://github.com/JaidedAI/EasyOCR](https://github.com/JaidedAI/EasyOCR)
* [https://github.com/PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
