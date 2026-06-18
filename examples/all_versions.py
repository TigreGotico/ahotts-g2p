#!/usr/bin/env python3
"""Compare the AhoTTS engine versions on the same Basque text.

V1 and V3 keep diphthong offglides and dictionary stress; V3 also emits
punctuation as tokens.
"""
from ahotts_g2p import phonemize

SENTENCES = [
    "Kaixo mundua.",
    "Euskara Euskal Herriko hizkuntza da.",
    "Horrek ez du balio.",
]


def main():
    for text in SENTENCES:
        print(text)
        for version in ("v1", "v3"):
            print(f"  {version}: {phonemize(text, lang='eu', version=version)}")
        print()


if __name__ == "__main__":
    main()
