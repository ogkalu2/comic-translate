import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Any

class ImageSaveRenderer:
    def __init__(self, cv2_image):
        self.cv2_image = cv2_image
        self.image = self.cv2_to_pil(cv2_image)
        self.draw = None
        self.text_items = []

    def cv2_to_pil(self, cv2_img):
        # Convert BGR to RGB
        rgb_image = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb_image)

    def pil_to_cv2(self, pil_image):
        # Convert PIL image to cv2 format
        numpy_image = np.array(pil_image)
        return cv2.cvtColor(numpy_image, cv2.COLOR_RGB2BGR)

    def add_state_to_image(self, state):
        self.text_items = []
        for text_block in state.get('text_items_state', []):
            self.text_items.append(text_block)

    def render_text(self, text_block: Dict[str, Any], scale_factor: float = 2.0):
        # Create a font object
        font = ImageFont.truetype(text_block['font_family'], int(text_block['font_size'] * scale_factor))

        # Calculate text position
        pos_x, pos_y = text_block['position']
        
        # Apply transformations
        if text_block.get('transform_origin'):
            origin_x, origin_y = text_block['transform_origin']
            # In PIL, we handle rotation around a point by adjusting the text position
            if text_block.get('rotation', 0) != 0:
                angle = text_block['rotation']
                # TODO: Implement complex rotation with origin point if needed

        # Draw text outline if specified
        if text_block.get('outline_width', 0) > 0:
            outline_width = int(text_block['outline_width'] * scale_factor)
            outline_color = text_block['outline_color']
            # Draw outline by offsetting text in all directions
            for dx in range(-outline_width, outline_width + 1):
                for dy in range(-outline_width, outline_width + 1):
                    if dx == 0 and dy == 0:
                        continue
                    self.draw.text(
                        (pos_x * scale_factor + dx, pos_y * scale_factor + dy),
                        text_block['text'],
                        font=font,
                        fill=outline_color,
                        align=text_block['alignment']
                    )

        # Draw main text
        self.draw.text(
            (pos_x * scale_factor, pos_y * scale_factor),
            text_block['text'],
            font=font,
            fill=text_block['text_color'],
            align=text_block['alignment']
        )

    def render_to_image(self):
        # Create a high-resolution image
        scale_factor = 2
        width, height = self.image.size
        scaled_image = Image.new('RGB', (width * scale_factor, height * scale_factor))
        scaled_image.paste(self.image.resize((width * scale_factor, height * scale_factor), Image.Resampling.LANCZOS))
        
        # Create a drawing context for the scaled image
        self.draw = ImageDraw.Draw(scaled_image)
        
        # Render all text items
        for text_block in self.text_items:
            self.render_text(text_block, scale_factor)
        
        # Scale back down to original size with antialiasing
        final_image = scaled_image.resize((width, height), Image.Resampling.LANCZOS)
        
        # Convert back to cv2 format
        return self.pil_to_cv2(final_image)

    def save_image(self, output_path):
        final_image = self.render_to_image()
        cv2.imwrite(output_path, final_image)

