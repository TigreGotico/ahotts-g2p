#!/usr/bin/env python3
"""Compare the AhoTTS engines on the same Basque text.

Both classic and modern keep diphthong offglides and dictionary stress; modern
also emits punctuation as tokens.
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
        for version in ("classic", "modern"):
            print(f"  {version}: {phonemize(text, lang='eu', version=version)}")
        print()


if __name__ == "__main__":
    main()
