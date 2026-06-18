"""Version-aware dispatch smoke tests for the unified phonemize() API.

Covers Basque (eu) and Spanish (es) across the ``classic`` and ``modern``
engines through the public ``phonemize(text, lang, version)`` entry point.
Pure stdlib; no skips.
"""
import pytest

from ahotts_g2p import phonemize


# --- Basque (eu) --------------------------------------------------------- #

@pytest.mark.parametrize("version,expected", [
    ("classic", "kajʃO mundUa"),
    ("modern", "kajʃO mundUa ."),  # modern emits punctuation as separate tokens
])
def test_eu_versions(version, expected):
    assert phonemize("Kaixo mundua.", lang="eu", version=version) == expected


def test_eu_modern_keeps_punct_classic_drops():
    # modern keeps the final stop as a token; classic does not.
    assert phonemize("Kaixo mundua.", "eu", "modern").endswith(" .")
    assert not phonemize("Kaixo mundua.", "eu", "classic").endswith(" .")


# --- Spanish (es) -------------------------------------------------------- #

@pytest.mark.parametrize("version,expected", [
    ("classic", "Ola mUndo"),
    ("modern", "Ola mUndo ."),    # modern emits punctuation as separate tokens
])
def test_es_versions(version, expected):
    assert phonemize("Hola mundo.", lang="es", version=version) == expected


def test_es_returns_nonempty_str():
    for v in ("classic", "modern"):
        out = phonemize("Buenos dias.", lang="es", version=v)
        assert isinstance(out, str) and out


def test_es_modern_keeps_punct():
    assert phonemize("Hola mundo.", "es", "modern").endswith(" .")
    assert not phonemize("Hola mundo.", "es", "classic").endswith(" .")
