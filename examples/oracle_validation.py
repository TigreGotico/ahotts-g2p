#!/usr/bin/env python3
"""Validate ahotts_g2p against the StyleTTS2-eu oracle (expects 100%).

Run from the repo root; reads the test split shipped under tests/data/.
"""
import os
import sys

from ahotts_g2p import phonemize

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(_HERE, os.pardir, "tests", "data")


def _load(name):
    out = {}
    with open(os.path.join(_DATA, name), encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if "|" in line:
                key, val = line.split("|", 1)
                out[key] = val
    return out


def main():
    texts = _load("test_tts_eu.txt")
    gold = _load("test_tts_eu_phonemes.txt")
    ok = 0
    for key in texts:
        got = phonemize(texts[key])
        exp = gold[key]
        mark = "OK " if got == exp else "XX "
        if got == exp:
            ok += 1
        else:
            print(f"{mark}{key}")
            print(f"    in : {texts[key]}")
            print(f"    got: {got}")
            print(f"    exp: {exp}")
    total = len(texts)
    print(f"\nParity: {ok}/{total} ({100 * ok / total:.1f}%)")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
