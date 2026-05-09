# import imkit as imk
# import numpy as np
# import platform
# from PIL import ImageFont, ImageDraw, Image
# from matplotlib import pyplot as plt


# def plt_imshow(title='image', img=None, figsize=(8, 5)):
#     plt.figure(figsize=figsize)

#     if type(img) is str:
#         img = imk.read_image(img)

#     if type(img) == list:
#         if type(title) == list:
#             titles = title
#         else:
#             titles = []

#             for i in range(len(img)):
#                 titles.append(title)

#         for i in range(len(img)):
#             if len(img[i].shape) <= 2:
#                 rgbImg = np.stack([img[i], img[i], img[i]], axis=2)  # Convert grayscale to RGB
#             else:
#                 rgbImg = img[i]  # Already in RGB format

#             plt.subplot(1, len(img), i + 1), plt.imshow(rgbImg)
#             plt.title(titles[i])
#             plt.xticks([]), plt.yticks([])

#         plt.show()
#     else:
#         if len(img.shape) < 3:
#             rgbImg = np.stack([img, img, img], axis=2)  # Convert grayscale to RGB
#         else:
#             rgbImg = img  # Already in RGB format

#         plt.imshow(rgbImg)
#         plt.title(title)
#         plt.xticks([]), plt.yticks([])
#         plt.show()


# def put_text(image, text, x, y, color=(0, 255, 0), font_size=22):
#     if type(image) == np.ndarray:
#         # Image is already in RGB format, no conversion needed
#         image = Image.fromarray(image)

#     if platform.system() == 'Darwin':
#         font = 'AppleGothic.ttf'
#     elif platform.system() == 'Windows':
#         font = 'malgun.ttf'

#     image_font = ImageFont.truetype(font, font_size)
#     font = ImageFont.load_default()
#     draw = ImageDraw.Draw(image)

#     draw.text((x, y), text, font=image_font, fill=color)

#     numpy_image = np.array(image)
#     # Return RGB image (no BGR conversion needed)
#     return numpy_image