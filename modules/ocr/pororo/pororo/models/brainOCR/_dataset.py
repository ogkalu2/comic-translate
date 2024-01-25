import os

from natsort import natsorted
from PIL import Image
from torch.utils.data import Dataset


class RawDataset(Dataset):

    def __init__(self, root, imgW, imgH):
        self.imgW = imgW
        self.imgH = imgH
        self.image_path_list = []
        for dirpath, _, filenames in os.walk(root):
            for name in filenames:
                _, ext = os.path.splitext(name)
                ext = ext.lower()
                if ext in (".jpg", ".jpeg", ".png"):
                    self.image_path_list.append(os.path.join(dirpath, name))

        self.image_path_list = natsorted(self.image_path_list)
        self.nSamples = len(self.image_path_list)

    def __len__(self):
        return self.nSamples

    def __getitem__(self, index):
        try:
            img = Image.open(self.image_path_list[index]).convert("L")

        except IOError:
            print(f"Corrupted image for {index}")
            img = Image.new("L", (self.imgW, self.imgH))

        return img, self.image_path_list[index]
