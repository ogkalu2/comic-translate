from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Callable

from PySide6 import QtCore
from PySide6.QtCore import QCoreApplication

from app.thread_worker import GenericWorker

if TYPE_CHECKING:
    from controller import ComicTranslate


class TaskRunnerController:
    def __init__(self, main: ComicTranslate):
        self.main = main
        self.operation_queue = deque()
        self.is_processing_queue = False

    def run_threaded(
        self,
        callback: Callable,
        result_callback: Callable = None,
        error_callback: Callable = None,
        finished_callback: Callable = None,
        *args,
        **kwargs,
    ):
        return self._queue_operation(
            callback,
            result_callback,
            error_callback,
            finished_callback,
            *args,
            **kwargs,
        )

    def _queue_operation(
        self,
        callback: Callable,
        result_callback: Callable = None,
        error_callback: Callable = None,
        finished_callback: Callable = None,
        *args,
        **kwargs,
    ):
        operation = {
            "callback": callback,
            "result_callback": result_callback,
            "error_callback": error_callback,
            "finished_callback": finished_callback,
            "args": args,
            "kwargs": kwargs,
        }

        self.operation_queue.append(operation)
        if not self.is_processing_queue:
            self._process_next_operation()

    def _process_next_operation(self):
        if not self.operation_queue:
            self.is_processing_queue = False
            return

        self.is_processing_queue = True
        operation = self.operation_queue.popleft()

        def enhanced_finished_callback():
            if operation["finished_callback"]:
                operation["finished_callback"]()
            QtCore.QTimer.singleShot(0, self._process_next_operation)

        def enhanced_error_callback(error_tuple):
            if operation["error_callback"]:
                operation["error_callback"](error_tuple)
            QtCore.QTimer.singleShot(0, self._process_next_operation)

        def enhanced_result_callback(result):
            if operation["result_callback"]:
                operation["result_callback"](result)

        self._execute_single_operation(
            operation["callback"],
            enhanced_result_callback,
            enhanced_error_callback,
            enhanced_finished_callback,
            *operation["args"],
            **operation["kwargs"],
        )

    def _execute_single_operation(
        self,
        callback: Callable,
        result_callback: Callable = None,
        error_callback: Callable = None,
        finished_callback: Callable = None,
        *args,
        **kwargs,
    ):
        worker = GenericWorker(callback, *args, **kwargs)

        if result_callback:
            worker.signals.result.connect(
                lambda result: QtCore.QTimer.singleShot(
                    0, lambda: result_callback(result)
                )
            )
        if error_callback:
            worker.signals.error.connect(
                lambda error: QtCore.QTimer.singleShot(0, lambda: error_callback(error))
            )
        if finished_callback:
            worker.signals.finished.connect(finished_callback)

        self.main.current_worker = worker
        self.main.threadpool.start(worker)

    def run_threaded_immediate(
        self,
        callback: Callable,
        result_callback: Callable = None,
        error_callback: Callable = None,
        finished_callback: Callable = None,
        *args,
        **kwargs,
    ):
        return self._execute_single_operation(
            callback,
            result_callback,
            error_callback,
            finished_callback,
            *args,
            **kwargs,
        )

    def clear_operation_queue(self):
        self.operation_queue.clear()

    def cancel_current_task(self):
        if self.main.current_worker:
            self.main.current_worker.cancel()

        if self.main._batch_active:
            self.main._batch_cancel_requested = True
            self.main.cancel_button.setEnabled(False)
            self.main.progress_bar.setFormat(
                QCoreApplication.translate("Messages", "Cancelling... %p%")
            )

        self.clear_operation_queue()
        self.is_processing_queue = False

    def run_finish_only(
        self, finished_callback: Callable, error_callback: Callable = None
    ):
        def _noop():
            pass

        self._queue_operation(
            callback=_noop,
            result_callback=None,
            error_callback=error_callback,
            finished_callback=finished_callback,
        )
