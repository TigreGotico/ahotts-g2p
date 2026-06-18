"""Engine versions and the per-version configuration table.

The original AhoTTS (``aholab/AhoTTS``) and its 2025 ``ahotts_common`` rewrite
(the same repository, later commit) are the same linguistic engine: every
``eu_*`` source file is identical apart from the licence header and two additive
config branches in the rewrite (``phtiparralde`` and ``StressDicSingleWords``).
A single faithful port, parameterised by the table below, reproduces every
version; the real differences are which dictionary is loaded and the wrapper
around the engine (``libhtts.transcribe`` for V1 versus the ``modulo1y2`` +
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
    * ``V3`` -- the StyleTTS-era ``arrandi`` ``modulo1y2`` build (newer
      ``eu_dicc_20250326`` dictionary), used by HiTZ/StyleTTS2-eu.  Like V1
      but with a silent-``h`` stress shift and punctuation emitted as tokens.

    The ``v1``/``v3`` labels are kept as-is: the gap reflects the real engine
    lineage rather than a contiguous numbering.
    """

    V1 = "v1"
    V3 = "v3"


#: Each key names a real source switch or a documented binary delta:
#:   dict         -- eu_dicc file (V3 = eu_dicc_20250326)
#:   StressDic    -- LangEU_PhTrans::StressDicSingleWords (off in all binaries)
#:   phtiparralde -- LangEU_PhTrans::phtiparralde (off; southern dialect)
#:   accentual    -- USE_TOKENIZER fgrp2agrp/agrp_stress path (dict STR_MRK,
#:                   clitics).
#:   glides       -- render iu2jw offglides as j/w
#:   keep_punct   -- emit punctuation as separate tokens (V3)
#:   h_shift      -- silent leading h anchors an empty syllable, shifting
#:                   audible stress one syllable earlier (V3)
#:   kdrop_xword  -- V1 foreign-word final-k drop
CONFIG = {
    "v1": {"dict": "eu_dicc_v1.dic", "StressDic": False, "phtiparralde": False,
           "accentual": True,  "glides": True,  "keep_punct": False,
           "h_shift": False, "kdrop_xword": True},
    "v3": {"dict": "eu_dicc_v3.dic", "StressDic": False, "phtiparralde": False,
           "accentual": True,  "glides": True,  "keep_punct": True,
           "h_shift": True, "kdrop_xword": False},
    # Northern Basque (Iparralde / Iparrahotsa): a V1-lineage fork of the engine
    # with PhTIparralde enabled.  /h/ is pronounced, ü -> /y/, the rhotic is
    # uvular /ʁ/, the sibilant system is remapped (s -> ʂ, z -> s, ts -> tʂ,
    # tz -> ts), j/y/dd -> /ɟ/, tch -> tx.  V1 accentual stress with the Northern
    # dictionary's STR_MRK; no silent-h stress shift; punctuation dropped.
    "eu_northern": {"dict": "eu_dicc_northern.dic", "StressDic": False,
                    "phtiparralde": True, "accentual": True, "glides": True,
                    "keep_punct": False, "h_shift": False, "kdrop_xword": True},
}

#: V1 loads the original eu_dicc; V3 ships the newer eu_dicc_20250326.
DICT_FILES = {v: cfg["dict"] for v, cfg in CONFIG.items()}
