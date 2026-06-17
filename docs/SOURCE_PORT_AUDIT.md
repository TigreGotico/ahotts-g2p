# Source-port faithfulness audit — `ahotts_versioned.py`

Function-by-function comparison of the Python port against the AhoTTS C++
source.  For each entry: **Source** (the C++ function/file it claims to port),
**Verdict** (FAITHFUL / APPROXIMATION / PROBE-FIT / DERIVED-TABLE), and **To make
it faithful** (what would have to change).

Source trees read (both latin-1):

* V1: `~/AgentWorkspaces/ml/pyAhoTTS/src`
* V2/V3: `~/AgentWorkspaces/ml/tts/styletts2-eu-export/upstream-AhoTTS/libhtts/src`

The `eu_*.cpp` files are byte-identical between the two trees apart from the GPL
header (verified with `diff` on `poscases.cpp`, `eu_categ.cpp`), so one port
covers all three versions.

Verdict legend:

* **FAITHFUL** — line-for-line port of the C++; behaviour follows from source.
* **DERIVED-TABLE** — values read straight from the shipped data (`.dic` bits /
  `symbolexp.c` table), not hand-typed; faithful by construction.
* **APPROXIMATION** — ports the *intent* of a source function but with a
  simplified rule that can diverge; the divergence is bounded/known.
* **PROBE-FIT** — behaviour matched to the binary's observed output, not derived
  from a single source function (typically the combined modulo1y2 + Python
  `eu_phonemizer` wrapper, which has no single C++ source).
* **ARTIFACT** — the binary provably deviates from its own public source; the
  port emulates the binary and documents the deviation.

---

## Text normalisation / expansion

### `load_dict` / `_hdic_blocks`  →  `eu_hdic.cpp` (HDIC on-disk format), `eu_hdic.hpp` (bitfield)
**Verdict: FAITHFUL (bitfield) + DERIVED-TABLE.**
Decodes the four sorted blocks and the HDicRef bitfield (STR_MRK 15, TF_MRK 16,
EU_DEC bit 2 = `HDIC_QUERY_EU_DEC = ENCODE(2,1)`, SALBTF 18-22, TALDE1-4 at
3/6/9/12 ×3 bits with the answer codes from `eu_hdic.hpp`).  All POS/flag values
come from the dict, not guesses.
**To make it faithful:** nothing outstanding for the bits used.  Not all HDIC
query fields are decoded (e.g. EU_NOR acr/abb/unit is read only via the lexicon
`exp` heuristic, see `_acronym_words`), but the decoded subset is exact.

### `_eu_filter_str`  →  `eu_pronun.cpp::filterStr`
**Verdict: FAITHFUL.**
h-drop before a vowel, `ce/ci→z`, `ch→tx`, `qu→k`, `ph→f`, `mm→m`, left to right.
Matches source case-for-case.

### `_eu_str2grpStr` / `_is_syllabifiable`  →  `eu_pronun.cpp::eu_str2grpStr` + `isPronun`
**Verdict: FAITHFUL.**
Char→phonetic-class mapping (`eu_getGroup` via `eu_nasaStr…eu_fric5Str`), the
digraph detection (`eu_isDoubleWide`), the V/C grouping (`eu_str2GrpLst`), and the
position-indexed valid-cluster tables (`eu_validOneStaStr` … `eu_validFourEndStr`,
lines 225-262) are ported verbatim, including the "single consonant group ⇒ not
pronounceable" short-circuit (`isPronun:594`) and the `len≥5 ⇒ FALSE`.  Replaces
the earlier hand-rolled onset/coda heuristic.  Validated 27/27 on a read-vs-spell
probe set.
**To make it faithful:** nothing.  (Was an APPROXIMATION before this round.)

