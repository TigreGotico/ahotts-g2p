# AhoTTS engine versions

AhoTTS is not a single phonemizer -- it has a real engine lineage, and
different public Basque voices were phonemized by different generations. The
output differs (most visibly in stress placement and diphthong handling), so
`ahotts-g2p` is **version-aware**: `phonemize(..., version=...)` selects which
engine to reproduce. The default is `v3`.

## The version table

| Version | Upstream source | Consuming model | Basque dict | Distinctive behaviour |
|---|---|---|---|---|
| **V1** | [ekaitz-zarraga/AhoTTS](https://github.com/ekaitz-zarraga/AhoTTS) -- original AhoTTS (= `aholab/AhoTTS` pre-rewrite); complete public C++ source | **HiTZ VITS** voices | old `eu_dicc` | accentual-group stress with dictionary `STR_MRK`; vowel offglides (`au` -> `aw`, `ai` -> `aj`) |
| **V2** | [aholab/AhoTTS](https://github.com/aholab/AhoTTS) Dec-2025 `ahotts_common` rewrite, `transcribe` mode | *none released* | old `eu_dicc` | no offglides (full-vowel diphthongs); flat "2nd syllable, 1st if monosyllabic" stress for every word |
| **V3** | [arrandi/phonemizer-eus-esp](https://huggingface.co/spaces/arrandi/phonemizer-eus-esp) -- `modulo1y2` + `eu_phonemizer.py` wrapper | [**HiTZ/StyleTTS2-eu**](https://huggingface.co/HiTZ) | `eu_dicc_20250326` | like V1, plus a silent-`h` stress shift, `ʝ` palatalisation, and punctuation emitted as separate tokens |

A separate Northern-dialect fork,
[AhoTTS_Iparrahotsa](https://github.com/aholab/AhoTTS_Iparrahotsa) (pronounced
`/h/`, French vowels, uvular r), is off the V1->V3 line and is not implemented.

## How the versions relate

V1 and the Dec-2025 `ahotts_common` rewrite are the **same linguistic engine**:
every `eu_*` source file is identical apart from the licence header and two
additive config branches (`phtiparralde` and `StressDicSingleWords`). With both
off -- the default -- the rewrite reduces to V1.

* **V1** is the pre-rewrite codebase. It applies dictionary `STR_MRK`
  first-syllable stress through the accentual-group machinery and renders
  diphthong offglides as `j`/`w`.
* **V2** is the modern engine's flat `transcribe` path: no offglides, and a
  plain 2nd-syllable stress rule that bypasses the dictionary `STR_MRK` /
  clitic machinery. No released model consumes this mode; it is provided for
  faithfulness to that engine path.
* **V3** is the StyleTTS-era `arrandi` build: the same accentual stress as V1,
  plus a silent-`h` rule that anchors an empty leading syllable (shifting
  audible stress one syllable earlier for `h`-initial words), the newer
  dictionary, and a wrapper that tokenises punctuation.

## Behavioural signatures (eu)

Stress is shown as the capitalised vowel; "glide" = diphthong offglide as
`j`/`w`; "full-vowel" = offglide kept as plain `i`/`u`.

| word | V1 | V2 | V3 |
|---|---|---|---|
| `berri` | `berI` | `berI` | `berI` |
| `horrek` | `orEk` (2nd, rule) | `orEk` (2nd, rule) | `Orek` (1st, dict) |
| `hizkuntza` | `iʂkUntʂa` (2nd) | `iʂkUntʂa` (2nd) | `IʂkunPa` (1st, dict) |
| `bai` | `bAj` (glide) | `bAi` (full-vowel) | `bAj` (glide) |
| `euskara` | `Ewskaɾa` (glide) | `euskAɾa` (full-vowel) | `Ewskaɾa` (glide) |

V2 stands out by its full-vowel diphthongs; V3 by its dictionary first-syllable
stress on demonstratives and common nouns.

## Which model used which version

* **HiTZ/StyleTTS2-eu** was phonemized by **V3** (arrandi `modulo1y2`). The
  model's training distribution uses dictionary first-syllable stress
  (`horrek -> Orek`, `hizkuntza -> IʂkunPa`), matching the arrandi binary.
* **HiTZ VITS** voices were phonemized by the AhoTTS `tts -Method=Vits` driver,
  whose eu output matches **V1**: rule-stress, offglides, old dictionary.
* **No released model uses V2.** It captures the `transcribe`-mode full-vowel
  behaviour of the modern engine, included for completeness.

See [reverse-engineering.md](reverse-engineering.md) for how each version was
identified from the binaries, and [accuracy.md](accuracy.md) for the verified
parity figures.
