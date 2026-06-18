# AhoTTS engine versions

AhoTTS is not a single phonemizer -- it has a real engine lineage, and
different public Basque voices were phonemized by different generations. The
output differs (most visibly in stress placement and diphthong handling), so
`ahotts-g2p` is **version-aware**: `phonemize(..., version=...)` selects which
engine to reproduce. The two public values are `classic` and `modern`; the
default is `modern`.

* **`classic`** is the original AhoTTS engine, the one that phonemized the HiTZ
  VITS voices.
* **`modern`** is the StyleTTS-era `arrandi` build that phonemized
  HiTZ/StyleTTS2-eu.

## The version table

| Version | Upstream source | Consuming model | Basque dict | Distinctive behaviour |
|---|---|---|---|---|
| **`classic`** | [aholab/AhoTTS](https://github.com/aholab/AhoTTS), original engine; complete public C++ source | **HiTZ VITS** voices | original `eu_dicc` | dictionary `STR_MRK` stress through the accentual-group machinery; vowel offglides (`au` -> `aw`, `ai` -> `aj`) |
| **`modern`** | [arrandi/phonemizer-eus-esp](https://huggingface.co/spaces/arrandi/phonemizer-eus-esp) -- `modulo1y2` + `eu_phonemizer.py` wrapper | [**HiTZ/StyleTTS2-eu**](https://huggingface.co/HiTZ) | `eu_dicc_20250326` | dictionary `STR_MRK` stress like `classic` but from the newer dictionary, plus a silent-`h` stress shift, `ʝ` palatalisation, and punctuation emitted as separate tokens |

`pyAhoTTS` builds the `classic` engine from
[ekaitz-zarraga/AhoTTS](https://github.com/ekaitz-zarraga/AhoTTS), a packaging
fork of `aholab/AhoTTS` carrying only build/portability changes (CMake,
makefiles) -- no algorithmic difference.

A separate Northern-dialect fork,
[AhoTTS_Iparrahotsa](https://github.com/aholab/AhoTTS_Iparrahotsa) (pronounced
`/h/`, French vowels, uvular r), is off the `classic`->`modern` line. It is
implemented as a dialect rather than a version --
`phonemize(..., dialect="northern")`. See [dialects.md](dialects.md).

## How the versions relate

`classic` and the 2025 `ahotts_common` rewrite are the **same linguistic
engine** (the same `aholab/AhoTTS` repository at different commits): every
`eu_*` source file is identical apart from the licence header and two additive
config branches (`phtiparralde` and `StressDicSingleWords`).

* **`classic`** is the original engine. It applies dictionary `STR_MRK` stress
  through the accentual-group machinery (a marked word like `hori` is stressed on
  its first syllable; an unmarked word falls back to the regular stress rule) and
  renders diphthong offglides as `j`/`w`.
* **`modern`** is the StyleTTS-era `arrandi` build: the same dictionary `STR_MRK`
  stress mechanism as `classic` but driven by the newer `eu_dicc_20250326` (which
  marks a different set of words -- e.g. `horrek`/`honek`/`hizkuntza` gain
  first-syllable stress while `hori` loses it), plus a silent-`h` rule that
  anchors an empty leading syllable (shifting audible stress one syllable
  earlier for `h`-initial words) and a wrapper that tokenises punctuation.

## Behavioural signatures (eu)

Stress is shown as the capitalised vowel; "glide" = diphthong offglide as
`j`/`w`; "full-vowel" = offglide kept as plain `i`/`u`.

| word | classic | modern |
|---|---|---|
| `berri` | `berI` | `berI` |
| `hori` | `Oɾi` (1st, dict) | `oɾi` (unmarked here) |
| `horrek` | `orEk` (2nd) | `Orek` (1st, dict) |
| `hizkuntza` | `iʂkUntʂa` (2nd) | `IʂkunPa` (1st, dict) |
| `bai` | `bAj` (glide) | `bAj` (glide) |
| `euskara` | `Ewskaɾa` (glide) | `Ewskaɾa` (glide) |

`classic` and `modern` both apply dictionary stress, but from different
dictionaries: `hori` is marked in the `classic` dictionary but not the `modern`
one, while `horrek`/`honek`/`hizkuntza` are marked in the `modern` dictionary
but not the `classic` one.

## Which model used which version

* **HiTZ/StyleTTS2-eu** was phonemized by **`modern`** (arrandi `modulo1y2`). The
  model's training distribution uses dictionary first-syllable stress
  (`horrek -> Orek`, `hizkuntza -> IʂkunPa`), matching the arrandi binary.
* **HiTZ VITS** voices were phonemized by the AhoTTS `tts -Method=Vits` driver,
  whose eu output matches **`classic`**: dictionary `STR_MRK` stress, offglides,
  the original dictionary.

The modern engine also exposes a flat `transcribe` mode (full-vowel diphthongs,
2nd-syllable stress that bypasses the dictionary). No released model consumes it,
so it is not shipped as a public version;
[reverse-engineering.md](reverse-engineering.md) keeps the research record of
that path for the future.

See [reverse-engineering.md](reverse-engineering.md) for how each version was
identified from the binaries, and [accuracy.md](accuracy.md) for the verified
parity figures.
</content>
</invoke>