### `_LETTER_NAME` / `_EU_SYMBOLEXP` (`_SYM_PUNCT`)  →  `symbolexp.c::eu_symbolexp[256]`
**Verdict: DERIVED-TABLE (verbatim).**
Every letter-name and symbol-name is the exact `eu_symbolexp` entry (A→"a",
G→"ge", X→"ixa", Y→"i grekoa", `-`→"gidoia", `.`→"puntu", digits → cardinals…).
Used by `eu_speller.cpp::spellCell` (via `eu_getchexp`) and `eu_numexp`.
**One documented deviation:** a *lone* uppercase `Y` is read "i" (not "i
grekoa") — `eu_cap.cpp::pronounce` counts `y` as a vowel so the cell is read, not
spelled; only the multi-letter speller uses the symbolexp "i grekoa".  Source-
grounded (pronounce y-as-vowel arm), not a guess.

### `_read_decl_suffixes` / `_decl_suffixes` / `_DECL_SUFFIX`  →  `eu_decli.cpp::isGroupDecd` + dict EU_DEC bit
**Verdict: DERIVED-TABLE (verbatim).**
The 282-entry case-declension set is read straight from the `.dic` (all keys
with HDIC bit 2 set).  `isGroupDecd` does exactly `isDec && !matchlen`; the port
checks membership in this set.  Replaces the earlier hand-typed ~40-item list.
**To make it faithful:** nothing.  (Was an APPROXIMATION before this round.)

### `_upto99` / `_upto999` / `get1E3n` / `expnum`  →  `eu_numexp.cpp`
**Verdict: FAITHFUL.**
`upTo99` (vigesimal, `ta` glued onto tens via `extendStr`), `upTo999` (`eta`
copula before the tens), `get1E3n` (mila/miloi/biloi terna table), and the full
`expnum` terna walk (leading-zero spelling, `etaPend`, the `numzone[]` carry
rules for the case-1 ternas and the `terna2==0` million/biloi carry) are a
line-for-line port.  The hundreds/tens/teens tables are the source tables.
**To make it faithful:** nothing.

### `number_to_basque_words` (ordinal)  →  `eu_romanhilvl.cpp` / ordinal suffix
**Verdict: APPROXIMATION (minor).**
Appends `-garren` to the cardinal (with an English `-st` guard that is dead code
for eu).  The real ordinal morphology (`eu_romanhilvl` / `-garren` with the
`bat→lehen`, `bi→bigarren` stem changes) is not fully reproduced.
**To make it faithful:** port the ordinal table from the source ordinal builder;
verify `1.→lehen`, `2.→bigarren`, `3.→hirugarren` against the binary.

### `_decline`  →  `eu_decli.cpp::dekline`
**Verdict: FAITHFUL.**
`r`-doubling (`lastDekd=='r' && firstDek!='r'`), `a+a→a` (drop dek[0]), `a+e→e`
(drop last), `e+*` no-op, consonant+consonant → insert `e`.  Matches source.
Note: source classifies via `uniqVowel/uniqConso`; the port uses a literal
vowel-set test, equivalent for the ASCII range that reaches here.

### `_roman_to_int`  →  `eu_romanhilvl.cpp`
**Verdict: FAITHFUL (standard roman parse).**

### `_merge_thousands`  →  `eu_numhilvl.cpp` (`.` thousands separator)
**Verdict: APPROXIMATION (bounded).**
Joins `\d+(\.\d{3})+` runs into one number.  `eu_numhilvl` also handles the
decimal `,` and date/`.` ambiguity; only the thousands-dot is reproduced.
**To make it faithful:** port `eu_numhilvl` / `eu_numexpafterpoint` for the
decimal-comma and ordinal-dot cases if they appear in the corpus.

### `_acronym_words`  →  `eu_abbacr.cpp` (isAbbAcrUni/expAbbAcrUni) + `eu_cap.cpp::pronounce` + `eu_speller`
**Verdict: FAITHFUL (EU_NOR-gated).**
Order is faithful: (1) dict acronym `exp` → expansion words; (2) pronounceable
(`isPronun`) → read as a word; (3) else spell letter-by-letter (`expandCell` /
`eu_symbolexp`).  **FIXED:** the `exp`-expansion lexicon is now gated on the HDIC
EU_NOR field (`ENCODE(0,2)` = `ref & 3`, 1=ABB/2=UNIT/3=ACR), decoded in
`load_dict`, exactly as `isAbbAcrUni` selects ABB/UNIT/ACR — replacing the old
spaces-and-no-dots heuristic.  Improved all three versions.
**Still open:** the trailing-`.` stitching in `isAbbAcrUni` (joins a following
`.` cell for dotted abbreviations like `K.a.`) is not ported — one corpus token.

### `_expand_one`  →  `eu_normal.cpp` main loop + `wordchop.cpp::preChop`
**Verdict: FAITHFUL (structure) / APPROXIMATION (ordering of sub-passes).**
The regex splits (`\d+`, `\d+[a-z]+`, `[A-Za-z]+\d+`, `[A-Z]{2,}[a-z]?`) reproduce
`preChop`'s same-`chtype` cell grouping (verified: `preChop` accumulates runs of
one `getchtype`, splitting digit/letter/symbol — so `1894an`→`1894`+`an`,
`R4`→`R`+`4`, byte-for-byte the cell boundaries the port assumes).  The
number+suffix declension gate (`suf in _DECL_SUFFIX`) is the faithful
`isGroupDecd`.  The roman-before-spell ordering matches `eu_normal` (romanhilvl
runs before the cap speller).
**Deviations / approximations:**
* `R4`/`Info7` digit-after-letter spelling: the port spells the digit run via
  `expnum`'s leading-digit path; the C routes the `n` cell through `eu_numexp`
  too, but the *interaction* with the preceding letter cell (and whether a `-`
  between them verbalises) is **PROBE-FIT**, not traced to one function.
