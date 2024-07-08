# コミック翻訳

https://github.com/ogkalu2/comic-translate/assets/115248977/b57360d3-eaad-4a93-bc46-94c01d38927c

## はじめに
多くの自動マンガ翻訳機は存在します。しかし、他の言語の他の種類のコミックを適切にサポートするものは非常に少ないです。このプロジェクトは、GPT-4oの能力を活用して、世界中のコミックを翻訳するために作成されました。現在、英語、韓国語、日本語、フランス語、簡体字中国語、繁体字中国語、ロシア語、ドイツ語、オランダ語、スペイン語、イタリア語へのおよびからの翻訳をサポートしています。以下の言語に翻訳できますが、翻訳元としては使用できません: トルコ語、ポーランド語、ポルトガル語、ブラジルポルトガル語。

- [機械翻訳の現状](#the-state-of-machine-translation)
- [プレビュー](#comic-samples)
- [始め方](#installation)
  - [インストール](#installation)
    - [Python](#python)
  - [使用方法](#usage)
    - [ヒント](#tips)
  - [APIキー](#api-keys)
    - [APIキーの取得](#getting-api-keys)
      - [Open AI](#open-ai-gpt)
      - [Google Cloud Vision](#google-cloud-vision)

- [動作原理](#how-it-works)
  - [テキスト検出](#text-detection)
  - [OCR](#OCR)
  - [インペインティング](#inpainting)
  - [翻訳](#translation)
  - [テキストレンダリング](#text-rendering)

- [謝辞](#acknowledgements)

## 機械翻訳の現状
数十の言語において、最良の機械翻訳はGoogle Translate、Papago、DeepLではなく、圧倒的にGPT-4です。これは特に、英語と韓国語、日本語など、言語間の距離が遠いペアにおいて顕著です。その他の翻訳機はしばしば意味不明な文章になりがちです。

## コミックサンプル
GPT-4oを翻訳機として使用。
注：これらの中には正式な英訳があるものも含まれます。

[高海の哀れな人々](https://www.drakoo.fr/bd/drakoo/les_damnes_du_grand_large/les_damnes_du_grand_large_-_histoire_complete/9782382330128)

<img src="https://i.imgur.com/75HwK4r.jpg" width="49%"> <img src="https://i.imgur.com/Wjjgs33.jpeg" width="49%">

[西遊記](https://ac.qq.com/Comic/comicInfo/id/541812)

<img src="https://i.imgur.com/zk7yiKe.jpg" width="49%"> <img src="https://i.imgur.com/y3tw9HD.jpeg" width="49%">

[ワームワールド サーガ](https://wormworldsaga.com/index.php)

<img src="https://i.imgur.com/cVVGVXp.jpg" width="49%"> <img src="https://i.imgur.com/ER93oER.jpeg" width="49%">

[砂の時代](https://9ekunst.nl/2021/05/20/nieuw-album-van-aimee-de-jongh-is-benauwend-als-een-zandstorm/)

<img src="https://i.imgur.com/m7PDiXN.jpg" width="49%"> <img src="https://i.imgur.com/73CBvga.jpeg" width="49%">

[プレイヤー (オ・ヒョンジュン)](https://comic.naver.com/webtoon/list?titleId=745876&page=1&sort=ASC&tab=fri)

<img src="https://i.imgur.com/KGwiHJh.jpg" width="49%"> <img src="https://i.imgur.com/x87dJnx.jpeg" width="49%">

[カーボンとシリコン](https://www.amazon.com/Carbone-Silicium-French-Mathieu-Bablet-ebook/dp/B0C1LTGZ85/)

<img src="https://i.imgur.com/h51XJx4.jpg" width="49%"> <img src="https://i.imgur.com/FIbz5si.jpeg" width="49%">

## インストール
### Python
Python (<=3.10) をインストールします。セットアップ時に "Add python.exe to PATH" を選択してください。
```bash
https://www.python.org/downloads/
```
現在、PaddleOCRの問題により、Python 3.11以上では完全には動作しません。デフォルトオプション（Paddle）で中国語からの翻訳を行う予定がない場合、requirements.txtファイルの
```bash
paddleocr==2.7.0.3
paddlepaddle==2.5.2
```
を 
```bash
PyMuPDF==1.23.8
```
に置き換えることで、3.11で使用することができます。

リポジトリをクローン（またはフォルダをダウンロード）し、フォルダに移動します
```bash
git clone https://github.com/ogkalu2/comic-translate
cd comic-translate
```
そして、必要なパッケージをインストールします
```bash
pip install -r requirements.txt
```

NVIDIA GPUをお使いの場合、以下のコマンドを実行することをお勧めします
```bash
pip uninstall torch torchvision
pip install torch==2.1.0+cu121 -f https://download.pytorch.org/whl/torch_stable.html
pip install torchvision==0.16.0+cu121 -f https://download.pytorch.org/whl/torch_stable.html
```
注：+cu121の121はCUDAバージョン12.1を示しています。121をお使いのCUDAバージョンに置き換えてください。例えば、CUDA 11.8を使用している場合は118です。

## 使用方法
comic-translateディレクトリで以下を実行します
```bash
python comic.py
```
これによりGUIが起動します

### ヒント
* 「Import > Images」メニューから単一または複数の画像を選択できます。CBRファイルを持っている場合、Winrarまたは7-Zipをインストールし、インストールしたフォルダ（例："C:\Program Files\WinRAR" for Windows）をPathに追加する必要があります。Pathにインストールされていない場合は、
```bash
raise RarCannotExec("Cannot find working tool")
```
というエラーが出ることがあります。その場合、[Windows](https://www.windowsdigitals.com/add-folder-to-path-environment-variable-in-windows-11-10/)、[Linux](https://linuxize.com/post/how-to-add-directory-to-path-in-linux/)、[Mac](https://techpp.com/2021/09/08/set-path-variable-in-macos-guide/)の手順に従ってください。

* 「Settings > Text Rendering > Adjust Textblocks」メニューからレンダリングされるブロックのサイズを調整できます。テキストが大きすぎたり小さすぎたりする場合に有効です。これはページの全ての検出されたブロックに適用されます。
* 選択したフォントがターゲット言語の文字をサポートしていることを確認してください。

## APIキー
以下の選択肢では、閉じたリソースへのアクセスとそれに伴うAPIキーが必要です：
* GPT-4oまたは3.5での翻訳（有料、約$0.01 USD/ページ for 4o）
* DeepL Translator（無料、月間500,000文字まで）
* フランス語、ロシア語、ドイツ語、オランダ語、スペイン語、イタリア語のOCR（有料、約$0.02 USD/ページ）にはGPT-4oがデフォルト
* Microsoft Azure Vision（無料、月間5000画像まで）
* Google Cloud Vision（無料、月間1000画像まで）

「Settings > Set Credentials」メニューからAPIキーを設定できます。

### APIキーの取得
#### Open AI (GPT)
* OpenAIのプラットフォームウェブサイト([platform.openai.com](https://platform.openai.com/))でOpenAIアカウントにサインインするか作成します。
* ページの右タスクバーにカーソルを合わせて「API Keys」を選択します。
* 「Create New Secret Key」をクリックして新しいAPIキーを生成し、コピーして保管します。

#### Google Cloud Vision 
* [Google Cloud](https://cloud.google.com/)アカウントにサインインまたは作成。 [Cloud Resource Manager](https://console.cloud.google.com/cloud-resource-manager) で「Create Project」をクリックしてプロジェクト名を設定します。
* [ここでプロジェクトを選択](https://console.cloud.google.com/welcome)し、「Billing」を選択して「Create Account」を選択します。ポップアップで「Enable billing account」をクリックして、無料トライアルアカウントを作成します。「Account type」を個人に設定し、有効なクレジットカードを入力します。
* プロジェクト用にGoogle Cloud Visionを[ここで有効にします](https://console.cloud.google.com/apis/library/vision.googleapis.com)。
* [Google Cloud Credentials](https://console.cloud.google.com/apis/credentials) ページで「Create Credentials」をクリックし、APIキーを選択します。コピーして保管します。

## 動作原理
### セリフバルーン検出とテキストセグメント化
[speech-bubble-detector](https://huggingface.co/ogkalu/comic-speech-bubble-detector-yolov8m)、[text-segmenter](https://huggingface.co/ogkalu/comic-text-segmenter-yolov8m)。8kおよび3kの画像のコミック（マンガ、ウェブトゥーン、西洋コミック）でそれぞれトレーニングされた2つのyolov8mモデル。

<img src="https://i.imgur.com/TlzVH3j.jpg" width="49%"> <img src="https://i.imgur.com/h18XrYT.jpg" width="49%"> 

### OCR
デフォルトでは：
* 英語には[EasyOCR](https://github.com/JaidedAI/EasyOCR)
* 日本語には[manga-ocr](https://github.com/kha-white/manga-ocr)
* 韓国語には[Pororo](https://github.com/yunwoong7/korean_ocr_using_pororo)
* 中国語には[PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
* フランス語、ロシア語、ドイツ語、オランダ語、スペイン語、イタリア語には[GPT-4o](https://platform.openai.com/docs/guides/vision)がデフォルト（有料、APIキーが必要）

オプション：

これらはサポートされている言語すべてで使用可能です。APIキーが必要です。

* [Google Cloud Vision](https://cloud.google.com/vision/docs/ocr)
* [Microsoft Azure Vision](https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/overview-ocr)

### インペインティング
[Manga/Anime finetuned](https://huggingface.co/dreMaz/AnimeMangaInpainting)を使用する[lama](https://github.com/advimman/lama)チェックポイントで、セグメンターによって検出されたテキストを除去します。実装は[lama-cleaner](https://github.com/Sanster/lama-cleaner)の提供です。

<img src="https://i.imgur.com/cVVGVXp.jpg" width="49%"> <img src="https://i.imgur.com/bLkPyqG.jpg" width="49%">

### 翻訳
現在のところ、GPT-4o、GPT-4、GPT-3.5、DeepL、Google Translateをサポートしています。
すべてのGPTモデルには、翻訳を補助するためにページ全体のテキストの文脈が提供されます。
特にGPT-4oには、ページの画像、元のテキストを含むページが提供され、（フランス語、ロシア語、ドイツ語、オランダ語、スペイン語、イタリア語のような）認識が得意な言語には画像とインペインティングされた画像が提供されます。

### テキストレンダリング
バウンディングボックス内で折り返されたテキストをレンダリングするためにPILを使用しています。

## 謝辞

* [https://github.com/hoffstadt/DearPyGui](https://github.com/hoffstadt/DearPyGui)
* [https://github.com/ultralytics/ultralytics](https://github.com/ultralytics/ultralytics)
* [https://github.com/Sanster/lama-cleaner](https://github.com/Sanster/lama-cleaner)
* [https://huggingface.co/dreMaz](https://huggingface.co/dreMaz)
* [https://github.com/yunwoong7/korean_ocr_using_pororo](https://github.com/yunwoong7/korean_ocr_using_pororo)
* [https://github.com/kha-white/manga-ocr](https://github.com/kha-white/manga-ocr)
* [https://github.com/JaidedAI/EasyOCR](https://github.com/JaidedAI/EasyOCR)
* [https://github.com/PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)