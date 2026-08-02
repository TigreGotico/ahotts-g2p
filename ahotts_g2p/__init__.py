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
``phonemize(text, lang="eu", version="modern", dialect="standard") -> str``
    Phonemize ``text`` to the single-char IPA training string.  ``lang`` is
    one of ``"eu"`` / ``"es"`` and ``version`` one of ``"classic"`` (the
    original AhoTTS engine, used by the HiTZ VITS voices) or ``"modern"`` (the
    StyleTTS-era build, used by HiTZ/StyleTTS2-eu; the default).  See
    ``docs/versions.md``.  ``dialect="northern"`` (Basque only) selects the
    Northern (Iparralde / Iparrahotsa) engine (see ``docs/dialects.md``).
``SAMPA_TO_IPA``
    The ordered SAMPA -> IPA mapping table.
"""
from .es import phonemize_es as _phonemize_es
from .g2p import phonemize_eu as _phonemize_eu
from .notation import SUPPORTED_ALPHABETS, convert_alphabet, native_to_ipa
from .phones import SAMPA_TO_IPA
from .version import __version__

__all__ = [
    "phonemize", "SAMPA_TO_IPA", "SUPPORTED_ALPHABETS", "native_to_ipa",
    "convert_alphabet", "__version__",
]

#: Languages the phonemizer can handle.
SUPPORTED_LANGS = ("eu", "es")
#: AhoTTS engine versions implemented (see docs/versions.md).
#:   "classic" -- the original AhoTTS engine, used by the HiTZ VITS voices.
#:   "modern"  -- the StyleTTS-era arrandi build, used by HiTZ/StyleTTS2-eu.
SUPPORTED_VERSIONS = ("classic", "modern")
#: Public version name -> internal engine-config key (see versions.CONFIG).
_VERSION_KEY = {"classic": "v1", "modern": "v3"}
#: Basque dialects implemented (see docs/dialects.md).
SUPPORTED_DIALECTS = ("standard", "northern")


def phonemize(text, lang="eu", version="modern", dialect="standard",
              alphabet="native"):
    """Phonemize ``text`` into the AhoTTS single-char IPA training string.

    Parameters
    ----------
    text : str
        Input text.  Numbers, ordinals and roman numerals are expanded to the
        target-language number words; punctuation is preserved as separate
        tokens (``modern``) or dropped (``classic``), matching each engine.
    lang : str, default ``"eu"``
        Target language: ``"eu"`` (Basque) or ``"es"`` (Spanish).
    version : str, default ``"modern"``
        AhoTTS engine to emulate -- ``"classic"`` (the original engine, used by
        the HiTZ VITS voices) or ``"modern"`` (the StyleTTS-era build, used by
        HiTZ/StyleTTS2-eu).  See ``docs/versions.md`` for what each reproduces.
        Ignored when ``dialect="northern"`` (that engine is a single fork).
    dialect : str, default ``"standard"``
        Basque dialect.  ``"standard"`` is the Southern (Batua) engine selected
        by ``version``; ``"northern"`` is the Northern (Iparralde /
        Iparrahotsa) engine -- pronounced /h/, French vowels (ü -> /y/), uvular
        /ʁ/, a remapped sibilant system.  See ``docs/dialects.md``.  Only valid
        for ``lang="eu"``.
    alphabet : str, default ``"native"``
        Output notation, see ``notation.SUPPORTED_ALPHABETS``.  ``"native"``
        (the default) is the AhoTTS single-char training string, unchanged
        from previous releases.  ``"ipa"`` expands the folded affricates,
        stressed vowels and aspirated stops back to plain IPA. Any other
        value is a `scriptconv <https://pypi.org/project/scriptconv/>`_
        phonetic notation (``"x-sampa"``, ``"arpa"``, ``"lexique"``,
        ``"kirshenbaum"``, ``"cotovia"``, ``"rfe"``, ``"mantoq"``), reached by
        first expanding to IPA and then converting. See ``notation.py``.

    Returns
    -------
    str
        Space-separated phonetic tokens in the requested ``alphabet``.  For
        the default ``alphabet="native"`` this is single-char IPA, with
        stressed vowels and multi-char phonemes folded to single characters,
        ready for a StyleTTS2-style model.

    Raises
    ------
    ValueError
        If ``lang``, ``version``, ``dialect`` or ``alphabet`` is not
        supported, ``dialect="northern"`` is combined with a non-Basque
        ``lang``, or a phone has no mapping in the requested ``alphabet``.
    """
    lang = (lang or "eu").lower()
    version = (version or "modern").lower()
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
        native = _phonemize_eu(text, "eu_northern")
        return convert_alphabet(native, alphabet)
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(
            f"version={version!r} is not supported "
            f"(supported: {', '.join(SUPPORTED_VERSIONS)}; see docs/versions.md)"
        )
    key = _VERSION_KEY[version]
    native = _phonemize_es(text, key) if lang == "es" else _phonemize_eu(text, key)
    return convert_alphabet(native, alphabet)
