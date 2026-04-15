from __future__ import annotations

from typing import TYPE_CHECKING

from app.controllers.batch_report_state_mixin import BatchReportStateMixin
from app.controllers.batch_report_view_mixin import BatchReportViewMixin

if TYPE_CHECKING:
    from controller import ComicTranslate


class BatchReportController(BatchReportStateMixin, BatchReportViewMixin):
    def __init__(self, main: ComicTranslate):
        self.main = main
        self._current_batch_report = None
        self._latest_batch_report = None
        self._batch_report_drawer = None
        self._error_registry: dict[str, dict] = {}
