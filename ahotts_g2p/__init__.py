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
``phonemize(text, lang="eu", version="v3", dialect="standard") -> str``
    Phonemize ``text`` to the single-char IPA training string.  ``lang`` is
    one of ``"eu"`` / ``"es"`` and ``version`` one of ``"v1"`` / ``"v3"``
    (see ``docs/versions.md``).  ``dialect="northern"`` (Basque only)
    selects the Northern (Iparralde / Iparrahotsa) engine (see
    ``docs/dialects.md``).
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
SUPPORTED_VERSIONS = ("v1", "v3")
#: Basque dialects implemented (see docs/dialects.md).
SUPPORTED_DIALECTS = ("standard", "northern")


def phonemize(text, lang="eu", version="v3", dialect="standard"):
    """Phonemize ``text`` into the AhoTTS single-char IPA training string.

    Parameters
    ----------
    text : str
        Input text.  Numbers, ordinals and roman numerals are expanded to the
        target-language number words; punctuation is preserved as separate
        tokens (V3) or dropped (V1), matching each engine.
    lang : str, default ``"eu"``
        Target language: ``"eu"`` (Basque) or ``"es"`` (Spanish).
    version : str, default ``"v3"``
        AhoTTS engine version to emulate -- ``"v1"`` or ``"v3"``.
        See ``docs/versions.md`` for what each reproduces.  Ignored when
        ``dialect="northern"`` (that engine is a single V1-lineage fork).
    dialect : str, default ``"standard"``
        Basque dialect.  ``"standard"`` is the Southern (Batua) engine selected
        by ``version``; ``"northern"`` is the Northern (Iparralde /
        Iparrahotsa) engine -- pronounced /h/, French vowels (ü -> /y/), uvular
        /ʁ/, a remapped sibilant system.  See ``docs/dialects.md``.  Only valid
        for ``lang="eu"``.

    Returns
    -------
    str
        Space-separated single-char IPA tokens, with stressed vowels and
        multi-char phonemes folded to single characters, ready for a
        StyleTTS2-style model.

    Raises
    ------
    ValueError
        If ``lang``, ``version`` or ``dialect`` is not supported, or
        ``dialect="northern"`` is combined with a non-Basque ``lang``.
    """
    lang = (lang or "eu").lower()
    version = (version or "v3").lower()
    dialect = (dialect or "standard").lower()
    if lang not in SUPPORTED_LANGS:
        raise ValueError(
            f"lang={lang!r} is not supported "
            f"(supported: {', '.join(SUPPORTED_LANGS)})"
        )
    if dialect not in SUPPORTED_DIALECTS:
        raise ValueError(
            f"dialect={dialect!r} is not supported "
            f"(supported: {', '.join(SUPPORTED_DIALECTS)}; see docs/dialects.md)"
        )
    if dialect == "northern":
        if lang != "eu":
            raise ValueError(
                "dialect='northern' is only available for lang='eu' (Basque)"
            )
        # The Northern (Iparrahotsa) engine is a single V1-lineage fork, so it
        # does not cross with the v1/v3 versions; `version` is ignored.
        return _phonemize_eu(text, "eu_northern")
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(
            f"version={version!r} is not supported "
            f"(supported: {', '.join(SUPPORTED_VERSIONS)}; see docs/versions.md)"
        )
    if lang == "es":
        return _phonemize_es(text, version)
    return _phonemize_eu(text, version)
