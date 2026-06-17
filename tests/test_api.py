"""Public-API shape tests for ahotts_g2p."""
import pytest

import ahotts_g2p
from ahotts_g2p import SAMPA_TO_IPA, phonemize


def test_exports():
    assert callable(phonemize)
    assert isinstance(SAMPA_TO_IPA, dict)
    assert isinstance(ahotts_g2p.__version__, str)
    assert set(ahotts_g2p.__all__) == {"phonemize", "SAMPA_TO_IPA", "__version__"}


def test_phonemize_returns_str():
    out = phonemize("Kaixo mundua")
    assert isinstance(out, str)
    assert out  # non-empty


def test_phonemize_defaults():
    # default lang/version is eu/v3
    assert phonemize("Bai.") == phonemize("Bai.", lang="eu", version="v3")


def test_phonemize_basic_value():
    # "Bai." -> "bAj ." (StyleTTS2-eu oracle line 1)
    assert phonemize("Bai.") == "bAj ."


@pytest.mark.parametrize("lang", ["es", "fr", "EN"])
def test_unsupported_lang_raises(lang):
    with pytest.raises(ValueError):
        phonemize("hola", lang=lang)


@pytest.mark.parametrize("version", ["v1", "v2", "V0", "x"])
def test_unsupported_version_raises(version):
    with pytest.raises(ValueError):
        phonemize("kaixo", version=version)


def test_version_string_is_alpha():
    assert ahotts_g2p.__version__.startswith("0.0.1")
