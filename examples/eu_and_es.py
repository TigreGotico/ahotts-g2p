#!/usr/bin/env python3
"""Phonemize Basque and Spanish through the same API."""
from ahotts_g2p import phonemize

PAIRS = [
    ("eu", "Kaixo mundua, zer moduz zaude?"),
    ("eu", "Mila esker zure laguntzagatik."),
    ("es", "Hola mundo, como estas?"),
    ("es", "Muchas gracias por tu ayuda."),
]


def main():
    for lang, text in PAIRS:
        print(f"[{lang}] {text}")
        print(f"      -> {phonemize(text, lang=lang)}")
        print()


if __name__ == "__main__":
    main()
