# Version-aware pure-Python AhoTTS Basque (eu) phonemizer

Pure-Python (stdlib-only) reimplementation of the AhoTTS Basque linguistic
front-end, ported **from the C++ source** and parameterised by an explicit
per-version config table.  `phonemize(text, version="v1"|"v2"|"v3")` returns the
final single-char IPA training string (the representation StyleTTS2-eu / HiTZ
VITS train on).

## Latest pass — OOV / foreign-word path (method-by-method audit)

See `METHOD_INVENTORY.md` for the full per-method C-source → port → verdict map.
This pass closed the eu OOV / foreign-word gap by porting the methods that were
previously missing or approximated:

* **`eu_cap.cpp::pronounce` ported 1:1** (`_pronounce` + `_pronounce_strip`) —
  the foreign-word rewrite (y→i vowelisation, double-letter collapse, h/c
  rewrites, m→n/v/w/q, iterative impronounceable-cluster strip, rr/ll + final
  s/n restore).  It was entirely missing; OOV words used to fall straight into
  g2p.  Now Gehry→ɡeɾI, Olympique→olImpike, Bayonnais→baʝOnajs,
  Hoffmeyer→ɟofmEʝer, Qasi→asI, Aymeric→ajmEɾik, flysch→flIs(t) all match.
* **`eu_normal.cpp` isCap routing** wired in `_expand_one` (class 2/5 → pronounce,
  class 3 mixed → expandCell spell — DiPC→"de i pe ze").
* **`eu_getGroup` w-class fix** — a single `w` resolves to OCLU ('O') via
  `eu_ocluStr="b g w"`, not the unreachable OCLU4 ('W'); the port table was
  corrected (web→uEβ).
* **accent fold for the OOV gate** — nô folds ô→o so it is read (nO), not spelled.
* **`ROMAN.suffix` ordinal-declension fusion** (`_merge_roman_dot`, `_normalize_v3`
  roman-dot fold) — XX.aren→hogeigarrenaren, IV.a→laugarrena (V1/V3; V2 spells).
* **mid-glued colon → "bi puntu"** and **V1/V2 citation-hyphen → "gidoia"**
  («-kuntza»→gidoia kuntza), with the spaced parenthetical dash left untouched.

**es-v3 `¿`/`¡` doubling is a wrapper bug — FIXED in the port (not reproduced).**
`eu_phonemizer.py::getPhonemes` counts non-punct words with ASCII
`string.punctuation`, so `¿`/`¡` (and «»/“”/–—) are miscounted as words; with one
fewer phoneme group than counted words, the pad-with-last-group loop doubles the
last group (`¿Qué hora es?` → `kE Oɾa Es Es ?`).  The modulo1y2 binary + wrapper
produces that doubled output, but there is no linguistic ambiguity — it is simply
wrong.  The port (`es_phonemizer._v3_interleave`) counts punctuation Unicode-aware
(`unicodedata.category(c).startswith('P')`), keeping the word/group counts
aligned, so it emits the correct `kE Oɾa Es ?` with no doubling.  The same bug is
fixed at source in the `ahotts-g2p` / `pyAhoTTS` wrappers we control.

Held-out corpus after this pass (positional / difflib-aligned):
eu v1 98.87% / 99.63%, v2 97.60% / 99.32%, v3 99.10% / 99.69%;
es v1/v2/v3 100% words + lines.  Remaining eu deltas are an enumerated set of
individual edge cases (N-634/5-10 code spelling on the V1/V2 libhtts path,
K.a./V.ak dotted abbreviations, Julian/Beilarien per-word POS-flag stress/glide),
each with a C reference in `METHOD_INVENTORY.md`; none are systemic.

## Method (source-first)

The port is built **from the source code**, not by diffing binary outputs.  The
binaries are used only to *validate* the source port and, where a binary
provably deviates from the public source, to characterise that deviation in a
documented, versioned way.

Two source trees were read (both latin-1; read with `iconv -f latin1 -t utf-8`):

| Tree | Path | Role |
|---|---|---|
| **pre-Dec-2025 AhoTTS** (ekaitz / pyAhoTTS) | `~/AgentWorkspaces/ml/pyAhoTTS/src` | complete public eu engine |
| **Dec-2025 ahotts_common rewrite** (aholab/AhoTTS @ `3d6f7fc`) | `…/upstream-AhoTTS/libhtts/src` | the V2/V3 engine |

