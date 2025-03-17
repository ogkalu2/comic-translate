---
language: ja
tags:
- image-to-text
license: apache-2.0
datasets:
- manga109s
---

# Manga OCR

Optical character recognition for Japanese text, with the main focus being Japanese manga.

It uses [Vision Encoder Decoder](https://huggingface.co/docs/transformers/model_doc/vision-encoder-decoder) framework.

Manga OCR can be used as a general purpose printed Japanese OCR, but its main goal was to provide a high quality
text recognition, robust against various scenarios specific to manga:
- both vertical and horizontal text
- text with furigana
- text overlaid on images
- wide variety of fonts and font styles
- low quality images

Code is available [here](https://github.com/kha-white/manga_ocr).
