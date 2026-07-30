# Architecture

`ahotts-g2p` reimplements the AhoTTS linguistic front-end as a straight-line
pipeline. No C code is involved. The only data input is the binary dictionary,
read with `struct`.

## Modules

| Module | Responsibility |
|---|---|
| `__init__` | public API: `phonemize(text, lang, version, dialect)`, `SAMPA_TO_IPA` |
| `versions` | the `Version`/`Lang` enums and the per-version/dialect config table |
| `phones` | phone code tables (`PHEU`, `PH_SAMPA`), `SAMPA_TO_IPA`, single-char folding (`MULTI`) |
| `g2p` | the Basque (eu) engine: normalisation, g2p, syllabification, stress, rendering |
| `es` | the Spanish (es) engine |
| `dict_hdic` | the HDIC binary-dictionary reader |
| `_faithful_search` | the HDIC binary search (`searchBin` / `tokbsearch`) |
| `_eu_pos` | the Basque part-of-speech cascade (`eu_categ` / `pos1`) |

## Pipeline

```
text
  -> normalize        lowercase, fold accents, expand numbers/ordinals/romans
  -> g2p              grapheme -> internal phone codes (context-sensitive)
  -> syllabify        place syllable boundaries (onset clusters, diphthongs)
  -> stress           assign lexical stress per word
  -> SAMPA            internal phone code -> SAMPA name
  -> IPA              SAMPA -> IPA
  -> single-char      fold multi-char IPA + stressed vowels to single chars
  -> training string  space-joined tokens, punctuation preserved
```

### normalize

`phonemize` tokenizes text, collapses runs of `.` , and expands:

- integers (`1870`) -> Basque number words (vigesimal: `hogei`, `berrogei`, ...).
- ordinals (a number followed by `.`) -> `...garren`.
- number + declension suffix (`1870eko`, `22an`) -> number words + suffix.
- roman numerals (`XXI`) -> ordinal Basque number words.
- dictionary acronyms/abbreviations -> their expansion (pronunciation) field.

Punctuation in `.,!?;:` is kept as standalone tokens and acts as a pause
boundary that splits the sentence into pause groups.

### g2p (`g2p_group`)

Mirrors the AhoTTS C++ grapheme walk. Each character of a **pause group** is
processed in context (the previous/next character can cross word boundaries
within the group), so approximant rules (b/d/g -> β/ð/ɣ), `n` assimilation
(`n` -> `m` before `b/p/m`), digraphs (`tx`, `tz`, `ts`, `dd`, `ll`, `rr`...),
palatalisation (`i` + `n`/`l`), and the `ez`/`ba`/`bait` proclitic sandhi are
all reproduced. Output is a flat list of internal single-char phone codes plus
a map from each phone back to its source word.

### syllabify (`syllabify`)

Per word (syllabification does not cross word boundaries). Walks the vowels and
places boundaries using the AhoTTS cases: `#V`, `CV`, `VCV` -> `V-CV`, `CCV`
(valid onset cluster -> `-CCV`, else `C-CV`), and `VV` (diphthong stays in one
syllable, otherwise `V-V`). Valid onset clusters are consonant + `l` / `r`.

### stress (`assign_stress`)

Per word, following the AhoTTS stress rules:

- `eta`/`ta`/`edo`/`ala`/`baina`/`baino` (`es_sin_acento`): stressed only when
  phrase-final.
- closed clitic/auxiliary words stay unstressed.
- first-syllable words: the hardcoded `salbuespena` list **plus** any word
  carrying the dictionary `STR_MRK` flag (exact-match lookup).
- bisyllabic `-ko`/`-go`/`-ten`/`-tzen` forms: first syllable.
- monosyllables: stressed (unless `ez`/`ba`/`bait` non-final).
- otherwise: second syllable.

### SAMPA -> IPA -> single-char

Internal phone codes map to SAMPA (`PH_SAMPA`), SAMPA to IPA (`SAMPA_TO_IPA`),
then multi-char IPA sequences and stressed vowels fold to single characters
(`MULTI`) so the result is one character per phoneme -- the form a
StyleTTS2-style model trains on. All three tables live in `phones`.

## The HDIC dictionary decode

The `.dic` files are AhoTTS's binary lexicons in the **HDIC** format. The
`dict_hdic` module parses them with `struct` -- no C build.

Format:

```
signature  "Aholab aHoTTS HDIC Database\x1A" + NUL   (28 B)
type       CHAR[2] ("eu")
version    UINT32 (== 0)
4 block descriptors (base, n, slen, [exlen])
per entry: UINT16 len | str[slen] | UINT32 ref | [UINT16 explen | exp[exlen]]
```

There are 4 sorted-array blocks (blocks 0/1 case-sensitive, 2/3
case-insensitive). Block 3 is the ~17k-word main lexicon. Each entry's 32-bit
`HDicRef` encodes part-of-speech groups and the flags the pipeline consults:

- `STR_MRK` (bit 15) -- first-syllable lexical stress.
- `SALBTF_N_J_N` (bit 21) -- suppress `n` -> ɲ palatalisation.
- plus `SALBTF_I_J`, `J_X`, `L_l`, `Z_T`, `TF_MRK`.

Driving stress and palatalisation from the **decoded dictionary flags** (rather
than a small curated list) is what lets the port generalise across the full
lexicon: hundreds of words carry these flags. A handful of phonetic-rule /
romanisation quirks the dictionary does not encode through its bits remain as
explicit per-word handling.

---
[← Dialects](dialects.md) · [Home](README.md) · [Methodology →](methodology.md)
