"""Binary-oracle parity: ahotts_g2p reproduces the real AhoTTS engines.

Correctness is defined as parity with the AhoTTS reference engines, captured as
per-version held-out corpora:

* ``eu_corpus.json`` -- 424 lines from the V3 arrandi ``modulo1y2`` build (which
  phonemized HiTZ/StyleTTS2-eu), with the matching V1/V2 columns.
* ``es_corpus.json`` -- 179 lines for Spanish across all three versions.

Scoring is positional (space-split) word match plus exact-line match, exactly
as the development parity harness reports.  The thresholds below are the
verified figures; any regression fails the suite.
"""
import json
import os

import pytest

from ahotts_g2p import phonemize

_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# (lang, version) -> (min word-match %, min exact lines)
_THRESHOLDS = {
    ("eu", "v1"): (99.94, 427),
    ("eu", "v2"): (100.0, 430),
    ("eu", "v3"): (99.90, 421),
    ("es", "v1"): (100.0, 179),
    ("es", "v2"): (100.0, 179),
    ("es", "v3"): (100.0, 179),
}


def _load(name):
    with open(os.path.join(_DATA, name), encoding="utf-8") as fh:
        return json.load(fh)


def _score(rows, lang, version):
    wm = wt = line_ok = npairs = 0
    for row in rows:
        gold = row.get(version, "")
        if not gold.strip():
            continue  # an empty oracle line is a binary failure, not truth
        got = phonemize(row["text"], lang=lang, version=version)
        npairs += 1
        if got == gold:
            line_ok += 1
        gw, pw = gold.split(), got.split()
        for i in range(max(len(gw), len(pw))):
            wt += 1
            if (gw[i] if i < len(gw) else None) == (pw[i] if i < len(pw) else None):
                wm += 1
    return 100.0 * wm / wt, line_ok, npairs


@pytest.mark.parametrize("lang,version", list(_THRESHOLDS))
def test_corpus_parity(lang, version):
    rows = _load("eu_corpus.json" if lang == "eu" else "es_corpus.json")
    min_pct, min_lines = _THRESHOLDS[(lang, version)]
    pct, line_ok, npairs = _score(rows, lang, version)
    assert pct >= min_pct, f"{lang}/{version} word parity {pct:.2f}% < {min_pct}%"
    assert line_ok >= min_lines, \
        f"{lang}/{version} exact lines {line_ok}/{npairs} < {min_lines}"


def test_styletts2_eu_default_path():
    """The default eu/v3 path is the one that phonemized HiTZ/StyleTTS2-eu."""
    # dict-stress demonstrative + the StyleTTS2-eu training convention
    assert phonemize("Euskara Euskal Herriko hizkuntza da.") == \
        "Ewskaɾa ewskAl Eriko IʂkunPa ðA ."
