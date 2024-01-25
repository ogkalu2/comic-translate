"""
Pororo task-specific factory class

    isort:skip_file

"""

import logging
from typing import Optional
from ..pororo.tasks.utils.base import PororoTaskBase

import torch

from ..pororo.tasks import (
    PororoOcrFactory,
)

SUPPORTED_TASKS = {
    "ocr": PororoOcrFactory,
}

LANG_ALIASES = {
    "english": "en",
    "eng": "en",
    "korean": "ko",
    "kor": "ko",
    "kr": "ko",
    "chinese": "zh",
    "chn": "zh",
    "cn": "zh",
    "japanese": "ja",
    "jap": "ja",
    "jp": "ja",
    "jejueo": "je",
    "jje": "je",
}

logging.getLogger("transformers").setLevel(logging.WARN)
logging.getLogger("fairseq").setLevel(logging.WARN)
logging.getLogger("sentence_transformers").setLevel(logging.WARN)
logging.getLogger("youtube_dl").setLevel(logging.WARN)
logging.getLogger("pydub").setLevel(logging.WARN)
logging.getLogger("librosa").setLevel(logging.WARN)


class Pororo:
    r"""
    This is a generic class that will return one of the task-specific model classes of the library
    when created with the `__new__()` method

    """

    def __new__(
        cls,
        task: str,
        lang: str = "en",
        model: Optional[str] = None,
        **kwargs,
    ) -> PororoTaskBase:
        if task not in SUPPORTED_TASKS:
            raise KeyError("Unknown task {}, available tasks are {}".format(
                task,
                list(SUPPORTED_TASKS.keys()),
            ))

        lang = lang.lower()
        lang = LANG_ALIASES[lang] if lang in LANG_ALIASES else lang

        # Get device information from torch API
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Instantiate task-specific pipeline module, if possible
        task_module = SUPPORTED_TASKS[task](
            task,
            lang,
            model,
            **kwargs,
        ).load(device)

        return task_module

    @staticmethod
    def available_tasks() -> str:
        """
        Returns available tasks in Pororo project

        Returns:
            str: Supported task names

        """
        return "Available tasks are {}".format(list(SUPPORTED_TASKS.keys()))

    @staticmethod
    def available_models(task: str) -> str:
        """
        Returns available model names correponding to the user-input task

        Args:
            task (str): user-input task name

        Returns:
            str: Supported model names corresponding to the user-input task

        Raises:
            KeyError: When user-input task is not supported

        """
        if task not in SUPPORTED_TASKS:
            raise KeyError(
                "Unknown task {} ! Please check available models via `available_tasks()`"
                .format(task))

        langs = SUPPORTED_TASKS[task].get_available_models()
        output = f"Available models for {task} are "
        for lang in langs:
            output += f"([lang]: {lang}, [model]: {', '.join(langs[lang])}), "
        return output[:-2]
