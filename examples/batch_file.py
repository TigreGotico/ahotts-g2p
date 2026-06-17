#!/usr/bin/env python3
"""Phonemize a text file line by line.

Usage:
    python examples/batch_file.py input.txt [output.txt]

Each input line is phonemized; lines of the form "ID|text" (LJSpeech style)
keep the ID and phonemize only the text field.
"""
import sys

from ahotts_g2p import phonemize


def process(line):
    line = line.rstrip("\n")
    if not line:
        return ""
    if "|" in line:
        key, text = line.split("|", 1)
        return f"{key}|{phonemize(text)}"
    return phonemize(line)


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    inp = argv[0]
    out = argv[1] if len(argv) > 1 else None
    lines = []
    with open(inp, encoding="utf-8") as fh:
        for line in fh:
            lines.append(process(line))
    text = "\n".join(lines) + "\n"
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"wrote {out}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
