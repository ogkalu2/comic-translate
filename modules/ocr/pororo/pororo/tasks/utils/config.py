from dataclasses import dataclass
from typing import Union


@dataclass
class TransformerConfig:
    src_dict: Union[str, None]
    tgt_dict: Union[str, None]
    src_tok: Union[str, None]
    tgt_tok: Union[str, None]


CONFIGS = {
    "transformer.base.ko.const":
        TransformerConfig(
            "dict.transformer.base.ko.const",
            "dict.transformer.base.ko.const",
            None,
            None,
        ),
    "transformer.base.ko.pg":
        TransformerConfig(
            "dict.transformer.base.ko.mt",
            "dict.transformer.base.ko.mt",
            "bpe8k.ko",
            None,
        ),
    "transformer.base.ko.pg_long":
        TransformerConfig(
            "dict.transformer.base.ko.mt",
            "dict.transformer.base.ko.mt",
            "bpe8k.ko",
            None,
        ),
    "transformer.base.en.gec":
        TransformerConfig(
            "dict.transformer.base.en.mt",
            "dict.transformer.base.en.mt",
            "bpe32k.en",
            None,
        ),
    "transformer.base.zh.pg":
        TransformerConfig(
            "dict.transformer.base.zh.mt",
            "dict.transformer.base.zh.mt",
            None,
            None,
        ),
    "transformer.base.ja.pg":
        TransformerConfig(
            "dict.transformer.base.ja.mt",
            "dict.transformer.base.ja.mt",
            "bpe8k.ja",
            None,
        ),
    "transformer.base.zh.const":
        TransformerConfig(
            "dict.transformer.base.zh.const",
            "dict.transformer.base.zh.const",
            None,
            None,
        ),
    "transformer.base.en.const":
        TransformerConfig(
            "dict.transformer.base.en.const",
            "dict.transformer.base.en.const",
            None,
            None,
        ),
    "transformer.base.en.pg":
        TransformerConfig(
            "dict.transformer.base.en.mt",
            "dict.transformer.base.en.mt",
            "bpe32k.en",
            None,
        ),
    "transformer.base.ko.gec":
        TransformerConfig(
            "dict.transformer.base.ko.gec",
            "dict.transformer.base.ko.gec",
            "bpe8k.ko",
            None,
        ),
    "transformer.base.en.char_gec":
        TransformerConfig(
            "dict.transformer.base.en.char_gec",
            "dict.transformer.base.en.char_gec",
            None,
            None,
        ),
    "transformer.base.en.caption":
        TransformerConfig(
            None,
            None,
            None,
            None,
        ),
    "transformer.base.ja.p2g":
        TransformerConfig(
            "dict.transformer.base.ja.p2g",
            "dict.transformer.base.ja.p2g",
            None,
            None,
        ),
    "transformer.large.multi.mtpg":
        TransformerConfig(
            "dict.transformer.large.multi.mtpg",
            "dict.transformer.large.multi.mtpg",
            "bpe32k.en",
            None,
        ),
    "transformer.large.multi.fast.mtpg":
        TransformerConfig(
            "dict.transformer.large.multi.mtpg",
            "dict.transformer.large.multi.mtpg",
            "bpe32k.en",
            None,
        ),
    "transformer.large.ko.wsd":
        TransformerConfig(
            "dict.transformer.large.ko.wsd",
            "dict.transformer.large.ko.wsd",
            None,
            None,
        ),
}