**Key source finding — the two trees are the SAME engine.**  Every `eu_*.cpp`
file is byte-identical between the two apart from (a) the GPL header pyAhoTTS
prepends and (b) two *additive* config branches in the rewrite:
`phtiparralde` (`eu_phtr.cpp`, northern dialect) and `StressDicSingleWords`
(`eu_stre.cpp::fgrp2agrp`, the "astuna" heavy-syllable mode).  Both default to
**FALSE** (`LangEU_PhTrans()` ctor, `eu_lingp.hpp`), and with both FALSE the
rewrite reduces *exactly* to the old engine.  So **one** faithful port,
parameterised by config + dict + wrapper, reproduces all versions.  This is the
correction to the previous round, which wrongly treated V2/V3 as "V1 + output
deltas".

## The single engine (source files → port functions)

`eu_w2ph.cpp::utt_w2phtr` is the pipeline; the port mirrors it stage for stage:

1. **g2p** — `eu_phtr.cpp::pausegr_ch2ph` → `g2p_group()`.  Per pause group,
   grapheme→phoneme with the full context switch: b/d/g approximants
   (intervocalic & after l/r), n→m before labials, n→ɲ / l→ʎ palatalisation
   after `i` (gated by the dict SALBTF `n_n`/`l_l` exception flags and the
   verb-before-`i` case), intervocalic r vs trill rr, digraphs tx/tz/ts/tt/dd,
   i/u glides (au→aw, ai→aj …), silent `h`, the `c/q/v/x/y/z` cases, and the
   `ez/ba/bait` + verb proclitic sandhi (d→t, g→k, b→p, z drop).
2. **syllabification** — `eu_syl.cpp::word_syllab` + `eu_uti` diphthong helpers
   → `syllabify()` / `_is_diphthong` / `_is_valid_cc`.
3. **POS tagging** — `eu_categ.cpp::utt_categ` + `posdic`/`aditudu`/`babait`/
   `atzadi`/`atzize` → `_tag_word()`.  Full dict match copies every TALDE field
   (decoded from the HDIC bitfield, `eu_hdic.hpp` layout) and STR_MRK; unfound
   words fall through the suffix-recovery cascade and inherit STR_MRK / the
   SALBTF flags from the longest dictionary-key prefix (`_inflected_str_mrk`,
   `_dict_lookup`).
4. **FGRP grouping** — `eu_gf.cpp::utt_gf` + `gfize.cpp`/`gfadi.cpp` groupers
   (enk, detize, izedet, izeadb, adbadj, izeize, baitadi, joklgn, jokjok, trn,
   jnt) → `_fgrp_grouping()`, an ordered first-match-wins left-to-right pass.
5. **AGRP type + stress** — `eu_stre.cpp::fgrp2agrp` + `agrp_stress` →
   `_agrp_types()` + `_agrp_stress()`.  Default OROK (2nd syllable of the
   group; 1st if monosyllabic); STR_MRK→MRK (1st); LOT_JNT coordinator→GABE;
   bisyllabic conjugated-verb -ko/-go/-ten/-tzen→MRK; proclitic / conjugated-verb
   look-aheads de-accent a following verb/auxiliary→NONE (only *within* the same
   FGRP, exactly as `fgrp2agrp` iterates `wordNext(URANGE_FGRP)`).
6. **number / date / abbreviation expansion** — `eu_numexp.cpp`,
   `eu_numhilvl.cpp` (thousands `.` separator), `eu_decli.cpp` (glued
   case-suffix on a digit form), `eu_percent.cpp`, `eu_romanhilvl.cpp` →
   `expnum()` / `number_to_basque_words()` / `_decline()` / `_expand_one()`.
   Faithful Basque vigesimal cardinals: `upTo99` glues "ta" (hogeita), `upTo999`
   inserts "eta", `expnum` walks the ternas (mila/miloi/biloi) with the
   eta-copula rule; the "rehun" hundreds (hirurehun=300) are literal table
   entries.

## The two stress paths (the V1/V3 vs V2 distinction is in the SOURCE)

`eu_w2ph.cpp::utt_w2phtr` selects, by `#ifdef USE_TOKENIZER`:

* **accentual path** (`fgrp2agrp` + `agrp_stress`): uses the dictionary POS —
  STR_MRK 1st-syllable marking, LOT_JNT/clitic de-accenting, the whole AGRP
  machinery.  This is the **V1 / V3** behaviour.
