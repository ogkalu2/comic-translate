from flask import Flask, request, Response, render_template

from main import Settings
from modules.batch_processor import BatchProcessor
from PIL import Image, ImageDraw
import io
import numpy as np
import cv2

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('upload.html')

@app.route('/covert_image', methods=['POST'])
def covert_image():
    input_image = request.files.get('image')
    if not input_image:
        return 'No image uploaded', 400
        
    # 将上传的文件转换为OpenCV格式
    file_bytes = np.asarray(bytearray(input_image.read()), dtype=np.uint8)
    image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    
    target_language = 'English'  # 'Chinese'
    settings = Settings(target_language)
    processor = BatchProcessor()
    flag, output_image = processor.process_one_image(settings, image, 'Japanese', target_language)
    
    if not flag:
        return 'Image processing failed', 500
        
    # 将OpenCV图像转换为PIL格式
    output_image_rgb = cv2.cvtColor(output_image, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(output_image_rgb)
    
    img_io = io.BytesIO()
    pil_image.save(img_io, 'PNG')
    img_io.seek(0)

    return Response(img_io, mimetype='image/png')

if __name__ == '__main__':
    app.run(debug=True)