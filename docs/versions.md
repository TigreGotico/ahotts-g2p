# AhoTTS engine versions

AhoTTS is not a single phonemizer -- it has a real engine lineage, and
different public Basque voices were phonemized by different generations. The
output differs (most visibly in stress placement and diphthong handling), so
`ahotts-g2p` is **version-aware**: `phonemize(..., version=...)` selects which
engine to reproduce. The default is `v3`.

## The version table

| Version | Upstream source | Consuming model | Basque dict | Distinctive behaviour |
|---|---|---|---|---|
| **V1** | [aholab/AhoTTS](https://github.com/aholab/AhoTTS), original engine; complete public C++ source | **HiTZ VITS** voices | original `eu_dicc` | dictionary `STR_MRK` stress through the accentual-group machinery; vowel offglides (`au` -> `aw`, `ai` -> `aj`) |
| **V2** | [aholab/AhoTTS](https://github.com/aholab/AhoTTS), 2025 `ahotts_common` rewrite commit (`transcribe` mode) | *none released* | original `eu_dicc` | full-vowel diphthongs (no offglides); flat "2nd syllable, 1st if monosyllabic" stress that bypasses dictionary `STR_MRK` |
| **V3** | [arrandi/phonemizer-eus-esp](https://huggingface.co/spaces/arrandi/phonemizer-eus-esp) -- `modulo1y2` + `eu_phonemizer.py` wrapper | [**HiTZ/StyleTTS2-eu**](https://huggingface.co/HiTZ) | `eu_dicc_20250326` | dictionary `STR_MRK` stress like V1 but from the newer dictionary, plus a silent-`h` stress shift, `ʝ` palatalisation, and punctuation emitted as separate tokens |

`pyAhoTTS` builds the V1 engine from
[ekaitz-zarraga/AhoTTS](https://github.com/ekaitz-zarraga/AhoTTS), a packaging
fork of `aholab/AhoTTS` carrying only build/portability changes (CMake,
makefiles) -- no algorithmic difference.

A separate Northern-dialect fork,
[AhoTTS_Iparrahotsa](https://github.com/aholab/AhoTTS_Iparrahotsa) (pronounced
`/h/`, French vowels, uvular r), is off the V1->V3 line and is not implemented.

## How the versions relate

V1 and the 2025 `ahotts_common` rewrite are the **same linguistic engine** (the
same `aholab/AhoTTS` repository at different commits): every `eu_*` source file
is identical apart from the licence header and two additive config branches
(`phtiparralde` and `StressDicSingleWords`).

* **V1** is the original engine. It applies dictionary `STR_MRK` stress through
  the accentual-group machinery (a marked word like `hori` is stressed on its
  first syllable; an unmarked word falls back to the regular stress rule) and
  renders diphthong offglides as `j`/`w`.
* **V2** is the 2025 rewrite's flat `transcribe` path: full-vowel diphthongs (no
  offglides) and a plain 2nd-syllable stress rule that **bypasses** the
  dictionary `STR_MRK` / clitic machinery, so `hori` becomes 2nd-syllable. No
  released model consumes this mode; it is provided for faithfulness to that
  engine path.
* **V3** is the StyleTTS-era `arrandi` build: the same dictionary `STR_MRK`
  stress mechanism as V1 but driven by the newer `eu_dicc_20250326` (which marks
  a different set of words -- e.g. `horrek`/`honek`/`hizkuntza` gain
  first-syllable stress while `hori` loses it), plus a silent-`h` rule that
  anchors an empty leading syllable (shifting audible stress one syllable
  earlier for `h`-initial words) and a wrapper that tokenises punctuation.

## Behavioural signatures (eu)

Stress is shown as the capitalised vowel; "glide" = diphthong offglide as
`j`/`w`; "full-vowel" = offglide kept as plain `i`/`u`.

| word | V1 | V2 | V3 |
|---|---|---|---|
| `berri` | `berI` | `berI` | `berI` |
| `hori` | `Oɾi` (1st, dict) | `oɾI` (2nd, flat) | `oɾi` (unmarked here) |
| `horrek` | `orEk` (2nd) | `orEk` (2nd) | `Orek` (1st, dict) |
| `hizkuntza` | `iʂkUntʂa` (2nd) | `iʂkUntʂa` (2nd) | `IʂkunPa` (1st, dict) |
| `bai` | `bAj` (glide) | `bAi` (full-vowel) | `bAj` (glide) |
| `euskara` | `Ewskaɾa` (glide) | `euskAɾa` (full-vowel) | `Ewskaɾa` (glide) |

V1 and V3 both apply dictionary stress, but from different dictionaries: `hori`
is marked in V1's dictionary but not V3's, while `horrek`/`honek`/`hizkuntza` are
marked in V3's but not V1's. V2 is the outlier -- it bypasses the dictionary
entirely (flat 2nd-syllable stress) and keeps full-vowel diphthongs.

## Which model used which version

* **HiTZ/StyleTTS2-eu** was phonemized by **V3** (arrandi `modulo1y2`). The
  model's training distribution uses dictionary first-syllable stress
  (`horrek -> Orek`, `hizkuntza -> IʂkunPa`), matching the arrandi binary.
* **HiTZ VITS** voices were phonemized by the AhoTTS `tts -Method=Vits` driver,
  whose eu output matches **V1**: dictionary `STR_MRK` stress, offglides, the
  original dictionary.
* **No released model uses V2.** It captures the `transcribe`-mode full-vowel
  behaviour of the modern engine, included for completeness.

See [reverse-engineering.md](reverse-engineering.md) for how each version was
identified from the binaries, and [accuracy.md](accuracy.md) for the verified
parity figures.