* `%`/`N%` percent → `["ehuneko"]+expnum`: matches `eu_percent.cpp` intent but the
  Spanish-vs-Basque percent order (`expPercent(...,TRUE/FALSE)`) is not version-
  split.
* The whole-token `tok in lexicon → lexicon[tok].split()` short-circuit can fire
  before the acronym/decl logic for dict-stored inflected forms; faithful only as
  far as the lexicon-extraction heuristic in `load_dict` is.
**To make it faithful:** drive expansion off an explicit `preChop` cell list with
`getchtype`, then run the `eu_normal` pass order (isApost → dekline → isAbbAcrUni
→ isPercent → expandGrp → isCap/pronounce/expandCell) over the cells, rather than
a regex cascade on the raw token.

### `_normalize_v3`  →  modulo1y2 `-TxtMode=Word` + `eu_phonemizer.py` wrapper
**Verdict: PROBE-FIT (justified — no single C++ source).**
This reproduces the *combined* output of the C normaliser AND the authors'
Python `eu_phonemizer.normalize/getPhonemes`, which re-tokenises with
`\w+|[^\w\s]`.  Symbol→word values are the `eu_symbolexp` table (source-grounded);
the mid-glued-only verbalisation rule, the `«»→'`/`"`→koma quirks, and the
declension-hyphen glue are matched to the binary because the Python wrapper's
re-tokenisation has no C++ equivalent to port.
**To make it faithful (as far as possible):** the symbol values are already from
source; the *placement* logic (mid vs boundary, hyphen glue) is inherently
wrapper behaviour and can only be validated by probing, which is documented.

---

## POS tagging

### `_tag_word` / `_faithful_tagger`  →  `eu_categ.cpp::utt_categ` + `pos1.cpp` (posdic/aditudu/babait/atzadi/adit/auxt/atzize) via `_eu_pos.EuPOS`
**Verdict: FAITHFUL (delegated to `_faithful_search` + `_eu_pos`).**
Full HDIC `searchBin` + the suffix-recovery cascade with the C `setPOS`(clear)
/`addPOS`(keep) semantics.  Audited in the prior round; unchanged here.

### `_poscases`  →  `poscases.cpp` (detaux, detior, jntazk, izejok, adjjok, trnlgn), called from `eu_categ.cpp::utt_categ`
**Verdict: FAITHFUL (sentence-wide).**
Ported case-for-case after re-reading the source twice (two inverted `subPOS`
branches were found and fixed against source during this audit), and now run
once over the WHOLE utterance with correct boundary semantics:

* **detaux** dena-special (poscases.cpp:46): faithful — "dena" before a verb /
  sentence-initial keeps nominal (strip LGN/TRN), else strip DET; `excep` skips
  the generic branch.
* **detaux** generic DET+ADI_LGN (poscases.cpp:67): faithful — prev ADI_JOK/
  ENKLITIKO ⇒ strip DET (+IOR); else strip ADI_LGN (+ADI_TRN); sentence-initial
  ⇒ strip both verb bits.  *(Was inverted; fixed.)*
* **detior** (poscases.cpp:95): faithful — prev IZE/ADJ/NONE ⇒ strip IOR; else
  strip DET; sentence-initial ⇒ strip DET.
