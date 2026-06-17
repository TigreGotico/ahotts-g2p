#!/usr/bin/env python3
"""Basic usage: phonemize a few Basque sentences to the AhoTTS IPA string."""
from ahotts_g2p import phonemize

SENTENCES = [
    "Bai.",
    "Ez, horrek ez du balio!",
    "Kaixo mundua, zer moduz zaude?",
    "Mila esker zure laguntzagatik.",
    "1870. urtean jaio zen.",
]


def main():
    for text in SENTENCES:
        print(f"{text}")
        print(f"  -> {phonemize(text)}")
        print()


if __name__ == "__main__":
    main()
