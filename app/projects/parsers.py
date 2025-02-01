import numpy as np
from PySide6 import QtGui
from PySide6.QtCore import Qt
from modules.utils.textblock import TextBlock
from ..ui.canvas.text_item import OutlineInfo, OutlineType

class ProjectEncoder:
    def __init__(self):
        self.encoders = [
            (np.ndarray, self.encode_numpy_array),
            (TextBlock, self.encode_textblock),
            (QtGui.QColor, self.encode_qcolor),
            (QtGui.QPainterPath, self.encode_qpainterpath),
            (Qt.AlignmentFlag, self.encode_alignment_flag),
            (tuple, self.encode_tuple), 
            (OutlineInfo, self.encode_outline_info),
            (Qt.LayoutDirection, self.encode_layout_flag)
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
        data = obj.__dict__
        return {
            'type': 'textblock',
            'data': data
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
    
    @staticmethod
    def encode_outline_info(obj):
        return {
            'type': 'selection_outline_info',
            'data': {
                'start': obj.start,
                'end': obj.end,
                'color': ProjectEncoder.encode_qcolor(obj.color),
                'width': obj.width,
                'type': obj.type.value
            }
        }
    

    @staticmethod
    def encode_layout_flag(obj):
        return {
            'type': 'layoutflag',
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
            'selection_outline_info': self.decode_outline_info,
            'layoutflag': self.decode_layout_flag,
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
        text_block = TextBlock()
        text_block.__dict__.update(obj['data'])  
        return text_block

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
    
    @staticmethod
    def decode_outline_info(obj):
        data = obj['data']
        return OutlineInfo(
            start=data['start'],
            end=data['end'],
            color=data['color'],
            width=data['width'],
            type=OutlineType(data['type']) if 'type' in data else OutlineType.Selection
        )
    
    @staticmethod
    def decode_layout_flag(obj):
        return Qt.LayoutDirection(obj['data'])
    
def ensure_string_keys(d):
    """ Recursively ensures that all dictionary keys are strings. """
    if isinstance(d, dict):
        return {str(k): ensure_string_keys(v) for k, v in d.items()}
    return d