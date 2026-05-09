import re
import unicodedata
from abc import abstractmethod
from dataclasses import dataclass
from typing import List, Mapping, Optional, Union


@dataclass
class TaskConfig:
    task: str
    lang: str
    n_model: str


class PororoTaskBase:
    r"""Task base class that implements basic functions for prediction"""

    def __init__(self, config: TaskConfig):
        self.config = config

    @property
    def n_model(self):
        return self.config.n_model

    @property
    def lang(self):
        return self.config.lang

    @abstractmethod
    def predict(
        self,
        text: Union[str, List[str]],
        **kwargs,
    ):
        raise NotImplementedError(
            "`predict()` function is not implemented properly!")

    def __call__(self):
        raise NotImplementedError(
            "`call()` function is not implemented properly!")

    def __repr__(self):
        return f"[TASK]: {self.config.task.upper()}\n[LANG]: {self.config.lang.upper()}\n[MODEL]: {self.config.n_model}"

    def _normalize(self, text: str):
        """Unicode normalization and whitespace removal (often needed for contexts)"""
        text = unicodedata.normalize("NFKC", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text


class PororoFactoryBase(object):
    r"""This is a factory base class that construct task-specific module"""

    def __init__(
        self,
        task: str,
        lang: str,
        model: Optional[str] = None,
    ):
        self._available_langs = self.get_available_langs()
        self._available_models = self.get_available_models()
        self._model2lang = {
            v: k for k, vs in self._available_models.items() for v in vs
        }

        # Set default language as very first supported language
        assert (
            lang in self._available_langs
        ), f"Following langs are supported for this task: {self._available_langs}"

        if lang is None:
            lang = self._available_langs[0]

        # Change language option if model is defined by user
        if model is not None:
            lang = self._model2lang[model]

        # Set default model
        if model is None:
            model = self.get_default_model(lang)

        # yapf: disable
        assert (model in self._available_models[lang]), f"{model} is NOT supported for {lang}"
        # yapf: enable

        self.config = TaskConfig(task, lang, model)

    @abstractmethod
    def get_available_langs(self) -> List[str]:
        raise NotImplementedError(
            "`get_available_langs()` is not implemented properly!")

    @abstractmethod
    def get_available_models(self) -> Mapping[str, List[str]]:
        raise NotImplementedError(
            "`get_available_models()` is not implemented properly!")

    @abstractmethod
    def get_default_model(self, lang: str) -> str:
        return self._available_models[lang][0]

    @classmethod
    def load(cls) -> PororoTaskBase:
        raise NotImplementedError(
            "Model load function is not implemented properly!")


class PororoSimpleBase(PororoTaskBase):
    r"""Simple task base wrapper class"""

    def __call__(self, text: str, **kwargs):
        return self.predict(text, **kwargs)


class PororoBiencoderBase(PororoTaskBase):
    r"""Bi-Encoder base wrapper class"""

    def __call__(
        self,
        sent_a: str,
        sent_b: Union[str, List[str]],
        **kwargs,
    ):
        assert isinstance(sent_a, str), "sent_a should be string type"
        assert isinstance(sent_b, str) or isinstance(
            sent_b, list), "sent_b should be string or list of string type"

        sent_a = self._normalize(sent_a)

        # For "Find Similar Sentence" task
        if isinstance(sent_b, list):
            sent_b = [self._normalize(t) for t in sent_b]
        else:
            sent_b = self._normalize(sent_b)

        return self.predict(sent_a, sent_b, **kwargs)


class PororoGenerationBase(PororoTaskBase):
    r"""Generation task wrapper class using various generation tricks"""

    def __call__(
        self,
        text: str,
        beam: int = 5,
        temperature: float = 1.0,
        top_k: int = -1,
        top_p: float = -1,
        no_repeat_ngram_size: int = 4,
        len_penalty: float = 1.0,
        **kwargs,
    ):
        assert isinstance(text, str), "Input text should be string type"

        return self.predict(
            text,
            beam=beam,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            no_repeat_ngram_size=no_repeat_ngram_size,
            len_penalty=len_penalty,
            **kwargs,
        )


class PororoTaskGenerationBase(PororoTaskBase):
    r"""Generation task wrapper class using only beam search"""

    def __call__(self, text: str, beam: int = 1, **kwargs):
        assert isinstance(text, str), "Input text should be string type"

        text = self._normalize(text)

        return self.predict(text, beam=beam, **kwargs)
