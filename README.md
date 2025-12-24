# Comic Translate
English | [한국어](docs/README_ko.md) | [Français](docs/README_fr.md) | [简体中文](docs/README_zh-CN.md) | [日本語](docs/README_ja.md) | [Português Brasileiro](docs/README_pt-BR.md)

<img src="https://i.imgur.com/QUVK6mK.png">

## Intro
Many Automatic Manga Translators exist. Very few properly support comics of other kinds in other languages. 
This project was created to utilize the ability of State of the Art (SOTA) Large Language Models (LLMs) like GPT-4 and translate comics from all over the world. Currently, it supports translating to and from English, Korean, Japanese, French, Simplified Chinese, Traditional Chinese, Russian, German, Dutch, Spanish and Italian. It can translate to (but not from) Turkish, Polish, Portuguese and Brazillian Portuguese.

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

- [How it works](#how-it-works)
    - [Text Detection](#text-detection)
    - [OCR](#OCR)
    - [Inpainting](#inpainting)
    - [Translation](#translation)
    - [Text Rendering](#text-rendering)

- [Acknowledgements](#acknowledgements)

## The State of Machine Translation
For a couple dozen languages, the best Machine Translator is not Google Translate, Papago or even DeepL, but a SOTA LLM like GPT-4o, and by far. 
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
### Python
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
uv remove torch torchvision
uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
```
Note: The 126 in cu126 represents the CUDA version - 12.6. Replace 126 with your CUDA version (or the version closest to yours). E.g 118 if you are running CUDA 11.8

## Usage
In the comic-translate directory, run
```bash
uv run comic.py
```
This will launch the GUI

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

## API Keys
To following selections will require access to closed resources and subsequently, API Keys:
* GPT-4o or 4o-mini for Translation (Paid, about $0.01 USD/Page for 4o)
* DeepL Translator (Free for 500,000 characters/month)
* GPT-4o for OCR (Default Option for French, Russian, German, Dutch, Spanish, Italian) (Paid, about $0.02 USD/Page)
* Microsoft Azure Vision for OCR (Free for 5000 images/month)
* Google Cloud Vision for OCR (Free for 1000 images/month)
You can set your API Keys by going to Settings > Credentials

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

## How it works
### Speech Bubble Detection and Text Segmentation
[speech-bubble-detector](https://huggingface.co/ogkalu/comic-speech-bubble-detector-yolov8m), [text-segmenter](https://huggingface.co/ogkalu/comic-text-segmenter-yolov8m). Two yolov8m models trained on 8k and 3k images of comics (Manga, Webtoons, Western) respectively. 

<img src="https://i.imgur.com/TlzVH3j.jpg" width="49%"> <img src="https://i.imgur.com/h18XrYT.jpg" width="49%"> 

### OCR
By Default:
* [doctr](https://github.com/mindee/doctr) for English, French, German, Dutch, Spanish and Italian.
* [manga-ocr](https://github.com/kha-white/manga-ocr) for Japanese
* [Pororo](https://github.com/yunwoong7/korean_ocr_using_pororo) for Korean 
* [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) for Chinese 
* [GPT-4o](https://platform.openai.com/docs/guides/vision) for Russian. Paid, Requires an API Key.

Optional:

These can be used for any of the supported languages. An API Key is required.

* [Google Cloud Vision](https://cloud.google.com/vision/docs/ocr)
* [Microsoft Azure Vision](https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/overview-ocr)

### Inpainting
A [Manga/Anime finetuned](https://huggingface.co/dreMaz/AnimeMangaInpainting) [lama](https://github.com/advimman/lama) checkpoint to remove text detected by the segmenter. Implementation courtsey of [lama-cleaner](https://github.com/Sanster/lama-cleaner)

<img src="https://i.imgur.com/cVVGVXp.jpg" width="49%"> <img src="https://i.imgur.com/bLkPyqG.jpg" width="49%">

### Translation
Currently, this supports using GPT-4o, GPT-4o mini, DeepL, Claude-3-Opus, Claude-3.5-Sonnet, Claude-3-Haiku, 
Gemini-1.5-Flash, Gemini-1.5-Pro, Yandex, Google Translate and Microsoft Translator.

All LLMs are fed the entire page text to aid translations. 
There is also the Option to provide the Image itself for further context. 

### Text Rendering
Wrapped text in bounding boxes obtained from bubbles and text.

## Acknowledgements

* [https://github.com/ultralytics/ultralytics](https://github.com/ultralytics/ultralytics)
* [https://github.com/Sanster/lama-cleaner](https://github.com/Sanster/lama-cleaner)
* [https://huggingface.co/dreMaz](https://huggingface.co/dreMaz)
* [https://github.com/yunwoong7/korean_ocr_using_pororo](https://github.com/yunwoong7/korean_ocr_using_pororo)
* [https://github.com/kha-white/manga-ocr](https://github.com/kha-white/manga-ocr)
* [https://github.com/JaidedAI/EasyOCR](https://github.com/JaidedAI/EasyOCR)
* [https://github.com/PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
* [https://github.com/phenom-films/dayu_widgets](https://github.com/phenom-films/dayu_widgets)

# Utilisation des modèles IA locaux (Traduction & OCR)

## Prérequis

- Python 3.8+
- Installez les dépendances nécessaires :

```bash
pip install torch transformers easyocr
```

## Traduction locale (HuggingFace, LLM, Ollama)

- Dans les paramètres de l’application, sélectionnez **"Traduction Locale"** comme moteur de traduction.
- Dans la section "Modèle local (LLM/Traduction)", choisissez le **type de modèle** :
  - **Seq2Seq (Traduction)** : pour les modèles de traduction HuggingFace (ex : NLLB, MarianMT, Helsinki-NLP, etc.)
  - **CausalLM (LLM)** : pour les modèles de génération de texte HuggingFace (ex : Llama, Mistral, GPT2, etc.)
  - **Ollama** : pour utiliser un modèle LLM via l’API Ollama (local, open source)

### Utiliser un modèle HuggingFace (Seq2Seq ou CausalLM)
- Déposez le dossier du modèle téléchargé dans un dossier local.
- Sélectionnez ce dossier via le bouton dans les paramètres.
- Pour Seq2Seq, le pipeline de traduction HuggingFace sera utilisé.
- Pour CausalLM, le pipeline de génération de texte HuggingFace sera utilisé (prompt : "Traduire en <langue> : <texte>").

### Utiliser un modèle Ollama
- Installez Ollama sur votre machine : https://ollama.com/
- Téléchargez un modèle compatible (ex : llama2, mistral, phi3, etc.) avec la commande :
  ```bash
  ollama pull mistral
  ollama pull llama2
  # etc.
  ```
- Dans les paramètres, choisissez "Ollama" comme type de modèle.
- Renseignez l’URL de l’API Ollama (par défaut : http://localhost:11434) et le nom du modèle (ex : llama2, mistral).
- Le prompt envoyé à Ollama sera : "Traduire en <langue> : <texte>".

**Remarque :**
- Vous pouvez utiliser n’importe quel modèle compatible avec le pipeline HuggingFace ou Ollama.
- Les performances et la qualité dépendent du modèle choisi et de la puissance de votre machine.

## OCR local (EasyOCR)

- Dans les paramètres de l’application, sélectionnez **"EasyOCR"** comme moteur OCR.
- EasyOCR fonctionne sur CPU par défaut, mais peut utiliser le GPU si activé dans les paramètres.
- Prend en charge de nombreuses langues (voir la doc EasyOCR pour la liste complète).

## Conseils de performance

- Pour de meilleures performances sur CPU, utilisez les versions optimisées de torch pour votre plateforme.
- Les modèles sélectionnés sont adaptés à des machines avec moins de 8GB de RAM.

## Limitations

- La première utilisation peut être plus lente (téléchargement et initialisation du modèle).
- Les performances et la qualité dépendent du modèle choisi et de la puissance de votre machine.

## Dépannage

- Si vous rencontrez des erreurs de mémoire, essayez un modèle plus léger (ex: MarianMT pour des paires de langues spécifiques).
- Consultez la console pour les messages d’erreur détaillés.

---

Pour toute question ou contribution, ouvrez une issue sur le dépôt GitHub.

## Polices personnalisées et styles

- Plusieurs polices par défaut sont proposées dans l'interface (dossier `fonts/`).
- Pour ajouter vos propres polices, placez les fichiers `.ttf`, `.otf`, `.woff` ou `.woff2` dans le dossier `fonts/`.
- Vous pouvez ensuite les sélectionner dans les paramètres de rendu du texte (Settings > Font).
- Exemples de polices incluses : Short Baby, ShadeBlue. Vous pouvez en ajouter d'autres (ComicNeue, Bangers, Roboto, etc).


