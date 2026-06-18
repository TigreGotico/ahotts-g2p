"""Public-API shape tests for ahotts_g2p."""
import pytest

import ahotts_g2p
from ahotts_g2p import SAMPA_TO_IPA, phonemize


def test_exports():
    assert callable(phonemize)
    assert isinstance(SAMPA_TO_IPA, dict)
    assert isinstance(ahotts_g2p.__version__, str)
    assert set(ahotts_g2p.__all__) == {"phonemize", "SAMPA_TO_IPA", "__version__"}


def test_supported_langs_and_versions():
    assert ahotts_g2p.SUPPORTED_LANGS == ("eu", "es")
    assert ahotts_g2p.SUPPORTED_VERSIONS == ("classic", "modern")
    assert ahotts_g2p.SUPPORTED_DIALECTS == ("standard", "northern")


def test_default_dialect_is_standard():
    # the default (no dialect) path is unchanged -- backward compatible
    assert phonemize("Bai.") == phonemize("Bai.", dialect="standard")


def test_northern_dialect_differs_from_standard():
    nor = phonemize("hori", lang="eu", dialect="northern")
    std = phonemize("hori", lang="eu", version="classic")
    assert nor != std
    assert nor.startswith("h")        # Northern pronounces the leading h


@pytest.mark.parametrize("dialect", ["norte", "Northern2", "x"])
def test_unsupported_dialect_raises(dialect):
    with pytest.raises(ValueError):
        phonemize("kaixo", dialect=dialect)


def test_phonemize_returns_str():
    out = phonemize("Kaixo mundua")
    assert isinstance(out, str)
    assert out  # non-empty


def test_phonemize_defaults():
    # default lang/version is eu/modern
    assert phonemize("Bai.") == phonemize("Bai.", lang="eu", version="modern")


def test_phonemize_basic_value():
    # "Bai." -> "bAj ." (StyleTTS2-eu oracle line 1)
    assert phonemize("Bai.") == "bAj ."


@pytest.mark.parametrize("lang", ["fr", "EN", "pt", "xx"])
def test_unsupported_lang_raises(lang):
    with pytest.raises(ValueError):
        phonemize("hola", lang=lang)


@pytest.mark.parametrize("version", ["v1", "v3", "v2", "V4", "x", "4"])
def test_unsupported_version_raises(version):
    with pytest.raises(ValueError):
        phonemize("kaixo", version=version)


def test_version_string_is_alpha():
    assert ahotts_g2p.__version__.startswith("0.1.0")
    assert "a" in ahotts_g2p.__version__
