import numpy as np
from PySide6 import QtGui
from PySide6.QtCore import Qt
from modules.utils.textblock import TextBlock

class ProjectEncoder:
    def __init__(self):
        self.encoders = [
            (np.ndarray, self.encode_numpy_array),
            (TextBlock, self.encode_textblock),
            (QtGui.QColor, self.encode_qcolor),
            (QtGui.QPainterPath, self.encode_qpainterpath),
            (Qt.AlignmentFlag, self.encode_alignment_flag),
            (tuple, self.encode_tuple),  
        ]

    def encode(self, obj):
        if isinstance(obj, np.generic):
            return self.encode_numpy_scalar(obj)
        for cls, encoder in self.encoders:
            if isinstance(obj, cls):
                return encoder(obj)
        return obj
    
    @staticmethod
    def encode_numpy_scalar(obj):
        return obj.item()
    
    @staticmethod
    def encode_tuple(obj):
        return {
            'type': 'tuple',
            'data': list(obj)
        }

    @staticmethod
    def encode_numpy_array(obj):
        if obj.ndim == 0:  # scalar numpy array
            return {
                'type': 'numpy.scalar',
                'data': obj.item(),
                'dtype': str(obj.dtype)
            }
        return {
            'type': 'numpy.ndarray',
            'data': obj.tobytes(),
            'shape': obj.shape,
            'dtype': str(obj.dtype)
        }

    @staticmethod
    def encode_textblock(obj):
        return {
            'type': 'textblock',
            'data': obj.__dict__
        }

    @staticmethod
    def encode_qcolor(obj):
        return {
            'type': 'qcolor',
            'data': obj.name(QtGui.QColor.HexArgb)
        }

    @staticmethod
    def encode_qpainterpath(obj):
        path_str = ""
        i = 0
        while i < obj.elementCount():
            e = obj.elementAt(i)
            if e.type == QtGui.QPainterPath.ElementType.MoveToElement:
                path_str += f"M {e.x} {e.y} "
            elif e.type == QtGui.QPainterPath.ElementType.LineToElement:
                path_str += f"L {e.x} {e.y} "
            elif e.type == QtGui.QPainterPath.ElementType.CurveToElement:
                if i + 2 < obj.elementCount():
                    c1, c2 = obj.elementAt(i + 1), obj.elementAt(i + 2)
                    path_str += f"C {e.x} {e.y} {c1.x} {c1.y} {c2.x} {c2.y} "
                    i += 2
            i += 1
        return {
            'type': 'qpainterpath',
            'data': path_str.strip()
        }

    @staticmethod
    def encode_alignment_flag(obj):
        return {
            'type': 'alignmentflag',
            'data': obj.value
        }
    

class ProjectDecoder:
    def __init__(self):
        self.decoders = {
            'numpy.ndarray': self.decode_numpy_array,
            'numpy.scalar': self.decode_numpy_scalar,
            'textblock': self.decode_textblock,
            'qcolor': self.decode_qcolor,
            'qpainterpath': self.decode_qpainterpath,
            'alignmentflag': self.decode_alignment_flag,
            'tuple': self.decode_tuple,  
        }

    def decode(self, obj):
        if isinstance(obj, dict) and 'type' in obj:
            decoder = self.decoders.get(obj['type'])
            if decoder:
                return decoder(obj)
        return obj
    
    @staticmethod
    def decode_numpy_scalar(obj):
        return np.dtype(obj['dtype']).type(obj['data'])
    
    @staticmethod
    def decode_tuple(obj):
        return tuple(obj['data'])

    @staticmethod
    def decode_numpy_array(obj):
        # Decode the base64-encoded data
        binary_data = obj['data']
        dtype = np.dtype(obj['dtype'])
        shape = tuple(obj['shape'])
        array = np.frombuffer(binary_data, dtype=dtype)
        if array.size == 4:
            x1, y1, x2, y2 = array
            return np.array([x1, y1, x2, y2], dtype=dtype)
        elif shape != ():  
            return array.reshape(shape)
        else:
            return array.reshape(-1, 4)

    @staticmethod
    def decode_textblock(obj):
        return TextBlock(
            text_bbox=obj['data'].get('xyxy'),
            bubble_bbox=obj['data'].get('bubble_xyxy'),
            text_class=obj['data'].get('text_class', ""),
            inpaint_bboxes=obj['data'].get('inpaint_bboxes'),
            lines=obj['data'].get('lines'),
            text_segm_points=obj['data'].get('segm_pts'),
            text=obj['data'].get('text'),
            translation=obj['data'].get('translation', ""),
            line_spacing=obj['data'].get('line_spacing', 1),
            alignment=obj['data'].get('alignment', ''),
            source_lang=obj['data'].get('source_lang', ""),
            target_lang=obj['data'].get('target_lang', ""),
            min_font_size=obj['data'].get('min_font_size', 0),
            max_font_size=obj['data'].get('max_font_size', 0),
            font_color=obj['data'].get('font_color', "")
        )

    @staticmethod
    def decode_qcolor(obj):
        return QtGui.QColor(obj['data'])

    @staticmethod
    def decode_qpainterpath(obj):
        path = QtGui.QPainterPath()
        elements = obj['data'].split()
        i = 0
        while i < len(elements):
            cmd = elements[i]
            i += 1
            if cmd == 'M':
                path.moveTo(float(elements[i]), float(elements[i+1]))
                i += 2
            elif cmd == 'L':
                path.lineTo(float(elements[i]), float(elements[i+1]))
                i += 2
            elif cmd == 'C':
                path.cubicTo(
                    float(elements[i]), float(elements[i+1]),
                    float(elements[i+2]), float(elements[i+3]),
                    float(elements[i+4]), float(elements[i+5])
                )
                i += 6
        return path

    @staticmethod
    def decode_alignment_flag(obj):
        return Qt.AlignmentFlag(obj['data'])
    
def ensure_string_keys(d):
    """ Recursively ensures that all dictionary keys are strings. """
    if isinstance(d, dict):
        return {str(k): ensure_string_keys(v) for k, v in d.items()}
    return d