* **flat path** (`word_stress`): plain "2nd syllable, 1st if monosyllabic" for
  every word, with no effective dictionary-driven stress.  This is the **V2**
  (HiTZ VITS `ahotts/tts`) behaviour.

**Verified against the source compiled here.** `upstream-AhoTTS/libhtts/build/
src/libhtts.so` is the Dec-2025 source built with default flags.  Run through
its `transcribe` entry point it produces the **flat** signature
(`euskara`→`euskAɾa`, `horrek`→`orEk` 2nd-syllable, `eta`→`etA` stressed, `ez
da`→both stressed) — i.e. it applies *zero* dictionary POS/STR_MRK/clitic
effects, with everything defaulting to OROK 2nd-syllable.  pyAhoTTS (V1), the
**same eu rules + same dict**, instead gives the accentual signature
(`euskara`→`Ewskaɾa` 1st-syllable).  So the V1↔V2 split is the
accentual-vs-flat stress path of the one engine, not two codebases.  The port's
V2 flat path matches the source-compiled libhtts exactly on the probed
vocabulary (12/12 on a spot set incl. euskara/horrek/hizkuntza/eta/etxe/bat).

## Per-version config (`_CONFIG` in `ahotts_versioned.py`)

| flag | source switch | v1 | v2 | v3 |
|---|---|---|---|---|
| `dict` | `HDicDBName` | eu_dicc (old) | eu_dicc (old) | **eu_dicc_20250326** |
| `accentual` | `USE_TOKENIZER` path (`eu_w2ph`) → fgrp2agrp/agrp_stress vs word_stress | **on** | **off** (flat) | **on** |
| `glides` | `iu2jw` offglide rendered j/w vs full vowel | on | **off** | on |
| `StressDic` | `StressDicSingleWords` (`eu_stre`) | off | off | off (none of the binaries enable astuna) |
| `phtiparralde` | `phtiparralde` (`eu_phtr`) | off | off | off (southern) |
| `keep_punct` | modulo1y2 / `eu_phonemizer` wrapper | off | off | **on** |
| `h_shift` | modulo1y2 delta (silent leading h anchors an empty syllable) | off | off | **on** |
| `kdrop_xword` | cross-word final-`k` drop before a `k`-initial word (V1 binary only) | **on** | off | off |

`StressDic` and `phtiparralde` are OFF for all three: the public source is a
*superset* (it has the astuna and Iparralde modes) but none of the shipped
binaries enables them — confirmed by reading the flags' defaults and by the
absence of astuna/Iparralde behaviour in every oracle.

## Oracles (validation only)

| Ver | Oracle | What it is |
|---|---|---|
| V1 | pyAhoTTS `libhtts_x86_64.so` (`pyahotts.AhoTTS`) | pre-Dec-2025 source, accentual path, old dict |
| V2 | source-built `upstream-AhoTTS/libhtts/build/src/libhtts.so` (and HiTZ `ahotts/tts`) | Dec-2025 source, flat path |
| V3 | arrandi `modulo1y2` via `eu_phonemizer.py` | ahotts_common build + eu_dicc_20250326 + punctuation wrapper |

`dump_oracles.py` caches their per-sentence output to `oracle_dump.json`;
`validate.py` scores the port against it (per-version word-match % + exact-line
%).  The shipped port needs none of the binaries — pure stdlib + the two `.dic`
files.

## Accuracy (held-out corpus.txt, 430 sentences)

```
[v1] words 4990/5137 = 97.14%   lines 402/430 = 93.5%
[v2] words 4968/5164 = 96.20%   lines 401/430 = 93.3%
[v3] words 6012/6119 = 98.25%   lines 404/424 = 95.3%  (6 empty-oracle rows excluded)
```

The two previously probe-derived tables are now **source-grounded** (no
hand-typed values):

* **Letter-name table (`_LETTER_NAME`)** — read verbatim from
  `symbolexp.c::eu_symbolexp[256]` (rows [065]A..[090]Z / [097]a..[122]z), the
  table `eu_speller.cpp::spellCell` indexes via `eu_getchexp(c)`.  Byte-identical
  in both source trees.  Corrected `y` -> "i grekoa" (source row [089]/[121]; a
  probe round had "i").
