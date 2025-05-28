from PySide6.QtCore import QRunnable, Signal, QObject
import traceback, sys
import types

class WorkerSignals(QObject):
    finished = Signal()
    error = Signal(tuple)
    result = Signal(object)

class GenericWorker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super(GenericWorker, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.is_cancelled = False

    def run(self):
        try:
            if isinstance(self.fn, types.GeneratorType):
                result = None
                for r in self.fn:
                    if self.is_cancelled:
                        break
                    result = r
                if not self.is_cancelled:
                    self.signals.result.emit(result)
            else:
                result = self.fn(*self.args, **self.kwargs)
                if not self.is_cancelled:
                    self.signals.result.emit(result)
        except:
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        finally:
            self.signals.finished.emit()

    def cancel(self):
        self.is_cancelled = True