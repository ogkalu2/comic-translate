# Trình dịch truyện tranh
<img src="https://i.imgur.com/QUVK6mK.png">

[English](../README.md) | [한국어](README_ko.md) | [Français](README_fr.md) | [简体中文](README_zh-CN.md) | [日本語](README_ja.md) | [Português Brasileiro](README_pt-BR.md) | Tiếng Việt

## Giới thiệu
Hiện nay có rất nhiều trình dịch truyện tranh một cách tự động. Tuy nhiên, rất ít phần mềm hỗ trợ tốt các thể loại truyện tranh khác bằng nhiều ngôn ngữ khác.
Dự án này được tạo ra để tận dụng khả năng của các mô hình ngôn ngữ lớn (LLM) xịn sò nhất hiện nay như GPT-4 và dịch truyện tranh từ khắp nơi trên cả thế giới.
Hiện tại, nó hỗ trợ dịch từ và sang: tiếng Anh, tiếng Hàn, tiếng Nhật, tiếng Pháp, tiếng Trung giản thể, tiếng Trung phồn thể, tiếng Nga, tiếng Đức, tiếng Hà Lan, tiếng Tây Ban Nha ,tiếng Ý.

- [Hiên trạng của máy dịch](#Tình-trạng-hiện-tại-của-dịch-máy)
- [Xem thử](#Mẫu-truyện-tranh)
- [Bắc đầu](#Cài-đặt)
    - [Cài đặt](#Cài-đặt)
      - [Python](#python)
    - [Cách sử dụng](#Cách-sử-dụng)
      - [Tips](#tips)
    - [API keys](#api-keys)
      - [Lấy khóa API](#Lấy-API-Keys)
            - [Open AI](#open-ai-gpt)
            - [Google Cloud Vision](#google-cloud-vision)
        
- [Cách hoạt động](#Cách-hoạt-động)
    - [Phát hiện bong bóng thoại và phân đoạn văn bản](#Phát-hiện-bong-bóng-thoại-và-phân-đoạn-văn-bản)
    -  [Nhận dạng ký tự quang học (OCR)](#OCR)
    - [Inpainting](#inpainting) <!-- từ này nếu dịch ra tiếng viết sẽ khó hiểu hơn. nên tốt nhất là giữa nguyên -->
    - [Dịch thuật](#Dịch-thuật)
    - [Tái tạo Văn bản](#Tái-tạo-văn-bản)

  - [Lời cảm ơn](#acknowledgements)
 
## Tình trạng hiện tại của dịch máy
Đối với khoảng 20 ngôn ngữ, công cụ dịch máy tốt nhất không phải là Google dịch, Papago hay thậm chí DeepL, mà là một công cụ LLM hàng đầu như GPT-4o, và vượt trội hơn hẳn.
Điều này rất rõ ràng đối với các cặp ngôn ngữ xa nhau (tiếng Hàn <-> tiếng Anh, tiếng Nhật <-> tiếng Anh, v.v.) nơi các công cụ dịch khác vẫn thường cho ra kết quả vô nghĩa.

Trích đoạn từ "Thực hành đi bộ" (보행 연습) của Dolki Min (돌기민)
![Model](https://i.imgur.com/72jvLBa.png)

## Mẫu truyện tranh
GPT-4 là người dịch.

Lưu ý: Một số mẫu này cũng có bản dịch tiếng Anh chính thức.
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

## Cài đặt
### Python
Cài đặt Python 3.12. Chọn "Thêm python.exe vào PATH" trong quá trình cài đặt.
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

Trong dòng lệnh (command line):
```bash
git clone https://github.com/ogkalu2/comic-translate
cd comic-translate
uv init --python 3.12
```
và cài đặt các yêu cầu:
```bash
uv add -r requirements.txt --compile-bytecode
```

Để cập nhật, chạy lệnh này trong thư mục comic-translate:
```bash
git pull
uv init --python 3.12 (Lưu ý: chỉ chạy dòng này nếu bạn không sử dụng uv trong lần cài đặt đầu tiên)
uv add -r requirements.txt --compile-bytecode
```

Nếu bạn có GPU NVIDIA, thì nên chạy lệnh sau:
```bash
uv pip install onnxruntime-gpu
```

## Cách sử dụng
Trong thư mục comic-translate, chạy lệnh sau:
```bash
uv run comic.py
```
Thao tác này sẽ khởi chạy giao diện người dùng đồ họa (GUI)


### Tips
* Nếu bạn có file CBR, bạn sẽ cần cài đặt WinRAR hoặc 7-Zip, sau đó thêm thư mục cài đặt của nó (ví dụ: "C:\Program Files\WinRAR" trên Windows) vào biến môi trường Path. Nếu đã cài đặt nhưng chưa thêm vào Path, bạn có thể gặp lỗi:
```bash
raise RarCannotExec("Cannot find working tool")
```

Trong trường hợp đó, hãy làm theo hướng dẫn cho [Windows](https://www.windowsdigitals.com/add-folder-to-path-environment-variable-in-windows-11-10/), [Linux](https://linuxize.com/post/how-to-add-directory-to-path-in-linux/), [Mac](https://techpp.com/2021/09/08/set-path-variable-in-macos-guide/)

* Đảm bảo font chữ được chọn có hỗ trợ các ký tự của ngôn ngữ mục tiêu
* Phiên bản v2.0 giới thiệu Chế độ Thủ công (Manual Mode). Khi bạn gặp vấn đề với Chế độ Tự động (không phát hiện được văn bản, OCR sai, làm sạch không đủ, v.v.), bạn có thể tự chỉnh sửa. Chỉ cần Hoàn tác (Undo) hình ảnh và bật Manual Mode.
* Trong Chế độ Tự động, sau khi một hình ảnh được xử lý, nó sẽ được tải vào Viewer hoặc lưu lại để tải khi chuyển đổi, giúp bạn tiếp tục đọc trong ứng dụng trong khi các hình ảnh khác vẫn đang được dịch.
* Ctrl + con lăn chuột để phóng to / thu nhỏ, nếu không thì cuộn dọc
* Các cử chỉ trackpad thông thường đều hoạt động khi xem hình ảnh
* Phím mũi tên Trái, Phải để chuyển giữa các hình ảnh

## API Keys

Các lựa chọn sau sẽ cần truy cập vào tài nguyên đóng và do đó yêu cầu API Key:

* GPT-4o hoặc 4o-mini để Dịch (Trả phí, khoảng $0.01 USD/trang với 4o)
* DeepL Translator (Miễn phí 500.000 ký tự/tháng)
* GPT-4o cho OCR (Tùy chọn mặc định cho tiếng Pháp, Nga, Đức, Hà Lan, Tây Ban Nha, Ý) (Trả phí, khoảng $0.02 USD/trang)
* Microsoft Azure Vision cho OCR (Miễn phí 5000 hình ảnh/tháng)
* Google Cloud Vision cho OCR (Miễn phí 1000 hình ảnh/tháng)
  Bạn có thể thiết lập API Key bằng cách vào Settings > Credentials

### Lấy API Keys

#### OpenAI (GPT)

* Truy cập website nền tảng OpenAI tại [platform.openai.com](https://platform.openai.com/) và đăng nhập (hoặc tạo) tài khoản OpenAI.
* Di chuột vào thanh tác vụ bên phải của trang và chọn “API Keys”.
* Nhấn “Create New Secret Key” để tạo API key mới. Sao chép và lưu trữ lại.

#### Google Cloud Vision

* Đăng nhập/Tạo tài khoản [Google Cloud](https://cloud.google.com/). Truy cập [Cloud Resource Manager](https://console.cloud.google.com/cloud-resource-manager) và nhấn “Create Project”. Đặt tên cho project.
* [Chọn project của bạn tại đây](https://console.cloud.google.com/welcome) sau đó chọn “Billing” rồi “Create Account”. Trong cửa sổ bật lên, chọn “Enable billing account” và chấp nhận ưu đãi tài khoản dùng thử miễn phí. “Account type” nên là cá nhân. Nhập thông tin thẻ tín dụng hợp lệ.
* Kích hoạt Google Cloud Vision cho project của bạn [tại đây](https://console.cloud.google.com/apis/library/vision.googleapis.com)
* Trong trang [Google Cloud Credentials](https://console.cloud.google.com/apis/credentials), nhấn “Create Credentials” rồi chọn API Key. Sao chép và lưu trữ lại.

## Cách hoạt động

### Phát hiện bong bóng thoại và phân đoạn văn bản

[bubble-and-text-detector](https://huggingface.co/ogkalu/comic-text-and-bubble-detector). Mô hình RT-DETR-v2 được huấn luyện trên 11.000 hình ảnh truyện tranh (Manga, Webtoon, truyện tranh phương Tây).
Phân đoạn bằng thuật toán dựa trên các bounding box được cung cấp từ mô hình phát hiện.

<img src="https://i.imgur.com/TlzVH3j.jpg" width="49%"> <img src="https://i.imgur.com/h18XrYT.jpg" width="49%">

### OCR

Mặc định:

* [manga-ocr](https://github.com/kha-white/manga-ocr) cho tiếng Nhật
* [Pororo](https://github.com/yunwoong7/korean_ocr_using_pororo) cho tiếng Hàn
* [PPOCRv5](https://www.paddleocr.ai/main/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5.html) cho các ngôn ngữ còn lại

Tùy chọn:

Các lựa chọn này có thể dùng cho bất kỳ ngôn ngữ được hỗ trợ nào. Yêu cầu API Key.

* [Google Cloud Vision](https://cloud.google.com/vision/docs/ocr)
* [Microsoft Azure Vision](https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/overview-ocr)

### Inpainting

Dùng để xóa văn bản đã được phân đoạn:

* Checkpoint [lama](https://github.com/advimman/lama) được fine-tune cho Manga/Anime từ [dreMaz](https://huggingface.co/dreMaz/AnimeMangaInpainting). Triển khai nhờ [lama-cleaner](https://github.com/Sanster/lama-cleaner)
* Mô hình dựa trên [AOT-GAN](https://arxiv.org/abs/2104.01431) bởi [zyddnys](https://github.com/zyddnys)

<img src="https://i.imgur.com/cVVGVXp.jpg" width="49%"> <img src="https://i.imgur.com/bLkPyqG.jpg" width="49%">

### Dịch thuật

Hiện tại hỗ trợ sử dụng GPT-4.1, DeepL, Claude-3,
Gemini-2.5, Yandex, Google Translate và Microsoft Azure Translator.

Tất cả các LLM đều được cung cấp toàn bộ văn bản của trang để hỗ trợ dịch tốt hơn.
Ngoài ra còn có tùy chọn cung cấp chính hình ảnh để có thêm ngữ cảnh.

### Tái tạo văn bản

Văn bản được tự động xuống dòng trong các bounding box lấy từ bong bóng thoại và vùng văn bản.

## Lời cảm ơn

* [https://github.com/Sanster/lama-cleaner](https://github.com/Sanster/lama-cleaner)
* [https://huggingface.co/dreMaz](https://huggingface.co/dreMaz)
* [https://github.com/yunwoong7/korean_ocr_using_pororo](https://github.com/yunwoong7/korean_ocr_using_pororo)
* [https://github.com/kha-white/manga-ocr](https://github.com/kha-white/manga-ocr)
* [https://github.com/JaidedAI/EasyOCR](https://github.com/JaidedAI/EasyOCR)
* [https://github.com/PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
* [https://github.com/RapidAI/RapidOCR](https://github.com/RapidAI/RapidOCR)
* [https://github.com/phenom-films/dayu_widgets](https://github.com/phenom-films/dayu_widgets)
