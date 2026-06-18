# METHOD_INVENTORY.md — AhoTTS eu/es linguistic pipeline, method-by-method port status

Per-method map from the AhoTTS C/C++ source to the pure-Python port, with a
faithfulness verdict for each. The port reimplements the **algorithm** of each
C method in stdlib Python (clean-room style: logic and data tables, not source
text); the GPL-3.0 C source is read only as the specification.

Source trees (both latin-1 / ISO-8859):

* **V1**: `~/AgentWorkspaces/ml/pyAhoTTS/src`
* **V2/V3**: `~/AgentWorkspaces/ml/tts/styletts2-eu-export/upstream-AhoTTS/libhtts/src`
  (the `eu_*.cpp` / `es_*.cpp` files are byte-identical to the V1 tree apart from
  the GPL header and two additive, default-FALSE config branches; one port,
  parameterised by config + dict + wrapper, covers all three generations).
* **V3 wrapper**: `…/StyleTTS2_basque/phonemizer/eu_phonemizer.py`
  (`normalize` + `getPhonemes`) and `…/v3-modulo1y2/eu_phonemizer_v2.py`.

Verdict legend:

* **FAITHFUL** — algorithm ported 1:1 from the cited C method; behaviour follows
  from the source.
* **DERIVED-TABLE** — values read from shipped data (`.dic` bitfields,
  `symbolexp.c` table) or transcribed verbatim from a source constant table;
  faithful by construction.
* **REWRITTEN-THIS-PASS** — ported or corrected in the current pass to be
  faithful (was missing or approximated before).
* **PROVEN-BINARY-ARTIFACT** — the shipped binary/wrapper provably deviates from
  the readable source; the port reproduces the binary (ground truth) and the
  deviation is documented with the exact line.

---

## Engine entry / text→utterance (t2u)

| C source | Port symbol | Verdict |
|---|---|---|
| `t2u_do.cpp` / `input_multilingual` driver | `phonemize` / `phonemize_es` | FAITHFUL (pipeline order) |
| `eu_numexp.cpp` `expnum`/`upTo99`/`upTo999`/`get1E3n` | `expnum`,`_upto99`,`_upto999`,`_get1e3n` | FAITHFUL |
| `eu_decli.cpp` `dekline`/`isGroupDecd` | `_decline`, `_DECL_SUFFIX` gate in `_expand_one` | FAITHFUL + DERIVED-TABLE (EU_DEC suffixes read from dict) |
| `eu_romanhilvl.cpp` roman→ordinal | `_roman_to_int`, `number_to_basque_words(ordinal=True)` | FAITHFUL |
| `eu_romanhilvl` + `eu_decli` `ROMAN.suffix` fusion | `_merge_roman_dot`, `_normalize_v3` roman-dot fold | **REWRITTEN-THIS-PASS** (was split into two tokens; now declines the ordinal and fuses — XX.aren→hogeigarrenaren; V1/V3 only, V2 spells the roman) |
| `eu_abbacr.cpp` `isAbbAcrUni`/`expAbbAcrUni` (NOR=acr exp) | `_expand_one` exp-field branch | FAITHFUL + DERIVED-TABLE |
| `eu_percent.cpp` | `_expand_one` `%` branch | FAITHFUL |
| `eu_numexp` thousands grouping | `_merge_thousands` | FAITHFUL |
| `symbolexp.c` / `eu_symbolexp` symbol→word | `_SYM_PUNCT`/`_SYM_MID`/`_SYM_ALWAYS`, `_normalize_v3` | DERIVED-TABLE |
| `symbolexp` mid-glued colon → "bi puntu" | `phonemize` `(?<=\w):(?=\w)` rule | **REWRITTEN-THIS-PASS** (glued colon was dropped; now verbalised on all paths; spaced colon stays a pause) |
| libhtts citation-hyphen → "gidoia" (V1/V2) | `phonemize` `(?<=[«"“])-(?=\w)` rule | **REWRITTEN-THIS-PASS** (V1/V2 only; «-kuntza»→gidoia kuntza; spaced parenthetical dash left alone) |

## Dictionary / HDIC

| C source | Port symbol | Verdict |
|---|---|---|
| `eu_hdic.cpp` HDIC on-disk format, `eu_hdic.hpp` bitfield | `load_dict`, `_hdic_blocks` | FAITHFUL (bitfield) + DERIVED-TABLE |
| `pos1.cpp::posdic` / `dic->search` block selection | `_dict_lookup`, `_normalize_word_keepcase` | FAITHFUL |
| TF_MRK transcription field decode | `_tf_exp_to_internal` | FAITHFUL |

