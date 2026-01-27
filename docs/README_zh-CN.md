# 漫画翻译
[English](../README.md) | [한국어](README_ko.md) | [Français](README_fr.md) | 简体中文

<img src="https://i.imgur.com/QUVK6mK.png">

## 简介
市面上有很多自动漫画翻译器。但很少有能正确支持其他语言的不同类型漫画的翻译器。
本项目旨在利用 GPT 等最先进 (SOTA) 的大语言模型 (LLM) 的能力来翻译来自世界各地的漫画。

目前，它支持翻译以下语言的漫画：英语、韩语、日语、法语、简体中文、繁体中文、俄语、德语、荷兰语、西班牙语和意大利语。它可以翻译成上述语言以及更多语言。

- [机器翻译的现状](#机器翻译的现状)
- [预览](#漫画样例)
- [快速开始](#安装)
    - [安装](#安装)
        - [下载](#下载)
        - [从源码安装](#从源码安装)
    - [使用](#使用)
        - [提示](#提示)

- [工作原理](#工作原理)
    - [文本检测](#文本检测)
    - [OCR](#OCR)
    - [图像修复](#图像修复)
    - [翻译](#翻译)
    - [文本渲染](#文本渲染)

- [鸣谢](#鸣谢)

## 机器翻译的现状
对于几十种语言来说，最好的机器翻译器不是 Google Translate、Papago 甚至 DeepL，而是像 GPT-4 这样的 SOTA LLM，而且遥遥领先。
这在语言差异较大的语言对（如韩语<->英语，日语<->英语等）中尤为明显，其他翻译器仍然经常翻译出不知所云的内容。

## 漫画样例
使用 GPT-4 作为翻译器。
注意：其中一些也有官方英文翻译。

[The Wretched of the High Seas](https://www.drakoo.fr/bd/drakoo/les_damnes_du_grand_large/les_damnes_du_grand_large_-_histoire_complete/9782382330128)

<img src="https://i.imgur.com/75HwK4r.jpg" width="49%"> <img src="https://i.imgur.com/mx0sQnW.jpeg" width="49%">

[The Wormworld Saga](https://wormworldsaga.com/index.php)

<img src="https://i.imgur.com/cVVGVXp.jpg" width="49%"> <img src="https://i.imgur.com/BpZ7ZAp.jpeg" width="49%">

[Frieren: Beyond Journey's End](https://renta.papy.co.jp/renta/sc/frm/item/220775/title/742932/)

<img src="https://i.imgur.com/ANGHVhG.png" width="49%"> <img src="https://i.imgur.com/QRBXRj0.png" width="49%">

[Days of Sand](https://9ekunst.nl/2021/05/20/nieuw-album-van-aimee-de-jongh-is-benauwend-als-een-zandstorm/)

<img src="https://i.imgur.com/m7PDiXN.jpg" width="49%"> <img src="https://i.imgur.com/4CI4iuC.jpeg" width="49%">

[Player (OH Hyeon-Jun)](https://comic.naver.com/webtoon/list?titleId=745876&page=1&sort=ASC&tab=fri)

<img src="https://i.imgur.com/KGwiHJh.jpg" width="49%"> <img src="https://i.imgur.com/sCQL9Kj.jpeg" width="49%">

[Carbon & Silicon](https://www.amazon.com/Carbone-Silicium-French-Mathieu-Bablet-ebook/dp/B0C1LTGZ85/)

<img src="https://i.imgur.com/h51XJx4.jpg" width="49%"> <img src="https://i.imgur.com/cPTHiys.jpeg" width="49%">

## 安装
### 下载
从[这里](https://www.comic-translate.com/download/)下载并安装适用于 Windows 和 macOS 的 Comic Translate。
> 注意：GPU 加速目前仅在从源码运行时可用。

### 从源码安装
或者，如果您想直接运行源代码。

安装 Python 3.12。在安装过程中勾选“Add python.exe to PATH”。
```bash
https://www.python.org/downloads/
```
安装 git
```bash
https://git-scm.com/
```
安装 uv
```
https://docs.astral.sh/uv/getting-started/installation/
```

然后，在命令行中
```bash
git clone https://github.com/ogkalu2/comic-translate
cd comic-translate
uv init --python 3.12
```
并安装依赖项
```bash
uv add -r requirements.txt --compile-bytecode
```

要更新，请在 comic-translate 文件夹中运行此命令
```bash
git pull
uv init --python 3.12 (注意：仅当您首次安装未使用 uv 时运行此行)
uv add -r requirements.txt --compile-bytecode
```

如果您有 NVIDIA GPU，建议运行
```bash
uv pip install onnxruntime-gpu
```

## 使用
在 comic-translate 目录下，运行
```bash
uv run comic.py
```
這將啟動 GUI

### 提示
* 如果您有 CBR 文件，您需要安装 Winrar 或 7-Zip，然后将其安装文件夹（例如 Windows 的 "C:\Program Files\WinRAR"）添加到 Path。如果已安装但未添加到 Path，您可能会收到错误：
```bash
raise RarCannotExec("Cannot find working tool")
```
在这种情况下，请参考 [Windows](https://www.windowsdigitals.com/add-folder-to-path-environment-variable-in-windows-11-10/)、[Linux](https://linuxize.com/post/how-to-add-directory-to-path-in-linux/)、[Mac](https://techpp.com/2021/09/08/set-path-variable-in-macos-guide/) 的说明。

* 确保所选字体支持目标语言的字符
* v2.0 引入了手动模式。当您遇到自动模式的问题（未检测到文本、OCR 不正确、清理不充分等）时，您现在可以进行更正。只需撤消图像并切换手动模式即可。
* 在自动模式下，一旦图像处理完毕，它将加载到查看器中或存储以便在切换时加载，这样您就可以在翻译其他图像的同时继续在应用中阅读。
* Ctrl + 鼠标滚轮缩放，否则为垂直滚动
* 常用的触控板手势适用于查看图像
* 左右键可在图像之间导航

## 工作原理
### 气泡检测和文本分割
[bubble-and-text-detector](https://huggingface.co/ogkalu/comic-text-and-bubble-detector)。RT-DETR-v2 模型，在 11k 张漫画（日漫、韩漫、美漫）图像上训练。
基于检测模型提供的框进行算法分割。

<img src="https://i.imgur.com/TlzVH3j.jpg" width="49%"> <img src="https://i.imgur.com/h18XrYT.jpg" width="49%"> 

### OCR
默认：
* 日语使用 [manga-ocr](https://github.com/kha-white/manga-ocr)
* 韩语使用 [Pororo](https://github.com/yunwoong7/korean_ocr_using_pororo)
* 其他所有语言使用 [PPOCRv5](https://www.paddleocr.ai/main/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5.html)

可选：

这些可以用于任何支持的语言。

* Gemini 2.0 Flash
* Microsoft Azure Vision

### 图像修复
去除分割后的文本
* 一个[针对漫画/动漫微调](https://huggingface.co/dreMaz/AnimeMangaInpainting)的 [lama](https://github.com/advimman/lama) 检查点。实现由 [lama-cleaner](https://github.com/Sanster/lama-cleaner) 提供
* 基于 [AOT-GAN](https://arxiv.org/abs/2104.01431) 的模型，由 [zyddnys](https://github.com/zyddnys) 提供

<img src="https://i.imgur.com/cVVGVXp.jpg" width="49%"> <img src="https://i.imgur.com/bLkPyqG.jpg" width="49%">

### 翻译
目前支持使用 GPT-4.1, Claude-4.5, 
Gemini-2.5。

所有 LLM 都会输入整页文本以辅助翻译。
还可以选择提供图像本身以获取更多上下文。

### 文本渲染
将文本包裹在从气泡和文本获得的边界框中。

## 鸣谢

* [https://github.com/Sanster/lama-cleaner](https://github.com/Sanster/lama-cleaner)
* [https://huggingface.co/dreMaz](https://huggingface.co/dreMaz)
* [https://github.com/yunwoong7/korean_ocr_using_pororo](https://github.com/yunwoong7/korean_ocr_using_pororo)
* [https://github.com/kha-white/manga-ocr](https://github.com/kha-white/manga-ocr)
* [https://github.com/JaidedAI/EasyOCR](https://github.com/JaidedAI/EasyOCR)
* [https://github.com/PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
* [https://github.com/RapidAI/RapidOCR](https://github.com/RapidAI/RapidOCR)
* [https://github.com/phenom-films/dayu_widgets](https://github.com/phenom-films/dayu_widgets)
