# Architecture

`ahotts-g2p` reimplements the AhoTTS Basque linguistic front-end as a
straight-line pipeline. No C code is involved; the only data input is the
binary dictionary, read with `struct`.

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

- integers (`1870`) -> Basque number words (vigesimal: `hogei`, `berrogei`, ...);
- ordinals (a number followed by `.`) -> `...garren`;
- number + declension suffix (`1870eko`, `22an`) -> number words + suffix;
- roman numerals (`XXI`) -> ordinal Basque number words;
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
  phrase-final;
- closed clitic/auxiliary words stay unstressed;
- first-syllable words: the hardcoded `salbuespena` list **plus** any word
  carrying the dictionary `STR_MRK` flag (exact-match lookup);
- bisyllabic `-ko`/`-go`/`-ten`/`-tzen` forms: first syllable;
- monosyllables: stressed (unless `ez`/`ba`/`bait` non-final);
- otherwise: second syllable.

### SAMPA -> IPA -> single-char

Internal phone codes map to SAMPA (`PH_SAMPA`), SAMPA to IPA (`SAMPA_TO_IPA`),
then multi-char IPA sequences and stressed vowels fold to single characters
(`MULTICHAR_TO_SINGLECHAR`) so the result is one character per phoneme, the
form a StyleTTS2-style model trains on.

## The HDIC dictionary decode

`eu_dicc.dic` is AhoTTS's binary lexicon in the **HDIC** format. Both
`decode_hdic.py` (a standalone reader/inspector) and the loader inside
`ahotts_eu_hdic.py` parse it with `struct` -- no C build.

Format:

```
signature  "Aholab aHoTTS HDIC Database\x1A" + NUL   (28 B)
type       CHAR[2] ("eu")
version    UINT32 (== 0)
4 block descriptors (base, n, slen, [exlen])
per entry: UINT16 len | str[slen] | UINT32 ref | [UINT16 explen | exp[exlen]]
```

There are 4 sorted-array blocks (blocks 0/1 case-sensitive, 2/3
case-insensitive; block 3 is the ~17k-word main lexicon). Each entry's 32-bit
`HDicRef` encodes part-of-speech groups and the flags the pipeline consults:

- `STR_MRK` (bit 15) -- first-syllable lexical stress;
- `SALBTF_N_J_N` (bit 21) -- suppress `n` -> ɲ palatalisation;
- plus `SALBTF_I_J`, `J_X`, `L_l`, `Z_T`, `TF_MRK`.

Driving stress and palatalisation from the **decoded dictionary flags** (rather
than a small curated list) is what lets the port generalise far beyond the
oracle's 25 lines: hundreds of words carry these flags. A handful of
phonetic-rule / romanisation quirks the dictionary does not encode through its
bits remain as explicit per-word overrides.
