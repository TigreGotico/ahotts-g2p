"""ahotts_g2p -- pure-Python, zero-dependency AhoTTS grapheme-to-phoneme.

An independent pure-Python reimplementation of the AhoTTS linguistic
front-end (grapheme-to-phoneme) for Basque (eu), in the spirit of pycotovia.
The text -> phoneme pipeline is:

    normalize -> g2p -> syllabify -> stress -> SAMPA -> IPA -> single-char

The bundled Basque dictionary (``eu_dicc.dic``) is read directly from its
HDIC binary format (stdlib ``struct``); there is no C build and no runtime
dependency.

Public API
----------
``phonemize(text, lang="eu", version="v3") -> str``
    Phonemize ``text`` to the single-char IPA training string.
``SAMPA_TO_IPA``
    The ordered SAMPA -> IPA mapping table.

Version / language support
--------------------------
The ``version`` (``"v1"`` / ``"v2"`` / ``"v3"``) and ``lang`` (``"eu"`` /
``"es"``) parameters are accepted now so callers can pin behaviour. The
current release implements the **V3** Basque path (the engine that
phonemized HiTZ/StyleTTS2-eu), which hits 100% on the StyleTTS2-eu oracle.
The version-aware V1/V2 lineage and the Spanish (``es``) module land in
upcoming releases; see ``docs/versions.md``.
"""
from .ahotts_eu_hdic import SAMPA_TO_IPA
from .ahotts_eu_hdic import phonemize as _phonemize_eu
from .version import __version__

__all__ = ["phonemize", "SAMPA_TO_IPA", "__version__"]

#: Languages the current release can phonemize.
SUPPORTED_LANGS = ("eu",)
#: AhoTTS engine versions the current release implements (see docs/versions.md).
SUPPORTED_VERSIONS = ("v3",)


def phonemize(text, lang="eu", version="v3"):
    """Phonemize ``text`` into the AhoTTS single-char IPA training string.

    Parameters
    ----------
    text : str
        Input text. Numbers, ordinals and roman numerals are expanded to
        Basque number words; punctuation is preserved as separate tokens.
    lang : str, default ``"eu"``
        Target language. Only ``"eu"`` (Basque) is implemented in this
        release. ``"es"`` (Spanish) lands in an upcoming release.
    version : str, default ``"v3"``
        AhoTTS engine version to emulate. Only ``"v3"`` -- the engine that
        phonemized HiTZ/StyleTTS2-eu -- is implemented in this release. The
        ``"v1"`` / ``"v2"`` lineage lands in upcoming releases. See
        ``docs/versions.md``.

    Returns
    -------
    str
        Space-separated single-char IPA tokens (one per word), with stressed
        vowels and multi-char phonemes folded to single characters, ready for
        a StyleTTS2-style model.

    Raises
    ------
    ValueError
        If ``lang`` or ``version`` is not yet supported.
    """
    lang = (lang or "eu").lower()
    version = (version or "v3").lower()
    if lang not in SUPPORTED_LANGS:
        raise ValueError(
            f"lang={lang!r} is not supported yet "
            f"(supported: {', '.join(SUPPORTED_LANGS)}; "
            f"'es' lands in an upcoming release)"
        )
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(
            f"version={version!r} is not supported yet "
            f"(supported: {', '.join(SUPPORTED_VERSIONS)}; "
            f"the V1/V2 lineage lands in upcoming releases -- see "
            f"docs/versions.md)"
        )
    return _phonemize_eu(text)
