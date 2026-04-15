from __future__ import annotations

from typing import TYPE_CHECKING

from app.controllers.project_export_mixin import ProjectExportMixin
from app.controllers.project_autosave_runtime_mixin import ProjectAutosaveRuntimeMixin
from app.controllers.project_recent_mixin import ProjectRecentMixin
from app.controllers.project_recovery_mixin import ProjectRecoveryMixin
from app.controllers.project_session_mixin import ProjectSessionMixin
from app.controllers.project_settings_mixin import ProjectSettingsMixin

if TYPE_CHECKING:
    from controller import ComicTranslate


class ProjectController(
    ProjectExportMixin,
    ProjectSessionMixin,
    ProjectSettingsMixin,
    ProjectAutosaveRuntimeMixin,
    ProjectRecoveryMixin,
    ProjectRecentMixin,
):
    def __init__(self, main: ComicTranslate):
        self.main = main
        self._init_project_autosave()
