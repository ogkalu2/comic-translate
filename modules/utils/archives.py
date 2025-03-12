import os, re
import zipfile
import math
import io
from PIL import Image

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', str(s))]

def is_image_file(filename):
    image_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')
    return filename.lower().endswith(image_extensions)

def extract_archive(file_path: str, extract_to: str):
    image_paths = []
    file_lower = file_path.lower()

    if file_lower.endswith(('.cbz', '.zip', '.epub')):
        with zipfile.ZipFile(file_path, 'r') as archive:
            for file in archive.namelist():
                if is_image_file(file):
                    archive.extract(file, extract_to)
                    image_paths.append(os.path.join(extract_to, file))
    
    elif file_lower.endswith(('.cbr', '.rar')):
        import rarfile
        with rarfile.RarFile(file_path, 'r') as archive:
            for file in archive.namelist():
                if is_image_file(file):
                    archive.extract(file, extract_to)
                    image_paths.append(os.path.join(extract_to, file))
    
    elif file_lower.endswith(('.cbt', '.tar')):
        import tarfile
        with tarfile.open(file_path, 'r') as archive:
            for member in archive:
                if member.isfile() and is_image_file(member.name):
                    archive.extract(member, extract_to)
                    image_paths.append(os.path.join(extract_to, member.name))
    
    elif file_lower.endswith(('.cb7', '.7z')):
        import py7zr
        with py7zr.SevenZipFile(file_path, 'r') as archive:
            for entry in archive.getnames():
                if is_image_file(entry):
                    archive.extract(targets=[entry], path=extract_to)
                    image_paths.append(os.path.join(extract_to, entry))

    elif file_path.lower().endswith('.pdf'):
        import pdfplumber

        with pdfplumber.open(file_path) as pdf:
            # Count total pages for consistent indexing
            total_pages = len(pdf.pages)
            digits = math.floor(math.log10(total_pages)) + 1 if total_pages > 0 else 1
            
            index = 0
            for page_num, page in enumerate(pdf.pages):
                index += 1
                image_extracted = False
                
                # Try to extract embedded image first
                if page.images and len(page.images) > 0:
                    try:
                        img = page.images[0]  # Assuming one image per page
                        if "stream" in img:
                            image_bytes = img["stream"].get_data()
                            
                            # Determine image extension
                            try:
                                pil_img = Image.open(io.BytesIO(image_bytes))
                                image_ext = pil_img.format.lower()
                                image_filename = f"{index:0{digits}d}.{image_ext}"
                                image_path = os.path.join(extract_to, image_filename)
                                
                                with open(image_path, "wb") as image_file:
                                    image_file.write(image_bytes)
                                image_paths.append(image_path)
                                image_extracted = True
                            except Exception as e:
                                print(f"{page_num+1}: {e}. Resorting to Page Rendering")

                    except Exception as e:
                        print(f"Error extracting image from page {page_num+1}: {e}")
                
                # If extraction failed, render the whole page as an image
                if not image_extracted:
                    try:
                        page_img = page.to_image()
                        image_filename = f"{index:0{digits}d}.png"  # Default to PNG for rendered pages
                        image_path = os.path.join(extract_to, image_filename)
                        page_img.save(image_path)
                        image_paths.append(image_path)
                    except Exception as e:
                        print(f"Failed to render page {page_num+1} as image: {e}")
    else:
        raise ValueError("Unsupported file format")
    
    return sorted(image_paths, key=natural_sort_key)

def make_cbz(input_dir, output_path='', output_dir='', output_base_name='', save_as_ext='.cbz'):
    if not output_path:
        output_path = os.path.join(output_dir, f"{output_base_name}_translated{save_as_ext}")
    
    with zipfile.ZipFile(output_path, 'w') as archive:
        for root, dirs, files in os.walk(input_dir):
            for file in files:
                if is_image_file(file):
                    file_path = os.path.join(root, file)
                    archive.write(file_path, arcname=os.path.relpath(file_path, input_dir))

def make_cb7(input_dir, output_path="", output_dir="", output_base_name=""):
    if not output_path:
        output_path = os.path.join(output_dir, f"{output_base_name}_translated.cb7")

    import py7zr
    with py7zr.SevenZipFile(output_path, 'w') as archive:
        for root, dirs, files in os.walk(input_dir):
            for file in files:
                if is_image_file(file):
                    file_path = os.path.join(root, file)
                    archive.write(file_path, arcname=os.path.relpath(file_path, input_dir))

def make_pdf(input_dir, output_path="", output_dir="", output_base_name=""):
    import img2pdf
    
    if not output_path:
        output_path = os.path.join(output_dir, f"{output_base_name}_translated.pdf")

    image_paths = []
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if is_image_file(file):
                image_paths.append(os.path.join(root, file))
    
    def get_number(filepath):
        basename = os.path.splitext(os.path.basename(filepath))[0]
        import re
        # Match either:
        # - numbers with or without padding (001, 01, 1)
        # - numbers with or without padding followed by _translated
        match = re.match(r'^(0*\d+)(_translated)?$', basename)
        if match:
            # Extract and return the number if it matches our pattern
            return int(match.group(1))  # int('002') will return 2
        return None
    
    # Sort files, keeping non-matching files in original order
    sorted_paths = sorted(
        image_paths,
        key=lambda x: (get_number(x) is None, get_number(x))
    )
    
    with open(output_path, "wb") as f:
        f.write(img2pdf.convert(sorted_paths))

def make(input_dir, output_path="", save_as_ext="", output_dir="", output_base_name=""):
    if not output_path and (not output_dir or not output_base_name):
        raise ValueError("Either output_path or both output_dir and output_base_name must be provided")
    
    if output_path:
        save_as_ext = os.path.splitext(output_path)[1]

    if save_as_ext in ['.cbz', '.zip']:
        make_cbz(input_dir, output_path, output_dir, output_base_name, save_as_ext)
    elif save_as_ext == '.cb7':
        make_cb7(input_dir, output_path, output_dir, output_base_name)
    elif save_as_ext == '.pdf':
        make_pdf(input_dir, output_path, output_dir, output_base_name)
    else:
        raise ValueError(f"Unsupported save_as_ext: {save_as_ext}")