## POS / FGRP / stress (accentual V1/V3 path; flat V2)

| C source | Port symbol | Verdict |
|---|---|---|
| `eu_categ.cpp::utt_categ` + posdic/aditudu/babait/atzadi/atzize | `_tag_word`, `_faithful_tagger`, `_empty_pos` | FAITHFUL + DERIVED-TABLE |
| `poscases.cpp` disambiguation pass | `_poscases` | FAITHFUL |
| `eu_gf.cpp::utt_gf` + gfize/gfadi groupers | `_fgrp_grouping` | FAITHFUL |
| `eu_stre.cpp::fgrp2agrp` (AGRP types) | `_agrp_types`, helpers `_is_mono/bisyllable`,`_ends_ko_go_ten_tzen` | FAITHFUL |
| `eu_stre.cpp::agrp_stress` + `eu_stuti.cpp` | `_agrp_stress`, `_stress_nth_syllable`, `_group_to_singlechar` | FAITHFUL |
| `eu_syl.cpp::word_syllab` + `eu_uti` diphthong helpers | `syllabify`, `_is_diphthong`, `_is_valid_cc`, `_is_vowel`, `_syllable_vowel` | FAITHFUL |
| SALBTF phonetic-exception flag tests (`trans_fonet_salb_*`) | `_salbtf_j_x/_l_l/_n_n`, `_word_j_x`,`_no_palatal_n`,`_word_l_l`,`_is_verbo_trn_lgn`,`_word_is_verb/_aux_or_syn` | FAITHFUL + DERIVED-TABLE |

## g2p (grapheme→phoneme)

| C source | Port symbol | Verdict |
|---|---|---|
| `eu_phtr.cpp::pausegr_ch2ph` full context switch (b/d/g approximants, n→m/ɲ, l→ʎ, r/rr, tx/tz/ts/tt/dd, i/u glides, silent h, c/q/v/x/y/z cases, ez/ba/bait proclitic sandhi, tf_mrk_ch2ph) | `g2p_group` | FAITHFUL (the `v`-after-consonant plosive case is a documented PROVEN-BINARY-ARTIFACT, see NOTES.md) |
| `phmap.cpp` / `phone.c` / `phone_tosampa` → `pho2sampa` | SAMPA→IPA→single-char tables in oracle + `_group_to_singlechar` | DERIVED-TABLE |

## OOV / foreign-word path (the eu-100% blocker — primary mandate this pass)

| C source | Port symbol | Verdict |
|---|---|---|
| `eu_normal.cpp:382-400` isCap routing → expandCell / pronounce / mayusDekline | `_expand_one` OOV branch (class-2/5 → pronounce; class-3 → spell; class-1 acronym) | **REWRITTEN-THIS-PASS** |
| `eu_cap.cpp::isCap` (class 1/2/3/5) | inline case tests in `_expand_one` (`islower`/Title/mixed/upper) | FAITHFUL |
| `eu_cap.cpp:203-792 ::pronounce` (y→i vowelisation, s+C→es, double-letter collapse ee→i oo→u, h/c rewrites incl. initial h→j sh→x ph→f chr→cr ch→tx ce/ci→z ck→k, m→n before C, v/w/q, iterative cluster strip, rr/ll restore, final s/n restore) | `_pronounce` + `_pronounce_strip` | **REWRITTEN-THIS-PASS** (was entirely MISSING — OOV words fell straight into g2p) |
| `eu_pronun.cpp::isPronun` + `eu_str2grpStr`/`filterStr`/`eu_getGroup`/`eu_str2GrpLst` + valid-group tables | `_is_syllabifiable`, `_eu_str2grpStr`, `_eu_filter_str`, `_EU_GETGROUP`, `_EU_VALID` | FAITHFUL + DERIVED-TABLE. **Corrected this pass**: `eu_getGroup` resolves a single `w` to OCLU ('O') via `eu_ocluStr="b g w"` (checked before `eu_oclu4Str`), not the unreachable OCLU4 ('W') — the port table had `w→'W'`, fixed to `w→'O'`. |
| `eu_speller.cpp::expandCell`/`spellCell` (`eu_getchexp`) | `_acronym_words` letter-spell branch, `_LETTER_NAME` | FAITHFUL + DERIVED-TABLE |
| accent fold for OOV test (`symbolexp.c`/`eu_t2l` Á..Û → base vowel) | `_normalize_word` accent map; OOV branch tests/rewrites the folded form | **REWRITTEN-THIS-PASS** (nô was mis-classified as vowel-less and spelled; now folds ô→o → read as nO) |

