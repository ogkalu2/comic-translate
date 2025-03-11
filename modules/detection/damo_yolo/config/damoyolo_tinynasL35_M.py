import os
from modules.detection.damo_yolo.config.base import BaseConfig

current_file_dir = os.path.dirname(os.path.abspath(__file__))
damo_root =  os.path.abspath(os.path.join(current_file_dir, '..'))

class Config(BaseConfig):
    def __init__(self):
        super().__init__()

        # backbone
        structure = self.read_structure(
             os.path.join(damo_root, 'base_models/backbones/nas_backbones/tinynas_L35_kxkx.txt')
            )
        TinyNAS = {
            'name': 'TinyNAS_csp',
            'net_structure_str': structure,
            'out_indices': (2, 3, 4),
            'with_spp': True,
            'use_focus': True,
            'act': 'silu',
            'reparam': True,
        }

        self.model.backbone = TinyNAS

        GiraffeNeckV2 = {
            'name': 'GiraffeNeckV2',
            'depth': 1.5,
            'hidden_ratio': 1.0,
            'in_channels': [128, 256, 512],
            'out_channels': [128, 256, 512],
            'act': 'silu',
            'spp': False,
            'block_name': 'BasicBlock_3x3_Reverse',
        }

        self.model.neck = GiraffeNeckV2

        ZeroHead = {
            'name': 'ZeroHead',
            'num_classes': 3,
            'in_channels': [128, 256, 512],
            'stacked_convs': 0,
            'reg_max': 16,
            'act': 'silu',
            'nms_conf_thre': 0.05,
            'nms_iou_thre': 0.7,
            'legacy': False,
        }
        self.model.head = ZeroHead

