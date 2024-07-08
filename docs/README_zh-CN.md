# 漫画翻译

https://github.com/ogkalu2/comic-translate/assets/115248977/b57360d3-eaad-4a93-bc46-94c01d38927c

## 简介

许多自动漫画翻译器存在。但很少有能正确支持其他语言的不同类型的漫画。本项目旨在利用 GPT-4 的能力来翻译来自世界各地的漫画。目前，它支持翻译为英文、韩文、日文、法文、简体中文、繁体中文、俄文、德文、荷兰文、西班牙文和意大利文，以及这些语言之间的互译。它可以翻译成土耳其语、波兰语、葡萄牙语和巴西葡萄牙语，但不能翻译这些语言的内容。

- [机器翻译的现状](#机器翻译的现状)
- [预览](#漫画样例)
- [快速开始](#安装)
  - [安装](#安装)
    - [Python](#python)
  - [使用](#使用)
    - [提示](#提示)
  - [API密钥](#api-密钥)
    - [获取API密钥](#获取-api-密钥)
      - [Open AI](#open-ai-gpt)
      - [Google Cloud Vision](#google-cloud-vision)

- [工作原理](#工作原理)
  - [文本检测](#文本检测)
  - [OCR](#ocr)
  - [图像修补](#图像修补)
  - [翻译](#翻译)
  - [文本渲染](#文本渲染)

- [鸣谢](#鸣谢)

## 机器翻译的现状

对于几十种语言来说，最好的机器翻译器不是 Google Translate、Papago 甚至 DeepL，而是 GPT-4，并且优势明显。这在语言对（如韩文<->英文，日文<->英文等）间尤为明显，其他翻译器仍然常常会变成胡言乱语。

## 漫画样例

GPT-4o 作为翻译器。
注意：其中一些漫画也有官方英文翻译

[大海的凄惨](https://www.drakoo.fr/bd/drakoo/les_damnes_du_grand_large/les_damnes_du_grand_large_-_histoire_complete/9782382330128)

<img src="https://i.imgur.com/75HwK4r.jpg" width="49%"> <img src="https://i.imgur.com/mx0sQnW.jpeg" width="49%">

[弗莉伦：旅途的终点](https://renta.papy.co.jp/renta/sc/frm/item/220775/title/742932/)

<img src="https://i.imgur.com/ANGHVhG.png" width="49%"> <img src="https://i.imgur.com/QRBXRj0.png" width="49%">

[虫世界传奇](https://wormworldsaga.com/index.php)

<img src="https://i.imgur.com/cVVGVXp.jpg" width="49%"> <img src="https://i.imgur.com/BpZ7ZAp.jpeg" width="49%">

[沙之日](https://9ekunst.nl/2021/05/20/nieuw-album-van-aimee-de-jongh-is-benauwend-als-een-zandstorm/)

<img src="https://i.imgur.com/m7PDiXN.jpg" width="49%"> <img src="https://i.imgur.com/4CI4iuC.jpeg" width="49%">

[玩家 (OH Hyeon-Jun)](https://comic.naver.com/webtoon/list?titleId=745876&page=1&sort=ASC&tab=fri)

<img src="https://i.imgur.com/KGwiHJh.jpg" width="49%"> <img src="https://i.imgur.com/sCQL9Kj.jpeg" width="49%">

[碳与硅](https://www.amazon.com/Carbone-Silicium-French-Mathieu-Bablet-ebook/dp/B0C1LTGZ85/)

<img src="https://i.imgur.com/h51XJx4.jpg" width="49%"> <img src="https://i.imgur.com/cPTHiys.jpeg" width="49%">

## 安装

### Python

安装 Python (<=3.10)。在设置中选择 "Add python.exe to PATH"。
```bash
https://www.python.org/downloads/
```
目前，由于 PaddleOCR 的问题，该项目无法完全在 Python 3.11 或更高版本上运行。如果您无意使用默认选项（Paddle）进行中文翻译，可以通过将
```bash
paddleocr==2.7.0.3
paddlepaddle==2.5.2
```
替换为
```bash
PyMuPDF==1.23.8
```
在 `requirements.txt` 文件中来使用 Python 3.11 或更高版本。

克隆仓库（或下载文件夹），导航到文件夹
```bash
git clone https://github.com/ogkalu2/comic-translate
cd comic-translate
```
并安装依赖项
```bash
pip install -r requirements.txt
```

如果您有 NVIDIA GPU，建议运行
```bash
pip uninstall torch torchvision
pip install torch==2.1.0+cu121 -f https://download.pytorch.org/whl/torch_stable.html
pip install torchvision==0.16.0+cu121 -f https://download.pytorch.org/whl/torch_stable.html
```
注意：+cu121 中的121代表 CUDA 版本 - 12.1。将121替换为您的 CUDA 版本。例如，运行 CUDA 11.8 时替换为118。

## 使用

在comic-translate目录下运行
```bash
python comic.py
```
这将启动 GUI

### 提示

* 导入 > 图像以选择单个或多个图像。如果您有 CBR 文件，您需要安装 Winrar 或 7-Zip，然后将其安装文件夹（例如 Windows 的"C:\Program Files\WinRAR"）添加到 PATH。如果已安装但未添加到 PATH，您可能会收到错误信息，
```bash
raise RarCannotExec("Cannot find working tool")
```
在这种情况下，您可以遵循以下网站的说明：[Windows](https://www.windowsdigitals.com/add-folder-to-path-environment-variable-in-windows-11-10/), [Linux](https://linuxize.com/post/how-to-add-directory-to-path-in-linux/), [Mac](https://techpp.com/2021/09/08/set-path-variable-in-macos-guide/)

* 前往设置 > 文本渲染 > 调整文本块以调整用于渲染的块的尺寸。适用于文本渲染过大/过小的情况。这将适用于页面上的所有检测到的块
* 确保所选字体支持目标语言的字符

## API 密钥

以下选择将需要访问封闭资源，因此需要 API 密钥：
* 用于翻译的 GPT-4o 或 3.5（付费，每页约 $0.01 美元用于 4o）
* DeepL 翻译器（免费，每月 500,000 个字符）
* 用于 OCR 的 GPT-4o（法文、俄文、德文、荷兰文、西班牙文、意大利文的默认选项）（付费，每页约 $0.02 美元）
* Microsoft Azure Vision 用于 OCR（免费，每月 5000 张图片）
* Google Cloud Vision 用于 OCR（免费，每月 1000 张图片）。
您可以前往设置 > 设置凭证 来设置 API 密钥

### 获取 API 密钥

#### Open AI (GPT)

* 前往 OpenAI 的平台网站 [platform.openai.com](https://platform.openai.com/) 并使用（或创建）一个 OpenAI 账户进行登录。
* 将鼠标悬停在页面右侧任务栏上，选择 "API 密钥"。
* 点击 "创建新秘密密钥" 来生成新 API 密钥。复制并保存它。

#### Google Cloud Vision

* 登录/创建一个 [Google Cloud](https://cloud.google.com/) 账户。前往[Cloud Resource Manager](https://console.cloud.google.com/cloud-resource-manager)并点击 "创建项目"。设置您的项目名称。
* [在此处选择您的项目](https://console.cloud.google.com/welcome)，然后选择 "计费"，再选择 "创建账户"。在弹出窗口中，"启用计费账户"，并接受免费试用账户的优惠。您的 "账户类型" 应为个人账户。填写有效信用卡信息。
* 为项目启用 Google Cloud Vision [在这里](https://console.cloud.google.com/apis/library/vision.googleapis.com)
* 在 [Google Cloud Credentials](https://console.cloud.google.com/apis/credentials) 页面，点击 "创建凭证" 然后 API 密钥。复制并保存它。

## 工作原理

### 对话气泡检测和文本分割

[speech-bubble-detector](https://huggingface.co/ogkalu/comic-speech-bubble-detector-yolov8m)，[text-segmenter](https://huggingface.co/ogkalu/comic-text-segmenter-yolov8m)。两个 yolov8m 模型，分别在 8000 张和 3000 张漫画（包括漫画、网络漫画、欧美漫画）图像上训练。

<img src="https://i.imgur.com/TlzVH3j.jpg" width="49%"> <img src="https://i.imgur.com/h18XrYT.jpg" width="49%"> 

### OCR

默认为：
* [EasyOCR](https://github.com/JaidedAI/EasyOCR) 用于英文
* [manga-ocr](https://github.com/kha-white/manga-ocr) 用于日文
* [Pororo](https://github.com/yunwoong7/korean_ocr_using_pororo) 用于韩文 
* [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) 用于中文 
* [GPT-4o](https://platform.openai.com/docs/guides/vision) 用于法文、俄文、德文、荷兰文、西班牙文和意大利文。需付费，需要 API 密钥。

可选：

这些可以用于任何支持的语言。需要 API 密钥。

* [Google Cloud Vision](https://cloud.google.com/vision/docs/ocr)
* [Microsoft Azure Vision](https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/overview-ocr)

### 图像修补

使用 [经过细调的漫画/动漫](https://huggingface.co/dreMaz/AnimeMangaInpainting) [lama](https://github.com/advimman/lama) 检测点来删除由分割器检测到的文本。实现 courtesy of [lama-cleaner](https://github.com/Sanster/lama-cleaner)

<img src="https://i.imgur.com/cVVGVXp.jpg" width="49%"> <img src="https://i.imgur.com/bLkPyqG.jpg" width="49%">

### 翻译

目前支持使用 GPT-4o、GPT-4、GPT-3.5、DeepL 和 Google Translate。
所有 GPT 模型都会读取整个页面文本的上下文以辅助翻译。特别是 GPT-4o 还会提供页面的图像，用于它擅长识别的语言（法文、俄文、德文、荷兰文、西班牙文、意大利文）中的原始文本所对应的页面图像，及其余语言的修补图像。

### 文本渲染

使用 PIL 在对话框和文本检测框内渲染换行文本。

## 鸣谢

* [https://github.com/hoffstadt/DearPyGui](https://github.com/hoffstadt/DearPyGui)
* [https://github.com/ultralytics/ultralytics](https://github.com/ultralytics/ultralytics)
* [https://github.com/Sanster/lama-cleaner](https://github.com/Sanster/lama-cleaner)
* [https://huggingface.co/dreMaz](https://huggingface.co/dreMaz)
* [https://github.com/yunwoong7/korean_ocr_using_pororo](https://github.com/yunwoong7/korean_ocr_using_pororo)
* [https://github.com/kha-white/manga-ocr](https://github.com/kha-white/manga-ocr)
* [https://github.com/JaidedAI/EasyOCR](https://github.com/JaidedAI/EasyOCR)
* [https://github.com/PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)