from __future__ import annotations

from app.controllers.text_render_batch_mixin import TextRenderBatchMixin
from app.controllers.text_render_live_mixin import TextRenderLiveMixin


class TextRenderMixin(
    TextRenderBatchMixin,
    TextRenderLiveMixin,
):
    def render_text(self):
        selected_paths = self.main.get_selected_page_paths()
        if self.main.image_viewer.hasPhoto() and len(selected_paths) > 1:
            self._render_selected_pages(selected_paths)
            return

        if self.main.image_viewer.hasPhoto():
            self.render_all_pages()
