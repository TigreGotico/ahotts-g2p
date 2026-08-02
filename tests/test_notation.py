"""Multi-alphabet output (scriptconv) tests.

* Default-output parity: ``alphabet="native"`` (the default) is byte-identical
  to pre-scriptconv releases -- fully backward compatible.
* IPA spot checks on documented gold lines (README quick-start / oracle
  corpus): stress folds back to the real IPA mark ``ˈ`` (U+02C8), affricates
  and aspirated stops expand to their multi-char IPA sequence.
* One X-SAMPA check per language.
* Error path: unsupported alphabet, and phones with no mapping in the
  requested scriptconv notation raise ``ValueError`` (never silently drop).

ARPABET is scoped to English phonology, so it inherently lacks symbols for
several Basque/Spanish phones and will never grow them: the retroflex
fricative ``ʂ`` (Basque /z/, e.g. in "Ez") and the voiced bilabial
approximant/fricative ``β`` (intervocalic Basque/Spanish b/v, e.g. in
"ibili"). Any AhoTTS output containing either raises ``ValueError`` when
converted to ``alphabet="arpa"``; this is exercised below as the error-path
test.
"""
import pytest

from ahotts_g2p import SUPPORTED_ALPHABETS, convert_alphabet, native_to_ipa, phonemize


def test_supported_alphabets():
    assert SUPPORTED_ALPHABETS[:2] == ("native", "ipa")
    assert "x-sampa" in SUPPORTED_ALPHABETS
    assert "arpa" in SUPPORTED_ALPHABETS
    assert "buckwalter" not in SUPPORTED_ALPHABETS
    assert "arabic" not in SUPPORTED_ALPHABETS


def test_default_alphabet_is_native_backward_compatible():
    text = "Ez, horrek ez du balio!"
    assert phonemize(text) == phonemize(text, alphabet="native")
    # unchanged from pre-scriptconv releases
    assert phonemize("Bai.") == "bAj ."


@pytest.mark.parametrize(
    "kwargs,ipa",
    [
        (dict(text="Bai."), "bˈaj ."),
        (dict(text="Ez, horrek ez du balio!"), "ˈeʂ , ˈorek eʂ tˈu βalˈio !"),
        (dict(text="Kaixo mundua", lang="eu", version="classic"),
         "kajʃˈo mundˈua"),
        (dict(text="Hola mundo.", lang="es", version="classic"),
         "ˈola mˈundo"),
    ],
)
def test_ipa_spot_checks(kwargs, ipa):
    text = kwargs.pop("text")
    assert phonemize(text, alphabet="ipa", **kwargs) == ipa


def test_native_to_ipa_matches_phonemize_ipa():
    native = phonemize("Ez, horrek ez du balio!")
    assert native_to_ipa(native) == phonemize("Ez, horrek ez du balio!", alphabet="ipa")


def test_convert_alphabet_native_is_identity():
    native = phonemize("Bai.")
    assert convert_alphabet(native, "native") == native


def test_xsampa_spot_check_basque():
    out = phonemize("Kaixo mundua", lang="eu", version="classic", alphabet="x-sampa")
    assert out == 'kajS"o mund"ua'


def test_xsampa_spot_check_spanish():
    out = phonemize("Hola mundo.", lang="es", version="classic", alphabet="x-sampa")
    assert out == '"ola m"undo'


def test_unsupported_alphabet_raises():
    with pytest.raises(ValueError):
        phonemize("Bai.", alphabet="klingon")


def test_unmapped_symbol_raises_clearly_not_silently():
    # /S`/ (retroflex fricative, Basque /z/) has no ARPABET mapping -- an
    # inherent gap in ARPA's English-scoped inventory (table gap, documented
    # above), not something scriptconv will ever add.
    with pytest.raises(ValueError, match="arpa"):
        phonemize("Ez, horrek ez du balio!", lang="eu", alphabet="arpa")


def test_beta_unmapped_in_arpa_raises():
    # "ibili" folds intervocalic b to the IPA voiced bilabial
    # approximant/fricative beta, also inherently unmapped in ARPABET
    with pytest.raises(ValueError):
        phonemize("ibili", lang="eu", alphabet="arpa")