* **Declension/case-suffix set (`_DECL_SUFFIX`)** — `eu_decli.cpp::isGroupDecd`
  carries NO hand list; it queries `HDIC_QUERY_EU_DEC` (bit 2, `eu_hdic.hpp:159`)
  on the trailing cell and requires `MATCHLEN==0`.  `_read_decl_suffixes()` now
  reads that bit straight from the `.dic`, yielding the full 282-entry EU_DEC set
  (identical in eu_dicc_v1 and eu_dicc_20250326), replacing the 40-entry guess.

Run: `~/.venvs/ovos/bin/python3 validate.py --version all` (cached dump; add
`--live` to recompute from the binaries; add `--csv FILE` to dump a per-word
mismatch CSV — port-out / binary-out / source-word / sentence — produced by
difflib sequence alignment per sentence, so a single inserted token does not
cascade into every downstream word).

Six V3 rows are excluded from V3 scoring: on those inputs the `modulo1y2`
binary aborts on raw `«» – —` characters and returns an *empty* line, which is
not ground truth (`validate.py` skips empty-oracle rows).

## Source-port modules added/fixed (from source, not diffing)

This round root-caused every mismatch pattern against the C source and **removed
the previous `urte`/`eva`/`lantze` 3-stem hack**, replacing the prefix-string
POS approximation with a faithful port of the engine's actual lookup + POS
cascade.  New/changed modules:

* **Faithful HDIC binary search** (`_faithful_search.FaithfulHDic`) — exact port
  of `eu_hdic.cpp::searchBin` + `hdic_do.cpp::tokbsearch`, operating on the four
  on-disk sorted blocks with raw-byte `strncmp`, the four-block "longest wins"
  selection, the partial-search loop, and the **stateful `hitlen`** class member
  (reset per `HDicDB::search`, not between the four block calls inside one
  `searchBin`).  This is the real bisection trajectory, MATCHLEN and all.
* **Faithful POS cascade** (`_eu_pos.EuPOS.tag`) — ports `eu_categ.cpp::utt_categ`
  + `pos1.cpp` (`posdic`, `aditudu`, `babait`, `atzadi`, `adit`, `auxt`,
  `atzize`) on top of the faithful search.  The load-bearing detail is the C
  **`setPOS` (clear) vs `addPOS` (keep)** semantics: a partial-match form first
  gets POS_EU_STR_MRK *added* (eu_categ STR_MRK block, gated on
  `encontrado==FALSE`), but if the suffix cascade then recognises it as an
  inflected **verb** (`adit`/`auxt`/`atzadi` ko-go call `setPOS`) the inherited
  STR_MRK is **wiped → the verb form surfaces OROK**; a noun suffix (`atzize`
  uses `addPOS`) keeps it.  Drives igotzen/jasotzen/gordetzea/irakasten/idazten →
  OROK while euskarak/bakarra/mugak/kontuan keep MRK.  The cascade runs even when
  the word is not in the dict at all (hDicRef==NULL), so morphological verbs like
  `ematen`/`emititzen` are recognised (their stem reconstruction keeps the
  `adi[:i+1]` boundary, matching the C `adi_temp` rebuilds).
* **fgrp2agrp faithful `p`-advance** (`_agrp_types`) — `eu_stre.cpp::fgrp2agrp`
  is called once per FGRP group and walks it with `for(p; p; p=wordNext(p))`; the
  `es_proclitico`/`es_verbo_jok` branches *reassign* `p` and set the NEXT word's
  AGrp (OROK/NONE), so that word is skipped and its own MRK is overwritten.
  Reproduced with an explicit per-group index that the look-ahead may advance.
  Fixes `emititzen hasi`→hasi OROK.
* **jokjok grouper** (`_fgrp_grouping`) — now keys on ADI_JOK **or** ATZ_ADI1 for
  both the head and the next word and also merges a trailing ADI_LGN/ATZ_ADI3
  aux (`gfadi.cpp::jokjok` verbatim), so `-tzen`/`-ten` verb + verb chains merge
  and de-accent the following verb.
* **TF_MRK phonetic transcription** (`_tf_exp_to_internal`, g2p TF branch) — the
  dict TF_MRK words carry their pronunciation in `exp` (dotted SAMPA
  `x.e.n.e.r.o`, or a respelling `bum`); `eu_phtr.cpp` applies it whenever the
  word carries POS_EU_TF_MRK (`trans_fonet_hitza`), **independent of
  StressDicSingleWords** (the previous "exclude TF" note was wrong).  Rendered
  verbatim for exact-TF matches.  Fixes boom→bUm, genero→xenEɾo, ibili→iβIʎi
  (the last replaces the old "verb-before-l" deviation — it was always the dict
  TF transcription).
