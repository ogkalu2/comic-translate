from .nav import NavRailMixin
from .workspace import WorkspaceMixin


class MainWindowBuildersMixin(NavRailMixin, WorkspaceMixin):
    pass


__all__ = ["MainWindowBuildersMixin"]
