r"""Multi-alphabet output for the AhoTTS single-char IPA training string.

``phonemize()`` returns the AhoTTS single-char training string by default
(the folded IPA described in ``phones.py``).  This module lets callers ask
for that same phonemization rendered in another phonetic alphabet, via
`scriptconv <https://pypi.org/project/scriptconv/>`_.

Mapping path
------------
native (single-char, folded) -> IPA -> scriptconv notation

The native -> IPA step is *not* a fresh table: it is the exact inverse of the
folding ``ahotts_g2p.g2p`` already performs (``phones.MULTI``), so it lives in
this repo (the fold is AhoTTS-specific) rather than in scriptconv. Every other
character in the native string is already IPA -- ``ahotts_g2p``'s "single
training char" alphabet *is* single-char IPA, per ``phones.SAMPA_TO_IPA``, so
most phones need no translation at all.

IPA -> anything else is delegated entirely to scriptconv (``x-sampa``,
``arpa``, ``lexique``, ``kirshenbaum``, ``cotovia``, ``rfe``, ``mantoq``).
Buckwalter/Arabic are excluded: those are orthographic transliteration
notations, not phonetic ones, and do not apply to a phone string.
"""
from __future__ import annotations

import string

from scriptconv.notation import Notation
from scriptconv.notation import convert as _sc_convert

from .phones import MULTI

#: single training char -> the IPA sequence it was folded from (inverse of
#: ``phones.MULTI``: affricates, stressed vowels, Spanish aspirated stops).
REVERSE_MULTI = {v: k for k, v in MULTI.items()}

# ``phones.MULTI``'s stress-vowel values (``"'i"`` etc.) use an ASCII
# apostrophe as an internal training-corpus shorthand for the dictionary
# STR_MRK stress flag (see phones.py's module docstring) -- it is not the
# IPA stress mark. For genuine IPA output, correct it to U+02C8 MODIFIER
# LETTER VERTICAL LINE, the IPA primary-stress mark (International Phonetic
# Alphabet chart, ipa International Phonetic Association 1999), placed
# immediately before the stressed vowel.
_IPA_PRIMARY_STRESS = "ˈ"
for _native_char, _folded in list(REVERSE_MULTI.items()):
    if _folded.startswith("'"):
        REVERSE_MULTI[_native_char] = _IPA_PRIMARY_STRESS + _folded[1:]
del _native_char, _folded

#: scriptconv notations exposed here, restricted to phonetic ones (Buckwalter
#: / Arabic script transliteration is not applicable to a phone string).
SCRIPTCONV_ALPHABETS = (
    Notation.XSAMPA.value,
    Notation.ARPA.value,
    Notation.LEXIQUE.value,
    Notation.KIRSHENBAUM.value,
    Notation.COTOVIA.value,
    Notation.RFE.value,
    Notation.MANTOQ.value,
)
#: every ``alphabet=`` value ``phonemize()`` accepts.
SUPPORTED_ALPHABETS = ("native", "ipa") + SCRIPTCONV_ALPHABETS

_PUNCT_CHARS = frozenset(string.punctuation)


def native_to_ipa(native: str) -> str:
    """Expand the AhoTTS single-char training string back to plain IPA.

    Reverses the folding ``ahotts_g2p.g2p`` applies (``phones.MULTI``):
    affricates (``C``/``V``/``P``), stressed vowels (``I``/``E``/``A``/``O``/
    ``U``) and the Spanish aspirated stops (``H``/``K``/``T``) each expand
    back to their multi-character IPA sequence. Every other character in the
    native string (``ɡ``, ``ɲ``, ``β``, ``θ``, ``ð``, ``ʃ``, ``ɣ``, ``ʎ``,
    ``ɾ``, ``ʝ``, the Northern-dialect ``ʁ``/``ɟ``/nasal-vowel tildes,
    whitespace, punctuation, ...) is already IPA and is passed through
    unchanged.
    """
    return "".join(REVERSE_MULTI.get(ch, ch) for ch in native)


def convert_alphabet(native: str, alphabet: str) -> str:
    """Convert a native ``phonemize()`` string to *alphabet*.

    Parameters
    ----------
    native : str
        The default ``phonemize()`` output (native single-char string).
    alphabet : str
        One of ``SUPPORTED_ALPHABETS``: ``"native"`` (identity), ``"ipa"``
        (`native_to_ipa`), or a scriptconv phonetic notation (``"x-sampa"``,
        ``"arpa"``, ``"lexique"``, ``"kirshenbaum"``, ``"cotovia"``,
        ``"rfe"``, ``"mantoq"``).

        Punctuation tokens -- surfaced by the ``modern`` engine as their own
        space-separated token (``.``/``,``/``!``/``?``/``;``/``:``) -- are
        left untouched: they are not phones and scriptconv's notation tables
        do not cover them.

    Returns
    -------
    str
        The phonemization rendered in *alphabet*.

    Raises
    ------
    ValueError
        If ``alphabet`` is not one of ``SUPPORTED_ALPHABETS``, or a phone in
        *native* has no mapping in the requested notation (scriptconv is
        called with ``errors="strict"`` -- unmapped symbols always raise,
        never silently drop).
    """
    alphabet = (alphabet or "native").lower()
    if alphabet not in SUPPORTED_ALPHABETS:
        raise ValueError(
            f"alphabet={alphabet!r} is not supported "
            f"(supported: {', '.join(SUPPORTED_ALPHABETS)})"
        )
    if alphabet == "native":
        return native
    ipa = native_to_ipa(native)
    if alphabet == "ipa":
        return ipa

    out = []
    for tok in ipa.split(" "):
        if tok == "" or all(c in _PUNCT_CHARS for c in tok):
            out.append(tok)
            continue
        try:
            out.append(_sc_convert(tok, Notation.IPA, alphabet, errors="strict"))
        except ValueError as e:
            raise ValueError(
                f"cannot convert {tok!r} (from {native!r}) to "
                f"alphabet={alphabet!r}: {e}"
            ) from e
    return " ".join(out)