* **SALBTF `j_x`** (`_word_j_x`, g2p case 'j') — words flagged SALBTF_J_0_X
  (juan, julian, jatorri, erlijio, jende) pronounce `j` as Spanish jota `x`.
* **n→m before a labial across a word/hyphen** (g2p case 'n') — `v` counts as a
  labial; the rule fires across the pause group (`NEXT(p)`), so
  mendean Viktoria→mendeam…, jakin-min→ɟakim….
* **k degemination is cross-word V1-only** (`kdrop_xword` config) — the V1 binary
  drops a word-final `k` before a `k`-initial next word (bakarrik korrika→
  …bakarri korrika→orika); V2/V3 keep both.  Within-word `kk` always collapses.
* **Hyphen-glued compounds stay in one pause group** (`phonemize`) — for V1/V2
  the hyphen is dropped so the two parts sit phonetically adjacent and
  cross-part coarticulation fires (bete-betean→βetEan, idazle-belaunaldi),
  matching the binary (which still emits two tokens).
* **Empty-oracle exclusion** (`validate.py`) — V3 rows where modulo1y2 crashed on
  `«» – —` return empty and are not ground truth; excluded from scoring.

## Divergence ledger — every remaining mismatch class with its root cause

Categories per the mandate: (1) port bug (2) missing config (3) different dict
(4) deterministic upstream artifact reproduced (5) genuinely
linguistic/ambiguous, justified.

1. **`urte` singular-case declensions → OROK** *(category 5, justified
   upstream artifact)*.  searchBin returns the `urte` entry with STR_MRK=1 for
   **every** declension (MATCHLEN!=0 → `found=FALSE`), and the eu_categ STR_MRK
   block (`pos1.cpp` posdic / eu_categ:158, gated only on `encontrado==FALSE`)
   then *adds* POS_EU_STR_MRK unconditionally — so the source as written predicts
   **MRK for all of them**, exactly as it correctly does for euskarak / bakarra /
   mugak / kontuan / goizean / beraren.  The compiled V1/V3 binaries instead
   surface the bare singular cases (`-a -ak -an -ko -tik`) OROK while plurals /
   `-ari` (`-en -etan -otan -ari`) and the exact match `urte` keep MRK.  Verified
   NOT derivable: the faithful searchBin trajectory and the full POS cascade are
   *identical* for urtean(OROK) and urteetan(MRK).  Confined to this one
   high-frequency stem (eva/lantze, formerly in the hack, are now handled
   correctly by the verb/suffix cascade).  Source cite: `eu_hdic.cpp:168-283`
   (searchBin), `pos1.cpp:43-160`+`eu_categ.cpp:158-171` (STR_MRK add).  Emulated
   for `urte` only in `_eu_pos.tag`.
2. **`bat` (enclitic determiner) stress** — *RESOLVED this round by a faithful
   source port (now 0/0 mismatches).*  The discriminator is NOT the host's
   static POS but the **FGRP grouper cascade + the driver's `p`-advance**
   (`eu_gf.cpp::utt_gf` advances `p` by `indice2-1` after each grouper).  When a
   genitive/local-genitive modifier (`-aren`/`-ko`, tagged ATZ_IZE by `atzize`)
   precedes the noun, `izeize` (`gfize.cpp:214-249`) merges the noun and advances
   `p` PAST it, so the next iteration lands on `bat`; since `bat` is DET+ENKLITIKO
   (not NONE/IZE) the `enk` host test fails and `bat` heads its own group →
   stressed (eginkizunaren zati bat, garaiko hilarri bat).  Without the genitive,
   the noun is the `enk` host and `bat` is de-accented (mota bat, ikasgai bat).
   Implemented by: adding `atz_ize` to the POS key set + name_map (it was
   computed by `_eu_pos` but dropped before the FGRP stage), porting the `izeize`
   grouper, and tightening the `enk`/`izedet` host to NONE|IZE only (the C
   `gfize.cpp:100` host test) so an ADJ host (`bortitz bat`) no longer wrongly
   merges its enclitic.  Source cite: `gfize.cpp:86-249`, `eu_gf.cpp:125-186`.
3. **`v` after a non-nasal consonant** *(category 5)* — source `eu_phtr.cpp`
   case 'v' gives approximant `β` (kartveliar→kartβ…, vascongadoak→βask…); the
   binary gives plosive `b`.  Left source-faithful; rare loan edge.  Source cite:
   `eu_phtr.cpp:111-118`.
