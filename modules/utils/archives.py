import os
import zipfile, tarfile, py7zr, rarfile
import math
import img2pdf
from ebooklib import epub
import pymupdf

def is_image_file(filename):
    image_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')
    return filename.lower().endswith(image_extensions)

def extract_archive(file_path, extract_to):
    image_paths = []

    if file_path.lower().endswith(('.cbz', '.zip', '.epub')):
        archive = zipfile.ZipFile(file_path, 'r')
        archive.extractall(extract_to)
        image_paths = [os.path.join(extract_to, file) for file in archive.namelist() if is_image_file(file) and 'cover' not in file.lower()]
        archive.close()

    elif file_path.lower().endswith('.cbr'):
        archive = rarfile.RarFile(file_path, 'r')
        archive.extractall(extract_to)
        image_paths = [os.path.join(extract_to, file) for file in archive.namelist() if is_image_file(file)]
        archive.close()

    elif file_path.lower().endswith('.cbt'):
        archive = tarfile.open(file_path, 'r')
        archive.extractall(extract_to)
        image_paths = [os.path.join(extract_to, file.name) for file in archive.getmembers() if file.isfile() and is_image_file(file.name)]
        archive.close()

    elif file_path.lower().endswith('.cb7'):
        with py7zr.SevenZipFile(file_path, 'r') as archive:
            archive.extractall(extract_to)
            image_paths = [os.path.join(extract_to, entry) for entry in archive.getnames() if is_image_file(entry)]

    elif file_path.lower().endswith('.pdf'):
        pdf_file = pymupdf.open(file_path)
        total_images = sum(len(page.get_images(full=True)) for page in pdf_file)
        digits = math.floor(math.log10(total_images)) + 1
        
        index = 0
        for page_num in range(len(pdf_file)):
            page = pdf_file[page_num]
            image_list = page.get_images(full=True)
            for img_index, img in enumerate(image_list, start=1):
                index += 1
                xref = img[0]
                base_image = pdf_file.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                image_filename = f"{index:0{digits}d}.{image_ext}"
                image_path = os.path.join(extract_to, image_filename)
                with open(image_path, "wb") as image_file:
                    image_file.write(image_bytes)
                image_paths.append(image_path)
        pdf_file.close()

    else:
        raise ValueError("Unsupported file format")
    
    return image_paths

def make_cbz(input_dir, output_path="", output_dir="", output_base_name=""):
    if not output_path:
        output_path = os.path.join(output_dir, f"{output_base_name}_translated.cbz")
    
    with zipfile.ZipFile(output_path, 'w') as archive:
        for root, dirs, files in os.walk(input_dir):
            for file in files:
                if is_image_file(file):
                    file_path = os.path.join(root, file)
                    archive.write(file_path, arcname=os.path.relpath(file_path, input_dir))

def make_cb7(input_dir, output_path="", output_dir="", output_base_name=""):
    if not output_path:
        output_path = os.path.join(output_dir, f"{output_base_name}_translated.cb7")
    
    with py7zr.SevenZipFile(output_path, 'w') as archive:
        for root, dirs, files in os.walk(input_dir):
            for file in files:
                if is_image_file(file):
                    file_path = os.path.join(root, file)
                    archive.write(file_path, arcname=os.path.relpath(file_path, input_dir))

def make_pdf(input_dir, output_path="", output_dir="", output_base_name=""):
    if not output_path:
        output_path = os.path.join(output_dir, f"{output_base_name}_translated.pdf")

    image_paths = []
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if is_image_file(file):
                image_paths.append(os.path.join(root, file))

    with open(output_path, "wb") as f:
        f.write(img2pdf.convert(image_paths))

def make_epub(input_dir, lang, output_path="", output_dir="", output_base_name=""):
    if not output_path:
        output_path = os.path.join(output_dir, f"{output_base_name}_translated.epub")

    mime = {
        '.jpeg': 'jpeg',
        '.jpg': 'jpg',
        '.png': 'png',
        '.webp': 'webp',
        '.bmp': 'bmp'
    }
    book = epub.EpubBook()
    book.set_title(os.path.splitext(os.path.basename(output_path))[0])
    book.set_language(lang)

    content = [u'<html> <head></head> <body>']

    image_paths = []
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if is_image_file(file):
                image_paths.append(os.path.join(root, file))
    
    cover_image_path = image_paths[0]  # Use the first image as cover
    cover_ext = os.path.splitext(cover_image_path)[1]
    book.set_cover("cover" + cover_ext, open(cover_image_path, 'rb').read())

    for image_path in image_paths:
        file_name = os.path.basename(image_path)
        ext = os.path.splitext(image_path)[1]
        epub_image = epub.EpubItem(file_name= "images/" + file_name, content=open(image_path, 'rb').read(), media_type=f"image/{mime[ext]}")
        book.add_item(epub_image)
        content.append(f'<img src="{epub_image.file_name}"/>')

    content.append('</body> </html>')
    c1 = epub.EpubHtml(title='Images', file_name='images.xhtml', lang=lang)
    c1.content = ''.join(content)

    book.add_item(c1)
    book.spine = ['nav', c1]

    epub.write_epub(output_path, book, {})

def make(input_dir, output_path="", save_as_ext="", output_dir="", output_base_name="", trg_lng=""):
    if not output_path and (not output_dir or not output_base_name):
        raise ValueError("Either output_path or both output_dir and output_base_name must be provided")
    
    if output_path:
        save_as_ext = os.path.splitext(output_path)[1]

    if save_as_ext in ['.cbz', '.zip']:
        make_cbz(input_dir, output_path, output_dir, output_base_name)
    elif save_as_ext == '.cb7':
        make_cb7(input_dir, output_path, output_dir, output_base_name)
    elif save_as_ext == '.pdf':
        make_pdf(input_dir, output_path, output_dir, output_base_name)
    elif save_as_ext == '.epub':
        make_epub(input_dir, trg_lng, output_path, output_dir, output_base_name)
    else:
        raise ValueError(f"Unsupported save_as_ext: {save_as_ext}")
