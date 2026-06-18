"""Binary-oracle parity: ahotts_g2p reproduces the real AhoTTS engines.

Correctness is defined as parity with the AhoTTS reference engines, captured as
per-version held-out corpora:

* ``eu_corpus.json`` -- 424 lines from the V3 arrandi ``modulo1y2`` build (which
  phonemized HiTZ/StyleTTS2-eu), with the matching V1 column.
* ``es_corpus.json`` -- 179 lines for Spanish across both versions.

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
    ("eu", "v3"): (99.90, 421),
    ("es", "v1"): (100.0, 179),
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


# --- Northern Basque (Iparralde / Iparrahotsa) dialect ---------------------
# Oracle: the AhoTTS_Iparrahotsa binary (pyAhoTTS-Iparrahotsa transcribe_text).
# Corpus: the same 430 Basque sentences, phonemized by that binary.  The
# threshold is the verified figure; the residual lines are documented
# faithful-artifacts (Northern eu_normal date expansion, foreign-name dict
# transcriptions with nasal vowels, post-k-drop stress) -- see docs/dialects.md.
_NORTHERN_THRESHOLD = (98.9, 400)   # (min word-match %, min exact lines)


def test_northern_corpus_parity():
    rows = _load("eu_northern_corpus.json")
    wm = wt = line_ok = npairs = 0
    for row in rows:
        gold = row["northern"]
        if not gold.strip():
            continue
        got = phonemize(row["text"], lang="eu", dialect="northern")
        npairs += 1
        if got == gold:
            line_ok += 1
        gw, pw = gold.split(), got.split()
        for i in range(max(len(gw), len(pw))):
            wt += 1
            if (gw[i] if i < len(gw) else None) == (pw[i] if i < len(pw) else None):
                wm += 1
    pct = 100.0 * wm / wt
    min_pct, min_lines = _NORTHERN_THRESHOLD
    assert pct >= min_pct, f"northern word parity {pct:.2f}% < {min_pct}%"
    assert line_ok >= min_lines, \
        f"northern exact lines {line_ok}/{npairs} < {min_lines}"


def test_northern_features():
    """The signature Northern features: pronounced /h/, ü -> /y/, uvular /ʁ/,
    remapped sibilants (s -> ʂ, z -> s, ts -> tʂ), j/dd -> /ɟ/."""
    # /h/ pronounced (silent in the South); uvular ʁ; dict first-syllable stress
    assert phonemize("hori horrek", lang="eu", dialect="northern") == "hOɾi hoʁEk"
    # ü -> /y/, uvular ʁ
    assert phonemize("bürü", lang="eu", dialect="northern") == "byʁy"
    # the full sentence: pronounced h, uvular ʁ, s -> ʂ, ts -> ʂ/tʂ
    assert phonemize("Euskara Euskal Herriko hizkuntza da.",
                     lang="eu", dialect="northern") == \
        "Ewʂkaɾa ewʂkAl heʁIko hiskUnVa ðA"


def test_northern_only_basque():
    import pytest as _pytest
    with _pytest.raises(ValueError):
        phonemize("hola", lang="es", dialect="northern")
