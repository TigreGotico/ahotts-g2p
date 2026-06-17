"""Version-aware dispatch smoke tests for the unified phonemize() API.

Covers Basque (eu) V1/V2/V3 and Spanish (es) V1/V2/V3 through the public
``phonemize(text, lang, version)`` entry point. Pure stdlib; no skips.
"""
import pytest

from ahotts_g2p import phonemize


# --- Basque (eu) --------------------------------------------------------- #

@pytest.mark.parametrize("version,expected", [
    ("v1", "kajʃO mundUa"),
    ("v2", "kaiʃO mundUa"),   # V2 drops vowel offglides (au stays a u)
    ("v3", "kajʃO mundUa ."),  # V3 emits punctuation as separate tokens
])
def test_eu_versions(version, expected):
    assert phonemize("Kaixo mundua.", lang="eu", version=version) == expected


def test_eu_v3_keeps_punct_v1_drops():
    # V3 keeps the final stop as a token; V1 does not.
    assert phonemize("Kaixo mundua.", "eu", "v3").endswith(" .")
    assert not phonemize("Kaixo mundua.", "eu", "v1").endswith(" .")


def test_eu_v1_v2_offglide_delta():
    # The defining V1->V2 delta: the "ai" diphthong offglide (j) disappears.
    assert phonemize("Kaixo mundua.", "eu", "v1") != \
        phonemize("Kaixo mundua.", "eu", "v2")


# --- Spanish (es) -------------------------------------------------------- #

@pytest.mark.parametrize("version,expected", [
    ("v1", "Ola mUndo"),
    ("v2", "Ola mUndo"),
    ("v3", "Ola mUndo ."),    # V3 emits punctuation as separate tokens
])
def test_es_versions(version, expected):
    assert phonemize("Hola mundo.", lang="es", version=version) == expected


def test_es_returns_nonempty_str():
    for v in ("v1", "v2", "v3"):
        out = phonemize("Buenos dias.", lang="es", version=v)
        assert isinstance(out, str) and out


def test_es_v3_keeps_punct():
    assert phonemize("Hola mundo.", "es", "v3").endswith(" .")
    assert not phonemize("Hola mundo.", "es", "v1").endswith(" .")
