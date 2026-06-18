"""Pure-Python, zero-dependency AhoTTS grapheme-to-phoneme.

A pure-Python reimplementation of the AhoTTS linguistic front-end
(grapheme-to-phoneme) for Basque (``eu``) and Spanish (``es``).  The
text -> phoneme pipeline is::

    normalize -> g2p -> syllabify -> stress -> SAMPA -> IPA -> single-char

The bundled dictionaries (``eu_dicc_v1.dic``, ``eu_dicc_v3.dic``,
``es_dicc.dic``) are read directly from their HDIC binary format with the
stdlib ``struct`` module; there is no C build and no runtime dependency.

Public API
----------
``phonemize(text, lang="eu", version="v3") -> str``
    Phonemize ``text`` to the single-char IPA training string.  ``lang`` is
    one of ``"eu"`` / ``"es"`` and ``version`` one of ``"v1"`` / ``"v2"`` /
    ``"v3"`` (see ``docs/versions.md``).
``SAMPA_TO_IPA``
    The ordered SAMPA -> IPA mapping table.
"""
from .es import phonemize_es as _phonemize_es
from .g2p import phonemize_eu as _phonemize_eu
from .phones import SAMPA_TO_IPA
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
        Input text.  Numbers, ordinals and roman numerals are expanded to the
        target-language number words; punctuation is preserved as separate
        tokens (V3) or dropped (V1/V2), matching each engine.
    lang : str, default ``"eu"``
        Target language: ``"eu"`` (Basque) or ``"es"`` (Spanish).
    version : str, default ``"v3"``
        AhoTTS engine version to emulate -- ``"v1"``, ``"v2"`` or ``"v3"``.
        See ``docs/versions.md`` for what each reproduces.

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
            f"(supported: {', '.join(SUPPORTED_VERSIONS)}; see docs/versions.md)"
        )
    if lang == "es":
        return _phonemize_es(text, version)
    return _phonemize_eu(text, version)
