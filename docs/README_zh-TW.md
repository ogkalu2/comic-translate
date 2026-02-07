# 漫畫翻譯
[English](../README.md) | [한국어](README_ko.md) | [Français](README_fr.md) | [简体中文](README_zh-CN.md) | 繁體中文

<img src="https://i.imgur.com/QUVK6mK.png">

## 簡介
市面上有很多自動漫畫翻譯器。但很少有能正確支持其他語言的不同類型漫畫的翻譯器。
本項目旨在利用 GPT 等最先進 (SOTA) 的大語言模型 (LLM) 的能力來翻譯來自世界各地的漫畫。

目前，它支持翻譯以下語言的漫畫：英語、韓語、日語、法語、簡體中文、繁體中文、俄語、德語、荷蘭語、西班牙語和意大利語。它可以翻譯成上述語言以及更多語言。

- [機器翻譯的現狀](#機器翻譯的現狀)
- [預覽](#漫畫樣例)
- [快速開始](#安裝)
    - [安裝](#安裝)
        - [下載](#下載)
        - [從源碼安裝](#從源碼安裝)
    - [使用](#使用)
        - [提示](#提示)

- [工作原理](#工作原理)
    - [文本檢測](#文本檢測)
    - [OCR](#OCR)
    - [圖像修復](#圖像修復)
    - [翻譯](#翻譯)
    - [文本渲染](#文本渲染)

- [鳴謝](#鳴謝)

## 機器翻譯的現狀
對於幾十種語言來說，最好的機器翻譯器不是 Google Translate、Papago 甚至 DeepL，而是像 GPT-4 這樣的 SOTA LLM，而且遙遙領先。
這在語言差異較大的語言對（如韓語<->英語，日語<->英語等）中尤為明顯，其他翻譯器仍然經常翻譯出不知所云的內容。

## 漫畫樣例
使用 GPT-4 作為翻譯器。
注意：其中一些也有官方英文翻譯。

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

## 安裝
### 下載
從[這裡](https://www.comic-translate.com/download/)下載並安裝適用於 Windows 和 macOS 的 Comic Translate。
> 對於 Windows，請忽略 Smart Screen（點擊「更多資訊」> 「仍要執行」）。對於 macOS，在嘗試打開後，前往「設定」> 「隱私與安全性」> 向下滾動並點擊「仍要打開」。

> 注意：GPU 加速目前僅在從源碼執行時可用。

### 從源碼安裝
或者，如果您想直接執行源代碼。

安裝 Python 3.12。在安裝過程中勾選「Add python.exe to PATH」。
```bash
https://www.python.org/downloads/
```
安裝 git
```bash
https://git-scm.com/
```
安裝 uv
```
https://docs.astral.sh/uv/getting-started/installation/
```

然後，在命令列中
```bash
git clone https://github.com/ogkalu2/comic-translate
cd comic-translate
uv init --python 3.12
```
並安裝依賴項
```bash
uv add -r requirements.txt --compile-bytecode
```

要更新，請在 comic-translate 資料夾中執行此命令
```bash
git pull
uv init --python 3.12 (注意：僅當您首次安裝未使用 uv 時執行此行)
uv add -r requirements.txt --compile-bytecode
```

如果您有 NVIDIA GPU，建議執行
```bash
uv pip install onnxruntime-gpu
```

## 使用
在 comic-translate 目錄下，執行
```bash
uv run comic.py
```
這將啟動 GUI

### 提示
* 如果您有 CBR 檔案，您需要安裝 Winrar 或 7-Zip，然後將其安裝資料夾（例如 Windows 的 "C:\Program Files\WinRAR"）新增到 Path。如果已安裝但未新增到 Path，您可能會收到錯誤：
```bash
raise RarCannotExec("Cannot find working tool")
```
在這種情況下，請參考 [Windows](https://www.windowsdigitals.com/add-folder-to-path-environment-variable-in-windows-11-10/)、[Linux](https://linuxize.com/post/how-to-add-directory-to-path-in-linux/)、[Mac](https://techpp.com/2021/09/08/set-path-variable-in-macos-guide/) 的說明。

* 確保所選字體支持目標語言的字元
* v2.0 引入了手動模式。當您遇到自動模式的問題（未檢測到文本、OCR 不正確、清理不充分等）時，您現在可以進行更正。只需撤銷圖像並切換手動模式即可。
* 在自動模式下，一旦圖像處理完畢，它將載入到檢視器中或儲存以便在切換時載入，這樣您就可以在翻譯其他圖像的同時繼續在應用中閱讀。
* Ctrl + 滑鼠滾輪縮放，否則為垂直滾動
* 常用的觸控板手勢適用於檢視圖像
* 左右鍵可在圖像之間導航

## 工作原理
### 氣泡檢測和文本分割
[bubble-and-text-detector](https://huggingface.co/ogkalu/comic-text-and-bubble-detector)。RT-DETR-v2 模型，在 11k 張漫畫（日漫、韓漫、美漫）圖像上訓練。
基於檢測模型提供的框進行演算法分割。

<img src="https://i.imgur.com/TlzVH3j.jpg" width="49%"> <img src="https://i.imgur.com/h18XrYT.jpg" width="49%">

### OCR
預設：
* 日語使用 [manga-ocr](https://github.com/kha-white/manga-ocr)
* 韓語使用 [Pororo](https://github.com/yunwoong7/korean_ocr_using_pororo)
* 其他所有語言使用 [PPOCRv5](https://www.paddleocr.ai/main/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5.html)

選用：

這些可以用於任何支持的語言。

* Gemini 2.0 Flash
* Microsoft Azure Vision

### 圖像修復
移除分割後的文本
* 一個[針對漫畫/動漫微調](https://huggingface.co/dreMaz/AnimeMangaInpainting)的 [lama](https://github.com/advimman/lama) 檢查點。實現由 [lama-cleaner](https://github.com/Sanster/lama-cleaner) 提供
* 基於 [AOT-GAN](https://arxiv.org/abs/2104.01431) 的模型，由 [zyddnys](https://github.com/zyddnys) 提供

<img src="https://i.imgur.com/cVVGVXp.jpg" width="49%"> <img src="https://i.imgur.com/bLkPyqG.jpg" width="49%">

### 翻譯
目前支持使用 GPT-4.1, Claude-4.5,
Gemini-2.5。

所有 LLM 都會輸入整頁文本以輔助翻譯。
還可以選擇提供圖像本身以獲取更多上下文。

### 文本渲染
將文本包裹在從氣泡和文本獲得的邊界框中。

## 鳴謝

* [https://github.com/Sanster/lama-cleaner](https://github.com/Sanster/lama-cleaner)
* [https://huggingface.co/dreMaz](https://huggingface.co/dreMaz)
* [https://github.com/yunwoong7/korean_ocr_using_pororo](https://github.com/yunwoong7/korean_ocr_using_pororo)
* [https://github.com/kha-white/manga-ocr](https://github.com/kha-white/manga-ocr)
* [https://github.com/JaidedAI/EasyOCR](https://github.com/JaidedAI/EasyOCR)
* [https://github.com/PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
* [https://github.com/RapidAI/RapidOCR](https://github.com/RapidAI/RapidOCR)
* [https://github.com/phenom-films/dayu_widgets](https://github.com/phenom-films/dayu_widgets)
