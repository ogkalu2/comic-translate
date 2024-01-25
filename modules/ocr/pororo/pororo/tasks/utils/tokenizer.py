from typing import List, Optional, Union

from tokenizers import Tokenizer, decoders, pre_tokenizers
from tokenizers.implementations import BaseTokenizer
from tokenizers.models import BPE, Unigram
from tokenizers.normalizers import NFKC


class CustomTokenizer(BaseTokenizer):

    def __init__(
        self,
        vocab: Union[str, List],
        merges: Union[str, None],
        unk_token: str = "<unk>",
        replacement: str = "▁",
        add_prefix_space: bool = True,
        dropout: Optional[float] = None,
        normalize: bool = True,
    ):
        if merges:
            n_model = "BPE"
            tokenizer = Tokenizer(
                BPE(
                    vocab,  # type: ignore
                    merges,
                    unk_token=unk_token,
                    fuse_unk=True,
                ))
        else:
            n_model = "Unigram"
            tokenizer = Tokenizer(Unigram(vocab, 1))  # type: ignore

        if normalize:
            tokenizer.normalizer = NFKC()

        tokenizer.pre_tokenizer = pre_tokenizers.Metaspace(
            replacement=replacement,
            add_prefix_space=add_prefix_space,
        )

        tokenizer.decoder = decoders.Metaspace(
            replacement=replacement,
            add_prefix_space=add_prefix_space,
        )

        parameters = {
            "model": f"SentencePiece{n_model}",
            "unk_token": unk_token,
            "replacement": replacement,
            "add_prefix_space": add_prefix_space,
            "dropout": dropout,
        }
        super().__init__(tokenizer, parameters)

    @staticmethod
    def from_file(
        vocab_filename: str,
        merges_filename: Union[str, None],
        **kwargs,
    ):
        # BPE
        if merges_filename:
            vocab, merges = BPE.read_file(vocab_filename, merges_filename)

        # Unigram
        else:
            vocab = []
            merges = None
            with open(vocab_filename, "r") as f_in:
                for line in f_in.readlines():
                    token, score = line.strip().split("\t")
                    vocab.append((token, float(score)))

        return CustomTokenizer(vocab, merges, **kwargs)

    def segment(self, text: str) -> List[str]:
        """
        Segment text into subword list

        Args:
            text (str): input text to be segmented

        Returns:
            List[str]: segmented subword list

        """
        encoding = self.encode(text)

        offsets = encoding.offsets
        tokens = encoding.tokens

        result = []
        for offset, token in zip(offsets, tokens):
            if token != "<unk>":
                result.append(token)
                continue
            s, e = offset
            result.append(text[s:e])
        return result