## V3 wrapper (modulo1y2 -TxtMode=Word + eu_phonemizer)

| C / Python source | Port symbol | Verdict |
|---|---|---|
| `modulo1y2 -TxtMode=Word` (the C text-normaliser) | `_normalize_v3` | FAITHFUL (symbol/quote/dash/colon/roman rules) |
| `eu_phonemizer.py::getPhonemes` word/punct interleave: `\w+|[^\w\s]` split, non-punct count, padding, punct re-emitted as own token | `phonemize` keep_punct branch; es `_v3_interleave` | FAITHFUL on the interleave; the upstream **ASCII-`string.punctuation` count bug is FIXED** — port counts punctuation Unicode-aware so ¿/¡ no longer trigger the duplicate-last-phoneme doubling (see below) |
| `eu_phonemizer.py::_transform_multichar_phonemes` (MULTICHAR_TO_SINGLECHAR) | single-char tables | DERIVED-TABLE |

---

## Wrapper bug FIXED in the port (not reproduced)

1. **es-v3 `¿`/`¡` last-phoneme doubling** — `¿Qué hora es?` → buggy
   `kE Oɾa Es Es ?`; `¡Hola!` → buggy `Ola Ola !`. Root cause in the wrapper
   `getPhonemes`: it counts "non-punctuation words" with Python
   `string.punctuation`, which is **ASCII-only**, so `¿`/`¡` (and «»/“”/–—) are
   counted as words (the engine emits no phoneme group for them). The count
   mismatch (N+1 counted words vs N groups) triggers the padding loop
   `while len(cleaned_phonemes) < len(non_punct_words): cleaned_phonemes.append(cleaned_phonemes[-1])`,
   duplicating the last group. There is no linguistic ambiguity — the output is
   simply wrong — so the port **fixes** it: `es_phonemizer._v3_interleave`
   classifies punctuation with `unicodedata.category(c).startswith('P')`, which
   recognises `¿`/`¡`, keeps the word/group counts aligned, and yields the
   correct `kE Oɾa Es ?` / `Ola !` with no doubling. The legitimate
   fewer-groups-than-words pad remains. The same bug is fixed at source in the
   `ahotts-g2p` and `pyAhoTTS` wrappers (TigreGotico repos we own).

## Proven binary artifacts (binary ≠ readable intent; port reproduces the binary)

2. **g2p `v`-after-consonant plosive** — `eu_phtr.cpp` case `'v'` as written only
   plosivises `v` after n/m; the binary surfaces plosive `b` for `v` after any
   non-`l` consonant. Documented in NOTES.md; port emulates the binary.

3. **`urte` artifact** — pre-existing, documented in NOTES.md.

---

## Residual mismatches (faithful port, still not 100% on the held-out eu corpus)

After this pass, on the 430-line held-out eu corpus (positional/cascade scoring;
difflib-aligned word accuracy in parentheses):

* eu v1: words 98.87%, lines 419/430 (aligned 99.63%)
* eu v2: words 97.60%, lines 417/430 (aligned 99.32%)
* eu v3: words 99.10%, lines 414/424 (aligned 99.69%)
* es v1/v2/v3: **100.00% words + lines** (held-out).

The remaining eu deltas are a small, enumerated set of individual edge cases, not
a systemic path gap:

* **`N-634` style alphanumeric codes** — binary spells the digit run
  (`gidoia sei hiru lau`); the port reads 634 as a cardinal. `eu_numexp` code vs
  cardinal disambiguation — not yet ported.
* **`5-10` number range** — port glues `bost`+`hamar` in one pause group → the
  st→s sandhi drops the t (`bOs`); the binary keeps the range parts as a word
  boundary (`bOst amAr`). Range-hyphen boundary not yet modelled.
* **`K.a.` / `V.ak`** — dotted single-letter abbreviation expansion
  (Kristo aurretik / uve puntuak) — not yet ported.
* **`Julian` / `Beilarien`** — proper-noun stress (STR_MRK suffix-prefix
  over-inheritance) and the `ei`→`ej` glide gated by SALBTF/verb flags that the
  word does not carry — per-word POS-flag edge cases.
* **`HABE,…` / `LTDan` / `NBEk`** — acronym-with-suffix expansion length.

Each is a localised normalisation/POS detail with a clear C reference; none
require re-touching the OOV / g2p / stress cores, which are faithful.
