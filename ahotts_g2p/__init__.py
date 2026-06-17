"""ahotts_g2p -- pure-Python, zero-dependency AhoTTS grapheme-to-phoneme.

An independent pure-Python reimplementation of the AhoTTS linguistic
front-end (grapheme-to-phoneme) for Basque (``eu``) and Spanish (``es``), in
the spirit of pycotovia.  The text -> phoneme pipeline is:

    normalize -> g2p -> syllabify -> stress -> SAMPA -> IPA -> single-char

The bundled dictionaries (``eu_dicc_v1.dic``, ``eu_dicc_v3.dic``,
``es_dicc.dic``) are read directly from their HDIC binary format (stdlib
``struct``); there is no C build and no runtime dependency.

Public API
----------
``phonemize(text, lang="eu", version="v3") -> str``
    Phonemize ``text`` to the single-char IPA training string.  ``lang`` is
    one of ``"eu"`` / ``"es"`` and ``version`` one of ``"v1"`` / ``"v2"`` /
    ``"v3"``.
``SAMPA_TO_IPA``
    The ordered SAMPA -> IPA mapping table.

Version / language support
--------------------------
Each ``version`` emulates a distinct AhoTTS engine generation (V1 = original
pyAhoTTS 2022, V2 = aholab/AhoTTS Dec-2025 VITS-era libhtts, V3 = arrandi
StyleTTS modulo1y2).  See ``docs/versions.md`` for the deltas and the
verified parity table.  The Basque ``v3`` path is served by the hardened
HDIC fast-path (``ahotts_eu_hdic``) that phonemized HiTZ/StyleTTS2-eu and
reproduces that oracle 100%; ``v1``/``v2`` and all Spanish versions are
served by the version-aware ports (``ahotts_versioned`` / ``es_phonemizer``).
"""
from .ahotts_eu_hdic import SAMPA_TO_IPA
from .ahotts_eu_hdic import phonemize as _phonemize_eu_v3
from .ahotts_versioned import phonemize as _phonemize_eu_versioned
from .es_phonemizer import phonemize_es as _phonemize_es
from .version import __version__

__all__ = ["phonemize", "SAMPA_TO_IPA", "__version__"]

#: Languages the phonemizer can handle.
SUPPORTED_LANGS = ("eu", "es")
#: AhoTTS engine versions implemented (see docs/versions.md).
SUPPORTED_VERSIONS = ("v1", "v2", "v3")


def phonemize(text, lang="eu", version="v3"):
    """Phonemize ``text`` into the AhoTTS single-char IPA training string.

    Parameters
    ----------
    text : str
        Input text. Numbers, ordinals and roman numerals are expanded to
        the target-language number words; punctuation is preserved as
        separate tokens (V3) or dropped (V1/V2), matching each engine.
    lang : str, default ``"eu"``
        Target language: ``"eu"`` (Basque) or ``"es"`` (Spanish).
    version : str, default ``"v3"``
        AhoTTS engine version to emulate: ``"v1"`` (original pyAhoTTS),
        ``"v2"`` (aholab/AhoTTS VITS-era) or ``"v3"`` (arrandi StyleTTS
        modulo1y2). See ``docs/versions.md``.

    Returns
    -------
    str
        Space-separated single-char IPA tokens, with stressed vowels and
        multi-char phonemes folded to single characters, ready for a
        StyleTTS2-style model.

    Raises
    ------
    ValueError
        If ``lang`` or ``version`` is not supported.
    """
    lang = (lang or "eu").lower()
    version = (version or "v3").lower()
    if lang not in SUPPORTED_LANGS:
        raise ValueError(
            f"lang={lang!r} is not supported "
            f"(supported: {', '.join(SUPPORTED_LANGS)})"
        )
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(
            f"version={version!r} is not supported "
            f"(supported: {', '.join(SUPPORTED_VERSIONS)}; see "
            f"docs/versions.md)"
        )
    if lang == "es":
        return _phonemize_es(text, version)
    # lang == "eu"
    if version == "v3":
        # Hardened HDIC fast-path: phonemized HiTZ/StyleTTS2-eu, 100% oracle.
        return _phonemize_eu_v3(text)
    return _phonemize_eu_versioned(text, version)