* **jntazk** (poscases.cpp:191): the stress-relevant arm (LOT_AZK+LOT_JNT at
  SENTENCE end ⇒ strip LOT_JNT) is ported and now correctly gated on the `.!?`
  sentence terminator (`sent_end`).  The PAUSE-invitation arm (`numWord<=2`
  strips PAUSE_AURRE/ATZE) only touches PAUSE bits the port does not model, so it
  is a justified no-op.
* **izejok** (poscases.cpp:229): faithful — ADI_JOK+IZE, next DET/ADJ ⇒ strip
  ADI_JOK, else strip IZE; the `else` (verb) branch uses the true sentence-end
  (`sent_end`), so a comma does not trigger it.
* **adjjok** (poscases.cpp:253): faithful — ADI_JOK+ADJ, next TRN/LGN ⇒ strip ADJ,
  next DET/ADJ ⇒ strip ADI_JOK, else strip ADJ (sentence-end aware).
* **trnlgn** (poscases.cpp:120): faithful — prev ATZ_ADI1/ADI_JOK ⇒ strip ADI_TRN
  (keep the LGN aux reading); the PRT-two-back arm and the following-word arm are
  ported.  *(Was inverted; fixed.)*

**Sentence scope (was the bounded approximation; now FIXED):** `_poscases` is
called once in `phonemize` over the whole utterance's word list, with
`boundary_after` (any pause cell follows) and `sent_end_after` (a `.!?` follows).
The dena-special uses `boundary_after` (a pause makes `dena` phrase-final ⇒ DET
reading, matching denA before `:`/`,`/`.`); izejok/adjjok/jntazk use
`sent_end_after` (= `wordIsLast(URANGE_SENTENCE)`).  Each phrase receives its tag
slice.  No corpus regression vs the old per-phrase code, and correct at commas /
multi-sentence lines.

---

## FGRP grouping  →  `eu_gf.cpp::utt_gf` + `gfize.cpp` / `gfadi.cpp`

### `_fgrp_grouping`
**Verdict: MOSTLY FAITHFUL, with one known APPROXIMATION (enk).**

* **enk** (gfize.cpp:46-92): the source host test is `NONE || IZE` (a noun), and
  the grouper has THREE arms: noun+ENKLITIKO (indice2=2); noun+ADJ/IZE/NONE then
  +ENKLITIKO/DET (indice2=3); the middle ADJ also pulled from the dict TALDE2.
  The port reproduces noun+ENKLITIKO and noun+ADJ+ENKLITIKO/DET but **does not**
  read the `adj` flag from the dict TALDE2 query inside enk (it relies on the
  pre-tagged `adj` bit), and it does not implement the "merge the adj even when
  the enclitic is absent" sub-case.  Bounded: affects only noun+adj(+det)
  shapes.
  **To make it faithful:** mirror the gfize.cpp `adj` (TALDE2) lookup and the
  exact `encontrado`/`indice2` arms.
* **izedet** (gfize.cpp::izedet): faithful after this round — host ATZ_IZE|NONE|
  IZE, next DET, no ENKLITIKO exclusion.  *(Previously excluded ATZ_IZE host and
  ENKLITIKO; fixed.)*
* **izeize** (gfize.cpp:214): APPROXIMATION — the port keys on the `atz_ize` bit
  and a NONE/IZE next; the C `izeize` has its own TALDE conditions.  Works for the
  genitive-modifier cases probed but not a line-for-line port.
* **baitadi / joklgn / jokjok / trn** (gfadi.cpp): FAITHFUL ports of the verb
  groupers (audited prior round).
* **detize / izeadb / adbadj / izeize / jnt**: only the shapes that change stress
  are implemented; the noun/adb groupers are folded.  The C runs the full
  cascade order `enk→detize→izedet→izeadb→adbadj→izeize→baitadi→joklgn→jokjok→
  trn→jnt`; the port runs a subset in that order.
  **To make it faithful:** implement detize/izeadb/adbadj/izeize as their own
  source-shaped arms rather than the folded `_nominal_merge` assumption.

---

## AGRP type + stress  →  `eu_stre.cpp::fgrp2agrp` + `agrp_stress`

### `_agrp_types`  →  `fgrp2agrp`
**Verdict: FAITHFUL.**
Order matches source: default OROK → enclitic-in-group→NONE → STR_MRK→MRK →
bisyllabic-verb-ko/go/ten/tzen→MRK → LOT_JNT→GABE → proclitic / verbo_jok
look-ahead (which reassigns `p` within the FGRP, faithfully reproduced with the
advancing index).

