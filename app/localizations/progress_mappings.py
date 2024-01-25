def progress_mappings(key, lang_code, index, total_images):
    mappings = {
    "en": {
        "Forming TextBlocks": f"Forming TextBlocks. Image {index + 1} of {total_images}",
        "Text Removal": f"Text Removal. Image {index + 1} of {total_images}",
        "Translating": f"Translating. Image {index + 1} of {total_images}",
        "Rendering Text": f"Rendering Text. Image {index + 1} of {total_images}",
    },
    "ko": {
        "Forming TextBlocks": f"텍스트 블록 형성 중. 이미지 {index + 1}/{total_images}",
        "Text Removal": f"텍스트 제거 중. 이미지 {index + 1}/{total_images}",
        "Translating": f"번역 중. 이미지 {index + 1}/{total_images}",
        "Rendering Text": f"텍스트 렌더링 중. 이미지 {index + 1}/{total_images}",
    },
    "ja": {
        "Forming TextBlocks": f"テキストブロックを形成中。画像 {index + 1} / {total_images}",
        "Text Removal": f"テキスト削除中。画像 {index + 1} / {total_images}",
        "Translating": f"翻訳中。画像 {index + 1} / {total_images}",
        "Rendering Text": f"テキストレンダリング中。画像 {index + 1} / {total_images}",
    },
    "fr": {
        "Forming TextBlocks": f"Formation des blocs de texte. Image {index + 1} sur {total_images}",
        "Text Removal": f"Suppression de texte. Image {index + 1} sur {total_images}",
        "Translating": f"Traduction en cours. Image {index + 1} sur {total_images}",
        "Rendering Text": f"Rendu du texte. Image {index + 1} sur {total_images}",
    },
    "zh-CN": {
        "Forming TextBlocks": f"正在形成文本块。图像 {index + 1} / {total_images}",
        "Text Removal": f"正在移除文本。图像 {index + 1} / {total_images}",
        "Translating": f"正在翻译。图像 {index + 1} / {total_images}",
        "Rendering Text": f"正在渲染文本。图像 {index + 1} / {total_images}",
    },
    "zh-TW": {
        "Forming TextBlocks": f"正在形成文本區塊。圖像 {index + 1} / {total_images}",
        "Text Removal": f"正在移除文字。圖像 {index + 1} / {total_images}",
        "Translating": f"正在翻譯。圖像 {index + 1} / {total_images}",
        "Rendering Text": f"正在渲染文字。圖像 {index + 1} / {total_images}",
    },
    "ru": {
        "Forming TextBlocks": f"Формирование текстовых блоков.\nИзображение {index + 1} из {total_images}",
        "Text Removal": f"Удаление текста. Изображение {index + 1} из {total_images}",
        "Translating": f"Перевод. Изображение {index + 1} из {total_images}",
        "Rendering Text": f"Отрисовка текста. Изображение {index + 1} из {total_images}",
    },
    "de": {
        "Forming TextBlocks": f"Textblöcke werden gebildet. Bild {index + 1} von {total_images}",
        "Text Removal": f"Textentfernung. Bild {index + 1} von {total_images}",
        "Translating": f"Übersetzung. Bild {index + 1} von {total_images}",
        "Rendering Text": f"Text wird gerendert. Bild {index + 1} von {total_images}",
    },
    "nl": {
        "Forming TextBlocks": f"Tekstblokken vormen. Afbeelding {index + 1} van {total_images}",
        "Text Removal": f"Tekst verwijderen. Afbeelding {index + 1} van {total_images}",
        "Translating": f"Vertalen. Afbeelding {index + 1} van {total_images}",
        "Rendering Text": f"Tekst renderen. Afbeelding {index + 1} van {total_images}",
    },
    "es": {
        "Forming TextBlocks": f"Formando bloques de texto. Imagen {index + 1} de {total_images}",
        "Text Removal": f"Eliminación de texto. Imagen {index + 1} de {total_images}",
        "Translating": f"Traduciendo. Imagen {index + 1} de {total_images}",
        "Rendering Text": f"Renderizando texto. Imagen {index + 1} de {total_images}",
    },
    "it": {
        "Forming TextBlocks": f"Formazione dei blocchi di testo. Immagine {index + 1} di {total_images}",
        "Text Removal": f"Rimozione del testo. Immagine {index + 1} di {total_images}",
        "Translating": f"Traduzione in corso. Immagine {index + 1} di {total_images}",
        "Rendering Text": f"Rendering del testo. Immagine {index + 1} di {total_images}",
    }
}

    return mappings.get(lang_code, {}).get(key, "Status not found.")