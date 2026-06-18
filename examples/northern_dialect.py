#!/usr/bin/env python3
"""Northern (Iparralde / Iparrahotsa) Basque dialect.

The Northern dialect engine pronounces /h/, has the French vowel ü -> /y/, a
uvular rhotic /ʁ/, a remapped sibilant system (s -> ʂ, z -> s, ts -> tʂ), and
j/dd -> /ɟ/.  Select it with ``dialect="northern"``; the standard (Southern)
output is shown alongside for contrast.
"""
from ahotts_g2p import phonemize

SENTENCES = [
    "hori horrek",
    "bürü",
    "Euskara Euskal Herriko hizkuntza da.",
    "Kaixo, ongi etorri!",
    "Gaur egun, Euskal Herrian bertan ere hizkuntza gutxitua da.",
]


def main():
    for text in SENTENCES:
        northern = phonemize(text, lang="eu", dialect="northern")
        standard = phonemize(text, lang="eu", version="classic")
        print(text)
        print(f"  northern: {northern}")
        print(f"  standard: {standard}")
        print()


if __name__ == "__main__":
    main()