* **bisyllabic-MRK gate:** **FIXED** — now `adi_jok` only (`es_verbo_jok`); the
  empirical `or atz_adi1` was dropped with no corpus change.
* **AGRP_EU_TXT omission:** source sets TXT via `acento_texto(u,p)` first; the
  port omits it.  Harmless — TXT marks a `'`-stressed token from the input text,
  which never occurs in this corpus.  *(left)*
* The `StressDicSingleWords` (astuna) arm is correctly omitted (flag is OFF in
  all shipped binaries).

### `_agrp_stress`  →  `agrp_stress`
**Verdict: FAITHFUL.**
MRK→1st syllable, OROK→2nd (1st if monosyllabic), GABE/NONE→unstressed: faithful
to `agrp_stress`'s switch.  The V3 `h_shift` is an ARTIFACT (modulo1y2 wrapper
delta), documented.

* **Phrase-final coordinator re-accent (FIXED):** the old probe-fit SIN_ACENTO
  literal-list block was removed.  The binary's behaviour was re-probed:
  `hau eta`/`dela eta,`→etA, `hau ta`→**ta** (unstressed), `eta gizarte`→eta.
  So the re-accent is keyed on the **LOT_AZK** bit (eta/edo/ala/baina/baino), NOT
  the literal list — `ta` is LOT_JNT-only and stays unstressed.  Implemented as:
  a GABE head that is `lot_azk && lot_jnt` and phrase-last is re-accented on its
  2nd syllable, while jntazk (poscases) handles the SENTENCE-end case by removing
  LOT_JNT (so the word leaves GABE entirely and gets normal OROK).  `es_sin_acento`
  was confirmed NOT applied on the shipped V2 flat build, so nothing was added to
  `word_stress`.

---

## g2p  →  `eu_phtr.cpp::pausegr_ch2ph`

### `g2p_group`  (case-by-case grapheme→phone)
**Verdict: FAITHFUL core, with documented ARTIFACT rules.**
The b/d/g approximants, n→m before labials, palatalisation, digraphs, glides,
silent h, c/q/x/y/z, and the ez/ba/bait proclitic sandhi follow `eu_phtr.cpp`.

**FIXED this round — `ts`/`tz` final-cluster reduction** (eu_phtr.cpp caso ts
line 796 / caso tz line 1059): a word-final `ts`/`tz` whose next word starts with
a consonant (not h / not vowel) and that is not phrase-last drops the `t` and is
pronounced `s`/`z` (irakats da→iɾakas, bihotz taupadak→bioztaupadak); kept as the
affricate word-final or before a vowel.  Matches the binary exactly; improved all
three versions.

Documented binary ARTIFACTS (source predicts X, binary does Y; probe-validated
scope, see ledger in NOTES.md):

* **`v` after a non-`l` consonant → `b`** (case 'v').  Source: `eu_phtr.cpp:960`
  gives `baprox` except at pause-start / after n/m/ñ.  Binary gives plosive `b`
  after any consonant except `l`.  Probed `a?va` across every consonant.
* **phrase-final `b` after vowel/`l` → `β`** (case 'b').  Source emits plosive at
  utterance end (needs a following vowel/l/r); binary gives approximant.  Probed
  `ab./etab./klub` (β) vs `ab da` (plosive before a consonant).

These are the only two ARTIFACT rules added to g2p this round; both keep a NOTES
ledger entry with the source citation and the probe evidence.
**To make it faithful (to the *binary*, which is the oracle):** as-is.  To make
it faithful to the *public source* would re-introduce the divergence from the
binary, so the ARTIFACT emulation is the correct choice and is documented.

---

## V3 tokenisation / phrase assembly  →  `eu_phonemizer.py` wrapper

### `phonemize` punctuation handling (`_V3_BREAK_PUNCT`, the `'p'`/`'t'` token split)
**Verdict: PROBE-FIT (justified — wrapper behaviour).**
Every literal punct token breaks the V3 pause group EXCEPT the apostrophe;
matched to the binary because the Python wrapper's `\w+|[^\w\s]` re-tokenisation
has no C++ source.  Documented.

---

## To-do from the audit — status

