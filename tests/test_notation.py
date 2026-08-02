"""Multi-alphabet output (scriptconv) tests.

* Default-output parity: ``alphabet="native"`` (the default) is byte-identical
  to pre-scriptconv releases -- fully backward compatible.
* IPA spot checks on documented gold lines (README quick-start / oracle
  corpus): stress folds back to the real IPA mark ``ˈ`` (U+02C8), affricates
  and aspirated stops expand to their multi-char IPA sequence.
* One X-SAMPA check per language (picked to avoid the two scriptconv table
  gaps documented below).
* Error path: unsupported alphabet, and phones with no mapping in the
  requested scriptconv notation raise ``ValueError`` (never silently drop).

Known scriptconv X-SAMPA table gaps (out of scope here; scriptconv-side):
the standard X-SAMPA table is missing plain ``r`` (alveolar trill -- only the
tap ``4``/``r`` alias is present as IPA ɾ) and plain ``h`` (voiceless glottal
fricative -- only ``h\\`` for ɦ is present). Any AhoTTS output containing a
trill (``rr`` -> IPA ``r``) or ``/h/`` raises ``ValueError`` when converted to
``alphabet="x-sampa"``; this is exercised below as the error-path test.
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
    # no trill /r/, no /h/ -- clear of the documented scriptconv table gaps
    out = phonemize("Kaixo mundua", lang="eu", version="classic", alphabet="x-sampa")
    assert out == 'kajS"o mund"ua'


def test_xsampa_spot_check_spanish():
    out = phonemize("Hola mundo.", lang="es", version="classic", alphabet="x-sampa")
    assert out == '"ola m"undo'


def test_unsupported_alphabet_raises():
    with pytest.raises(ValueError):
        phonemize("Bai.", alphabet="klingon")


def test_unmapped_symbol_raises_clearly_not_silently():
    # /h/ has no scriptconv X-SAMPA mapping (table gap, documented above)
    with pytest.raises(ValueError, match="x-sampa"):
        phonemize("hori horrek", lang="eu", dialect="northern", alphabet="x-sampa")


def test_trill_r_unmapped_in_xsampa_raises():
    # "horrek" folds its geminate rr to the IPA trill /r/, also unmapped
    with pytest.raises(ValueError):
        phonemize("horrek", lang="eu", alphabet="x-sampa")
