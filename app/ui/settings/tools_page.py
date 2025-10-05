from PySide6 import QtWidgets

from ..dayu_widgets.check_box import MCheckBox
from ..dayu_widgets.label import MLabel
from ..dayu_widgets.spin_box import MSpinBox
from .utils import create_title_and_combo, set_combo_box_width


class ToolsPage(QtWidgets.QWidget):
    def __init__(
        self,
        translators: list[str],
        ocr_engines: list[str],
        detectors: list[str],
        inpainters: list[str],
        inpaint_strategy: list[str],
        image_enhancers: list[str] | None = None,
        waifu2x_models: list[str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.translators = translators
        self.ocr_engines = ocr_engines
        self.detectors = detectors
        self.inpainters = inpainters
        self.inpaint_strategy = inpaint_strategy
        self.image_enhancers = image_enhancers or [
            self.tr("Disabled"),
            self.tr("Waifu2x NCNN Vulkan (CLI)"),
            self.tr("Waifu2x Converter (Python)"),
            self.tr("Waifu2x Unlimited (Web API)"),
        ]
        self.engine_codes = {
            self.tr("Disabled"): "disabled",
            self.tr("Waifu2x NCNN Vulkan (CLI)"): "waifu2x-ncnn-vulkan",
            self.tr("Waifu2x Converter (Python)"): "waifu2x-converter",
            self.tr("Waifu2x Unlimited (Web API)"): "waifu2x-unlimited",
        }
        self.waifu2x_models = waifu2x_models or [
            self.tr("CUnet (Anime Art)"),
            self.tr("UpConv-7 Anime"),
            self.tr("UpConv-7 Photo"),
        ]
        self.noise_levels = [
            self.tr("Disable"),
            self.tr("Low"),
            self.tr("Medium"),
            self.tr("High"),
            self.tr("Highest"),
        ]
        self.scale_levels = [
            self.tr("1x"),
            self.tr("2x"),
            self.tr("4x"),
        ]

        layout = QtWidgets.QVBoxLayout(self)

        translator_widget, self.translator_combo = create_title_and_combo(
            self.tr("Translator"),
            self.translators,
            h4=True,
        )
        set_combo_box_width(self.translator_combo, self.translators)

        enhancer_widget, self.image_enhancer_engine_combo = create_title_and_combo(
            self.tr("Image Enhancer"),
            self.image_enhancers,
            h4=True,
        )
        set_combo_box_width(self.image_enhancer_engine_combo, self.image_enhancers)
        if self.tr("Waifu2x NCNN Vulkan (CLI)") in self.image_enhancers:
            self.image_enhancer_engine_combo.setCurrentText(
                self.tr("Waifu2x NCNN Vulkan (CLI)")
            )
        for idx, option in enumerate(self.image_enhancers):
            self.image_enhancer_engine_combo.setItemData(
                idx, self.engine_codes.get(option, option)
            )

        self.image_enhancer_model_widget, self.image_enhancer_model_combo = create_title_and_combo(
            self.tr("Waifu2x Model"),
            self.waifu2x_models,
            h4=False,
        )
        set_combo_box_width(self.image_enhancer_model_combo, self.waifu2x_models)

        self.image_enhancer_noise_widget, self.image_enhancer_noise_combo = create_title_and_combo(
            self.tr("Noise Reduction"),
            self.noise_levels,
            h4=False,
        )
        set_combo_box_width(self.image_enhancer_noise_combo, self.noise_levels)
        self.image_enhancer_noise_combo.setCurrentText(self.tr("Medium"))

        self.image_enhancer_scale_widget, self.image_enhancer_scale_combo = create_title_and_combo(
            self.tr("Upscale"),
            self.scale_levels,
            h4=False,
        )
        set_combo_box_width(self.image_enhancer_scale_combo, self.scale_levels)
        self.image_enhancer_scale_combo.setCurrentText(self.tr("2x"))

        self.image_enhancer_tta_checkbox = MCheckBox(self.tr("Enable TTA"))
        self.image_enhancer_keep_size_checkbox = MCheckBox(
            self.tr("Keep Original Size")
        )
        self.image_enhancer_keep_size_checkbox.setChecked(True)

        self.image_enhancer_tile_widget = QtWidgets.QWidget()
        tile_layout = QtWidgets.QHBoxLayout(self.image_enhancer_tile_widget)
        tile_layout.setContentsMargins(0, 0, 0, 0)
        tile_label = MLabel(self.tr("Tile Size"))
        self.image_enhancer_tile_spinbox = MSpinBox().small()
        self.image_enhancer_tile_spinbox.setRange(0, 2048)
        self.image_enhancer_tile_spinbox.setValue(0)
        self.image_enhancer_tile_spinbox.setFixedWidth(70)
        tile_layout.addWidget(tile_label)
        tile_layout.addStretch(1)
        tile_layout.addWidget(self.image_enhancer_tile_spinbox)

        # Backwards-compatible alias expected by legacy code paths
        self.image_enhancer_combo = self.image_enhancer_engine_combo

        ocr_widget, self.ocr_combo = create_title_and_combo(
            self.tr("OCR"),
            self.ocr_engines,
            h4=True,
        )
        set_combo_box_width(self.ocr_combo, self.ocr_engines)

        detector_widget, self.detector_combo = create_title_and_combo(
            self.tr("Text Detector"),
            self.detectors,
            h4=True,
        )
        set_combo_box_width(self.detector_combo, self.detectors)

        inpainting_label = MLabel(self.tr("Inpainting")).h4()
        inpainter_widget, self.inpainter_combo = create_title_and_combo(
            self.tr("Inpainter"),
            self.inpainters,
            h4=False,
        )
        set_combo_box_width(self.inpainter_combo, self.inpainters)
        self.inpainter_combo.setCurrentText(self.tr("AOT"))

        inpaint_strategy_widget, self.inpaint_strategy_combo = create_title_and_combo(
            self.tr("HD Strategy"),
            self.inpaint_strategy,
            h4=False,
        )
        set_combo_box_width(self.inpaint_strategy_combo, self.inpaint_strategy)
        self.inpaint_strategy_combo.setCurrentText(self.tr("Resize"))

        self.hd_strategy_widgets = QtWidgets.QWidget()
        self.hd_strategy_layout = QtWidgets.QVBoxLayout(self.hd_strategy_widgets)

        self.resize_widget = QtWidgets.QWidget()
        about_resize_layout = QtWidgets.QVBoxLayout(self.resize_widget)
        resize_layout = QtWidgets.QHBoxLayout()
        resize_label = MLabel(self.tr("Resize Limit:"))
        about_resize_label = MLabel(
            self.tr(
                "Resize the longer side of the image to a specific size,\n"
                "then do inpainting on the resized image."
            )
        )
        self.resize_spinbox = MSpinBox().small()
        self.resize_spinbox.setFixedWidth(70)
        self.resize_spinbox.setMaximum(3000)
        self.resize_spinbox.setValue(960)
        resize_layout.addWidget(resize_label)
        resize_layout.addWidget(self.resize_spinbox)
        resize_layout.addStretch()
        about_resize_layout.addWidget(about_resize_label)
        about_resize_layout.addLayout(resize_layout)
        about_resize_layout.setContentsMargins(5, 5, 5, 5)
        about_resize_layout.addStretch()

        self.crop_widget = QtWidgets.QWidget()
        crop_layout = QtWidgets.QVBoxLayout(self.crop_widget)
        about_crop_label = MLabel(
            self.tr("Crop masking area from the original image to do inpainting.")
        )
        crop_margin_layout = QtWidgets.QHBoxLayout()
        crop_margin_label = MLabel(self.tr("Crop Margin:"))
        self.crop_margin_spinbox = MSpinBox().small()
        self.crop_margin_spinbox.setFixedWidth(70)
        self.crop_margin_spinbox.setMaximum(3000)
        self.crop_margin_spinbox.setValue(512)
        crop_margin_layout.addWidget(crop_margin_label)
        crop_margin_layout.addWidget(self.crop_margin_spinbox)
        crop_margin_layout.addStretch()

        crop_trigger_layout = QtWidgets.QHBoxLayout()
        crop_trigger_label = MLabel(self.tr("Crop Trigger Size:"))
        self.crop_trigger_spinbox = MSpinBox().small()
        self.crop_trigger_spinbox.setFixedWidth(70)
        self.crop_trigger_spinbox.setMaximum(3000)
        self.crop_trigger_spinbox.setValue(512)
        crop_trigger_layout.addWidget(crop_trigger_label)
        crop_trigger_layout.addWidget(self.crop_trigger_spinbox)
        crop_trigger_layout.addStretch()

        crop_layout.addWidget(about_crop_label)
        crop_layout.addLayout(crop_margin_layout)
        crop_layout.addLayout(crop_trigger_layout)
        crop_layout.setContentsMargins(5, 5, 5, 5)

        self.hd_strategy_layout.addWidget(self.resize_widget)
        self.hd_strategy_layout.addWidget(self.crop_widget)

        self.resize_widget.show()
        self.crop_widget.hide()
        self.inpaint_strategy_combo.currentIndexChanged.connect(
            self._update_hd_strategy_widgets
        )

        self.use_gpu_checkbox = MCheckBox(self.tr("Use GPU"))

        layout.addWidget(translator_widget)
        layout.addWidget(enhancer_widget)
        layout.addWidget(self.image_enhancer_model_widget)
        layout.addWidget(self.image_enhancer_noise_widget)
        layout.addWidget(self.image_enhancer_scale_widget)
        layout.addWidget(self.image_enhancer_tta_checkbox)
        layout.addWidget(self.image_enhancer_keep_size_checkbox)
        layout.addWidget(self.image_enhancer_tile_widget)
        layout.addSpacing(10)

        self.image_enhancer_engine_combo.currentIndexChanged.connect(
            self._update_enhancer_controls
        )
        self._update_enhancer_controls(self.image_enhancer_engine_combo.currentIndex())
        layout.addWidget(detector_widget)
        layout.addSpacing(10)
        layout.addWidget(ocr_widget)
        layout.addSpacing(10)
        layout.addWidget(inpainting_label)
        layout.addWidget(inpainter_widget)
        layout.addWidget(inpaint_strategy_widget)
        layout.addWidget(self.hd_strategy_widgets)
        layout.addSpacing(10)
        layout.addWidget(self.use_gpu_checkbox)
        layout.addStretch(1)

        self._update_hd_strategy_widgets(self.inpaint_strategy_combo.currentIndex())

    def _update_hd_strategy_widgets(self, index: int) -> None:
        strategy = self.inpaint_strategy_combo.itemText(index)
        self.resize_widget.setVisible(strategy == self.tr("Resize"))
        self.crop_widget.setVisible(strategy == self.tr("Crop"))
        if strategy == self.tr("Original"):
            self.hd_strategy_widgets.setFixedHeight(0)
        else:
            self.hd_strategy_widgets.setFixedHeight(
                self.hd_strategy_widgets.sizeHint().height()
            )

    def _update_enhancer_controls(self, index: int) -> None:
        engine_code = self.image_enhancer_engine_combo.itemData(index)
        if engine_code is None:
            engine_code = self.image_enhancer_engine_combo.itemText(index)
        engine_code = str(engine_code).lower()

        disabled = engine_code in {"", "disabled", "none", "off"}
        enable_tile = engine_code == "waifu2x-ncnn-vulkan"

        for widget in (
            self.image_enhancer_model_widget,
            self.image_enhancer_noise_widget,
            self.image_enhancer_scale_widget,
        ):
            widget.setEnabled(not disabled)

        for combo in (
            self.image_enhancer_model_combo,
            self.image_enhancer_noise_combo,
            self.image_enhancer_scale_combo,
        ):
            combo.setEnabled(not disabled)

        self.image_enhancer_tta_checkbox.setEnabled(not disabled)
        self.image_enhancer_keep_size_checkbox.setEnabled(not disabled)
        self.image_enhancer_tile_widget.setEnabled(enable_tile)
        self.image_enhancer_tile_spinbox.setEnabled(enable_tile)