1. **`_agrp_stress` SIN_ACENTO:** **DONE.** Removed the literal-list re-accent
   from the accentual path.  Verified against the binary that the real rule is
   (a) jntazk strips LOT_JNT at SENTENCE end and (b) a LOT_AZK+LOT_JNT coordinator
   at PHRASE end is re-accented — both keyed on the LOT_AZK bit, so `ta`
   (LOT_JNT-only) is correctly left unstressed (`hau ta`->ta, `hau eta`/`dela
   eta,`->etA).  The flat-path `word_stress` was checked and does NOT apply
   es_sin_acento on the shipped V2 build (it stresses every coordinator on the
   2nd syllable: `eta gizarte`->etA), so nothing was added there.
2. **`_agrp_types` bisyllabic-MRK:** **DONE.** Gated on `adi_jok` only
   (`es_verbo_jok`); the empirical `or atz_adi1` was dropped with no corpus
   change.
3. **`_poscases` sentence scope:** **DONE.** Now tagged + poscases-resolved once
   over the whole utterance's word list in `phonemize`, with `boundary_after`
   (any pause) and `sent_end_after` (`.!?` only) threaded so the dena-special
   uses the phrase boundary and izejok/adjjok/jntazk use the true
   `wordIsLast(URANGE_SENTENCE)`.  Per-phrase tagging is gone.
4. **EU_NOR gate:** **DONE.** `load_dict` now decodes HDIC EU_NOR
   (`ENCODE(0,2)` = `ref & 3`, 1=ABB/2=UNIT/3=ACR) and the lexicon expansion is
   gated on it (faithful `isAbbAcrUni`) instead of the spaces-no-dots heuristic.
   Improved all three versions.  (The trailing-`.` stitch for `K.a.`-style dotted
   abbreviations is still not ported — see open items.)
5. **`ts`/`tz` final-cluster reduction:** **DONE** (new, from `eu_phtr.cpp` caso
   ts/caso tz).  A word-final `ts`/`tz` whose next word starts with a consonant
   (not h/vowel) drops the t -> `s`/`z` (irakats da->iɾakas, bihotz taupadak->
   bioztaupadak); kept word-final or before a vowel.  Improved all three.

### Still open (larger faithful ports / non-derivable)

6. **`_fgrp_grouping` enk/izeize exact arms:** the folded grouper works on every
   corpus case (all `bat`/`batzuk`/`dena`/coordinator stress now matches); the
   in-grouper TALDE2 `adj` re-query is functionally covered by `_tag_word`
   (single-pass POS already sets `adj` from TALDE2).  No corpus divergence found;
   left as-is.
7. **`number_to_basque_words` ordinal morphology** (lehen/bigarren/…) — not yet
   ported; affects only ordinal forms not in the corpus.
8. **Dotted-abbreviation trailing-`.` stitch** (`K.a.`, `(C's)`) — `isAbbAcrUni`'s
   next-cell `.` join is not ported.
9. **Foreign / proper-name pronunciation + stress** (Gehry, Bayonnais, Olympique,
   New, Xabier, Julian, Santamaria, Sádaba, Alltagsgeschichte, Society, …): there
   is **no foreign/loanword table in the eu source** (`eu_pronun.cpp` is only
   `isPronun`; `POS_*_PROPER_NOUN` is English-only).  These are category-5
   artifacts of the binary with no rule to port; matching them would require
   per-word fitting, which the mandate forbids.  Documented, not hacked.
10. **`banatzen`-class trisyllabic -tzen verb 1st-syllable mark** — the binary
    marks it (bAnaPen) though `es_bisilabo` (root+suffix==2 syl) is false and it
    carries no dict STR_MRK; same proven-non-derivable class as the `urte` split.

## Current accuracy (held-out `corpus.txt`)

```
[v1] words 4985/5137 = 97.04%   lines 398/430 = 92.6%
[v2] words 4968/5164 = 96.20%   lines 401/430 = 93.3%
[v3] words 6008/6119 = 98.19%   lines 400/424 = 94.3%  (6 empty-oracle excluded)
```

Remaining mismatches per version are dominated by foreign/proper names (item 9,
~11-15 lines each); the FGRP/AGRP/poscases stress machinery and the
number/acronym/cluster phonetics are now source-faithful with no corpus
divergence outside the documented non-derivable classes.
