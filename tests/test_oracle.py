"""StyleTTS2-eu oracle parity: ahotts_g2p must hit 100% on the 25-line set.

The two data files (input text + gold phoneme strings) are the official
HiTZ/StyleTTS2-eu test split, phonemized by the AhoTTS V3 engine. This package
reproduces every line exactly.
"""
import os

import pytest

from ahotts_g2p import phonemize

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(_HERE, "data")
_TEXT = os.path.join(_DATA, "test_tts_eu.txt")
_PHON = os.path.join(_DATA, "test_tts_eu_phonemes.txt")


def _load(path):
    out = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if "|" in line:
                key, val = line.split("|", 1)
                out[key] = val
    return out


def _oracle_pairs():
    texts = _load(_TEXT)
    gold = _load(_PHON)
    assert texts, "oracle input file empty/missing"
    assert set(texts) == set(gold), "input/gold key mismatch"
    return [(k, texts[k], gold[k]) for k in texts]


@pytest.mark.parametrize("key,text,expected", _oracle_pairs())
def test_oracle_line(key, text, expected):
    assert phonemize(text) == expected, key


def test_oracle_full_parity_100pct():
    pairs = _oracle_pairs()
    ok = sum(1 for _, text, exp in pairs if phonemize(text) == exp)
    assert ok == len(pairs) == 25