4. **V3 cross-token coarticulation across bracket/quote** *(category 1, partially
   open)* — a literal `( « » :` token inside a phrase should break the flat
   coarticulation chain (Barrutia (Deustu)→deustu plosive), but the port's
   g2p group concatenates the words and the `(` does not interrupt adjacency, so
   `Deustu`'s `d` wrongly approximates after `Barrutia`'s final vowel.  Affects a
   few V3 lines; needs the punct positions threaded into `g2p_group`.
5. **Foreign-name romanisation / stress** *(category 5, NOT source-derivable —
   verified)* — Aymeric, Bayonnais, Gehry, Hoffmeyer, Olympique,
   Alltagsgeschichte, Qasi, Sádaba, Julian (stress only), Beilarien, Santamaria,
   britainiar, flysch, society: the binary's letter-to-sound and stress for
   non-Basque names.  **Verified NOT in either dict** (`decode_hdic.py` on
   `eu_dicc_v1`/`eu_dicc_v3` returns NOT FOUND for every one of them except
   `julian`/`britainiar`, which are present with no exp and no STR_MRK), so there
   is no `exp` respelling to port — unlike New/baby/Xabier/boom, which ARE in the
   dict with an `exp` and are now closed (see "Closed this round").  `Julian`
   stays open as a *stress-only* divergence: the faithful searchBin lands on a
   STR_MRK partial (`julia*`, matchlen 4) so the port marks it 1st-syllable
   (`xUlian`) while the binary surfaces OROK (`xulIan`) — the same
   searchBin-trajectory artifact documented for `urte` (ledger #1), not
   probe-fittable.  `britainiar` is the inverse: the public `eu_phtr` case 'i'
   i-drop+palatalise rule (`eu_phtr.cpp:224-247`, gated on prev-phone∈`aeou`) DOES
   fire here (predicting `britAɲiar`), but the binary keeps the glide and the
   plain `n` (`britAjniar`) — a binary deviation from its own source.  **There is
   no foreign-name / loanword pronunciation table in the eu source** — confirmed
   by reading
   `eu_pronun.cpp` (it is only `isPronun`, the read-vs-spell pronounceability
   check) and grepping the whole tree (`foreign|extranj|loanwo|mailegu|erdara`
   = no hits; `POS_..._PROPER_NOUN` exists only in the English `hts.cpp`).  The
   binary runs these spellings through the same `eu_phtr` rules and then collapses
   geminates (Bayonnais nn→n, Bilborock kk→k), drops/alters final clusters, and
   restresses them in ways the literal g2p does not produce.  Left source-faithful
   (the eu g2p output); the divergence is a compiled-binary artifact with no
   source rule to port.
6. **`-tz`/`-sch`/foreign final clusters** *(category 5)* — bortitz→βortIʂ,
   flysch→flis, irakats→iɾAkas: irregular per-word final-cluster handling in the
   binary.  The regular `-st`/`-ts` final-t drop before a consonant IS ported
   (`bost`→bOs); the phrase-final `-ts`/`-tz` retroflex realisations are not in
   the public `eu_phtr` case 's'/'z' logic (which only drops the t when the NEXT
   word starts with a consonant — `eu_phtr.cpp:710-724`).
7. **Number-range / abbreviation verbalisation edges** *(category 1, long tail)*
   — a handful of V1/V2 `missing` tokens are number-list (`7`→zazpi) and symbol
   ("-"→gidoia) verbalisations in unusual contexts that the expander does not
   reproduce token-for-token.

V2's profile is the same g2p set as V1 minus the dict-POS stress (the faithful
flat path), so its residuals are the b/β, v, and cluster edges above.

## Closed this round (faithful dict/source ports, with cites)

Three closable residual classes were closed from the dictionary `exp` field and
the eu_phtr text-accent rule — no probe-fitting, no per-word tables.  The fixes
generalise (they fire for every NOR=acr respelling in the dict, not just the
probed words); the words that surfaced in the corpus are New, baby, Xabier, boom.

