"""CLI: python -m ahotts_g2p "Kaixo mundua"."""
import argparse
import sys

from . import phonemize
from .notation import SUPPORTED_ALPHABETS


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(prog="ahotts-g2p")
    parser.add_argument("text", nargs="*", help="text to phonemize (stdin if omitted)")
    parser.add_argument("--lang", default="eu", choices=("eu", "es"))
    parser.add_argument("--version", dest="version", default="modern",
                         choices=("classic", "modern"))
    parser.add_argument("--dialect", default="standard",
                         choices=("standard", "northern"))
    parser.add_argument("--alphabet", default="native", choices=SUPPORTED_ALPHABETS,
                         help="output notation (default: native single-char IPA)")
    args = parser.parse_args(argv)

    def _run(text):
        print(phonemize(text, lang=args.lang, version=args.version,
                         dialect=args.dialect, alphabet=args.alphabet))

    if not args.text:
        for line in sys.stdin:
            line = line.rstrip("\n")
            if line:
                _run(line)
        return 0
    _run(" ".join(args.text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
