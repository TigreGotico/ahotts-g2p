"""Engine versions and the per-version configuration table.

The original AhoTTS (``aholab/AhoTTS``) and its 2025 ``ahotts_common`` rewrite
(the same repository, later commit) are the same linguistic engine: every
``eu_*`` source file is identical apart from the licence header and two additive
config branches in the rewrite (``phtiparralde`` and ``StressDicSingleWords``).
A single faithful port, parameterised by the table below, reproduces every
version; the real differences are which dictionary is loaded, whether dictionary
``STR_MRK`` stress is applied or bypassed for a flat rule, and the wrapper around
the engine (``libhtts.transcribe`` for V1/V2 versus the ``modulo1y2`` +
``eu_phonemizer`` pipeline for V3, which tokenises punctuation).

(``pyAhoTTS`` builds the V1 engine from ``ekaitz-zarraga/AhoTTS``, a packaging
fork of ``aholab/AhoTTS`` with build/portability changes only.)

See ``docs/versions.md`` for the version -> upstream source -> consuming model
mapping.
"""
from enum import Enum


class Lang(str, Enum):
    """Supported languages."""

    EU = "eu"
    ES = "es"


class Version(str, Enum):
    """AhoTTS engine generations.

    * ``V1`` -- original AhoTTS (``ekaitz-zarraga/AhoTTS``); the family the
      HiTZ VITS voices use.  Accentual-group stress with dictionary
      ``STR_MRK`` first-syllable marking; vowel offglides (``au`` -> ``aw``).
    * ``V2`` -- the Dec-2025 ``ahotts_common`` ``transcribe`` variant.  No
      vowel offglides (diphthongs stay full vowels) and a plain
      "2nd-syllable" stress rule for every word.  No released model uses it;
      it is provided for completeness.
    * ``V3`` -- the StyleTTS-era ``arrandi`` ``modulo1y2`` build (newer
      ``eu_dicc_20250326`` dictionary), used by HiTZ/StyleTTS2-eu.  Like V1
      but with a silent-``h`` stress shift and punctuation emitted as tokens.
    """

    V1 = "v1"
    V2 = "v2"
    V3 = "v3"


#: Each key names a real source switch or a documented binary delta:
#:   dict         -- eu_dicc file (V3 = eu_dicc_20250326)
#:   StressDic    -- LangEU_PhTrans::StressDicSingleWords (off in all binaries)
#:   phtiparralde -- LangEU_PhTrans::phtiparralde (off; southern dialect)
#:   accentual    -- USE_TOKENIZER fgrp2agrp/agrp_stress path (dict STR_MRK,
#:                   clitics).  When off, the flat word_stress path is used.
#:   glides       -- render iu2jw offglides as j/w (True) vs full vowels (V2)
#:   keep_punct   -- emit punctuation as separate tokens (V3)
#:   h_shift      -- silent leading h anchors an empty syllable, shifting
#:                   audible stress one syllable earlier (V3)
#:   kdrop_xword  -- V1 foreign-word final-k drop
CONFIG = {
    "v1": {"dict": "eu_dicc_v1.dic", "StressDic": False, "phtiparralde": False,
           "accentual": True,  "glides": True,  "keep_punct": False,
           "h_shift": False, "kdrop_xword": True},
    "v2": {"dict": "eu_dicc_v1.dic", "StressDic": False, "phtiparralde": False,
           "accentual": False, "glides": False, "keep_punct": False,
           "h_shift": False, "kdrop_xword": False},
    "v3": {"dict": "eu_dicc_v3.dic", "StressDic": False, "phtiparralde": False,
           "accentual": True,  "glides": True,  "keep_punct": True,
           "h_shift": True, "kdrop_xword": False},
}

#: V1 and V2 share a dictionary; V3 ships the newer eu_dicc_20250326.
DICT_FILES = {v: cfg["dict"] for v, cfg in CONFIG.items()}