* **NOR=acr `exp` respelling expansion is case-insensitive** (`_expand_one`).
  `eu_abbacr.cpp::isAbbAcrUni`+`expAbbAcrUni` replace an exact-dict-match word
  whose HDIC EU_NOR field == ACR with `str2wrdLst(exp)` at the normaliser stage
  (`eu_normal.cpp:311-325`).  The dict search hits the case-insensitive blocks
  2/3, so a capitalised proper name (`New`, `Xabier`) matches the lowercase key
  — the port now lowercases the lookup, matching the binary.  Fixes `New`→`niU`
  (exp `niu`), `Xabier`→`ʃaβiEr` (exp `xabiér`).  Cite: `eu_abbacr.cpp:132-420`,
  `eu_normal.cpp:311-325`; dict field: `new`/`xabier` NOR=acr, exp.

* **Acute-accent text stress (USTRESS_TEXT)** (`_accent_vowel_ord` +
  `_group_to_singlechar` override).  A NOR=acr respelling carries its stress as
  an acute accent on the stressed vowel (`béibi`, `xabiér`, `donatélo`).  In g2p,
  `eu_phtr.cpp:274-278` maps the accented vowel char (CS_atilde..CS_utilde) to
  its base phoneme AND calls `SETSTREUS` = `setStress(USTRESS_TEXT)` on that
  cell.  `agrp_stress` has **no `AGRP_EU_TXT` case** (`eu_stre.cpp:161-186`), so
  the only accent on such a word is that one phone-level text stress on the
  accented vowel — the port clears the AGRP stress for the word and stresses the
  accented vowel's phone (counting full vowels + diphthong glides in emit order).
  Gated to the accentual V1/V3 path (the V2 flat build does not run the abbacr
  normaliser, so it reads the raw word — `New`→`nEu`, `baby`→`bAbʝ`).  Fixes
  `baby`→`bEjβi`, `Xabier`→`ʃaβiEr`.  Cite: `eu_phtr.cpp:124-125,274-278`
  (SETSTREUS), `eu_stuti.cpp:184-190` (acento_texto), `eu_stre.cpp:95-105,161-186`
  (fgrp2agrp AGRP_EU_TXT, agrp_stress).

* **TF_MRK transcription takes precedence over the NOR=acr `exp` expansion**
  (`_expand_one` is gated off TF_MRK words).  `boom` carries BOTH a NOR=acr exp
  (`bum`) and a TF_MRK transcription (`b.u.m`).  `eu_phtr.cpp:168-187`
  (`trans_fonet_hitza`→`tf_mrk_ch2ph`) emits the dict transcription **verbatim**
  and advances `p` past the whole word, so the TF phones never pass through the
  `switch(ch)` g2p — the leading `b` stays plosive `[b]` regardless of a
  preceding vowel.  Expanding `boom`→`bum` and re-g2p'ing would approximate the
  `b`→`β` after a vowel (case 'b' `aeiou` rule, `eu_phtr.cpp:302-306`).  Leaving
  it TF gives `bUm` everywhere (`baby boom`→`bEjβi bUm`, `da boom`→`dA bUm`),
  matching V1.  V3's dict (`eu_dicc_20250326`) has `boom` TF_MRK=0, NOR=acr, so
  it expands and approximates (`βUm`) — which is V3's oracle; both fall out of
  reading the per-version dict flags.  The respelling-vs-acronym split is the
  on-disk exp terminator: `\r` = phonetic respelling (V1/V3-only), `\t` = true
  acronym/initialism (`bilborok\t`, `euskadiko autonomi elkartea\t`, read on all
  paths).  Cite: `eu_phtr.cpp:168-187,302-306`; dict: `boom` TF_MRK+NOR=acr.

## Source-ported this round (faithful, with source cites)

* **`bat` enclitic stress via the FGRP cascade** — see ledger #2 (izeize grouper,
  `atz_ize` threaded to the FGRP stage, enk/izedet host = NONE|IZE only).
* **SALBTF exceptions read from the searchBin-SELECTED block** (not OR'd over
  blocks).  `pos1.cpp::posdic` (l.213-233) queries SALBTF_J_0_X / L_l_L / N_J_N
  from the single HDicRef searchBin picked; the selection is case-sensitive
  (blocks 0/1 cased, 2/3 lowercased).  `_eu_pos._posdic` now adds the SALBTF
  flags, and g2p routes j/l/n through `_salbtf_j_x` / `_salbtf_l_l` /
  `_salbtf_n_n` using the faithful tagger with the **original-case** word
  (`_normalize_word_keepcase`).  Fixes: jende/jauregian/jendearentzat → ʝ/ɟ (not
  x) while Juan/Julian/jatorri/erlijio → x; termino → palatalised termIɲoak (one
  of its two block-3 entries has N_N=0, which searchBin selects) while
  diziplina/linea/zinema/kilo/ilustrazio correctly keep non-palatal.
  Cite: `eu_phtr.cpp:423-430` (case j), `eu_stuti.cpp:468-490`
  (trans_fonet_salb_*), `pos1.cpp:213-233` (posdic SALBTF), `eu_hdic.cpp` searchBin.
