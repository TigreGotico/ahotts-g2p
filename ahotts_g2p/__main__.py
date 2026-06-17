"""CLI: python -m ahotts_g2p "Kaixo mundua"."""
import sys

from . import phonemize


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        for line in sys.stdin:
            line = line.rstrip("\n")
            if line:
                print(phonemize(line))
        return 0
    print(phonemize(" ".join(argv)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