* **Proclitic devoicing b/d/g → p/t/k after ez/bait** made source-exact
  (`eu_phtr.cpp` case 'b' l.287-300 = "ez" only; cases 'd'/'g' l.331-405 =
  "ez"||"bait"; NOT "ba").  Now gated on (a) the accentual path (the flat V2 path
  does not run the POS test → keeps voiced: ez du→dU), and (b) the b/d/g-word
  being `es_verbo_trn||es_verbo_lgn` via the faithful tagger (`_is_verbo_trn_lgn`,
  recognises inflected auxiliaries direla/duen → ADI_LGN).  Fixes ez du/dago/
  da/direla/duen (V2 keeps voiced, V1/V3 devoice) and ez baitzaio→pAjPaʝo.
  Cite: `eu_phtr.cpp:287-405`, `eu_stuti.cpp:144-158` (es_verbo_*).
* **Quotation marks are not pause breaks on the V1/V2 transcribe path** — `«»"`
  (and curly quotes) are dropped so coarticulation continues across them
  (dira «diskurtso → ...ðiɾA ðiskUrVo), like the hyphen-glued compound rule.
* **Circumflex vowels â/ê/î/ô/û → base vowel** in `_ACCENT_REPL` (symbolexp.c
  folds the accented forms; "nô" → nO instead of dropping the vowel).

## Known TODOs / open defects (remaining mismatches)

After this round (New/baby/Xabier/boom closed from the dict `exp`), **all
remaining mismatches are OOV-foreign / non-derivable artifacts** (ledger #5/#6)
or the small long-tail below; none is a probe-fitted rule.  100% is NOT reached
because the binary diverges from the public source on these:

* **Foreign geminate collapse / final-cluster realisation** (category 5, NOT
  source-derivable): Bayonnais nn→n, Bilborock kk→k, irakats -ts→s, bortitz
  -tz→ʂ, flysch -sch→s, Alltagsgeschichte ll→l (no palatal).  The public
  `eu_phtr` keeps the geminate / digraph; the binary collapses it.  No source
  rule exists to port — documented artifact.  *Could* be force-matched with a
  per-word/-cluster table, but that would be exactly the probe-fitting the
  mandate forbids, so left source-faithful.
* **OOV foreign-name stress / romanisation** (category 5): the residual
  foreign-name tail is now words **not in either dict** (no `exp` to port) —
  Aymeric, Bayonnais, Gehry, Hoffmeyer, Olympique, Alltagsgeschichte, Qasi,
  Sádaba, Beilarien, Santamaria, britainiar, flysch, society — plus `Julian`
  (in-dict, stress-only: searchBin lands on a STR_MRK partial → 1st-syllable,
  the binary surfaces OROK, the `urte`-class searchBin artifact, not fittable).
  New/baby/Xabier/boom are **no longer here** — they were in the dict with an
  `exp` respelling and are closed.
* **`(C's)` / `XX.aren` abbreviation+declension edges** (category 1, long tail):
  the glued apostrophe-S and the roman-numeral + glued declension expansions are
  not reproduced token-for-token by the expander.
* **V3 cross-token coarticulation across a literal bracket/quote** (category 1,
  ledger #4): a few V3 lines where an inline `(`/`«` should break the flat
  coarticulation chain but the g2p group still concatenates the words.
* **`urte` singular-case OROK** (category 5, ledger #1): the one documented,
  probe-validated + source-trajectory-proven non-derivable artifact, emulated for
  `urte` only.

### Verification of "no undocumented/probe-fitted rules remain"

The two former probe tables are now source-grounded (above).  Every behavioural
rule added this round cites a specific source file/line.  The only emulated
artifact in code is the `urte` STR_MRK split (ledger #1), proven non-derivable.
All other gaps are the foreign-name / final-cluster binary artifacts (#5/#6) and
the abbreviation long tail (#7), which are documented here rather than hacked —
fixing them to 100% would require per-word fitting, which the mandate forbids.
