# AhoTTS engine versions

AhoTTS is not a single phonemizer -- it has a real engine lineage, and
different public Basque voices were phonemized by different versions. The
output differs (most visibly in stress placement and diphthong handling), so
`ahotts-g2p` is **version-aware**: `phonemize(..., version=...)` selects which
engine to emulate.

## The lineage

| Version | Phonemizer | Engine source | Basque dict | Stress behaviour | Used by |
|---|---|---|---|---|---|
| **V1** | pyAhoTTS `libhtts` | `ekaitz-zarraga/AhoTTS` (= `aholab/AhoTTS` pre-rewrite) -- complete public source | old `eu_dicc` | dictionary `STR_MRK` via accentual group | pyAhoTTS users |
| **V2** | ahoNT `modulo1y2.so` / hitz `ahotts/tts` | `aholab/AhoTTS` modern `ahotts_common` engine | old `eu_dicc` | **flat 2nd-syllable, no dict stress** | HiTZ VITS voices (`HiTZ/TTS-*`) |
| **V3** | arrandi `modulo1y2` | `ahotts_common` engine, es/eu | `eu_dicc_20250326` | dictionary `STR_MRK` + silent-`h` anchors leading syllable | **HiTZ/StyleTTS2-eu** |
| **V1-ipar** | `AhoTTS_Iparrahotsa` | `aholab/AhoTTS_Iparrahotsa` -- complete public source | Northern `eu_dicc` | Northern: /h/ pronounced, French vowels, uvular r, Iparralde diphthongs | continental Basque |

**V2 and V3 are the same modern engine**, differing only by configuration and
dictionary: V2 runs with flat-stress (dictionary `STR_MRK` off) and the old
dict; V3 enables dictionary stress (`StressDicSingleWords`) plus the silent-`h`
leading-syllable rule and the newer dictionary. V1 is a separate, earlier
codebase.

## Behavioural signatures (eu)

| word | V1 | V2 | V3 |
|---|---|---|---|
| `berri` | `berI` | `berI` | `berI` |
| `horrek` | `Orek` (1st syllable) | `orEk` (2nd) | `Orek` (1st) |
| `hizkuntza` | `'iskuntsa` (1st) | `isk'untsa` (2nd) | `'iskuntsa` (1st) |
| diphthong | glide (`Ewskaɾa`) | full vowel (`euskAɾa`) | glide (V1-like) |

V2 stands out: flat 2nd-syllable stress, no dictionary stress, full-vowel
diphthongs.

## What this release implements

This release is **version-aware across the full lineage**: `phonemize(text,
lang, version)` accepts `lang` in `{eu, es}` and `version` in `{v1, v2, v3}`,
each emulating the matching AhoTTS engine generation.

- **Basque (`lang="eu"`):** `v3` (the default) is served by the hardened HDIC
  fast-path that phonemized `HiTZ/StyleTTS2-eu` and reproduces that oracle
  100%; `v1` and `v2` are served by the version-aware port (`ahotts_versioned`)
  reimplemented from the matching public AhoTTS source states.
- **Spanish (`lang="es"`):** `v1`/`v2`/`v3` are served by `es_phonemizer`.

Each module is a clean-room Python reimplementation of the public AhoTTS C++
source; the binaries are used only to **validate** parity, never to
reverse-engineer rules. See [accuracy.md](accuracy.md) for the verified parity
table.

The `V1-ipar` (Northern / Iparrahotsa) path remains planned.

## Which model used which version

- **HiTZ/StyleTTS2-eu** was phonemized by **V3** (the training distribution's
  `horrek -> Orek` first-syllable stress matches V3, not V2).
- **HiTZ VITS voices** (`HiTZ/TTS-{eu,gl,ca,es}_*`, shipped as
  `vits.onnx` + `config.json`) were phonemized by **V2**.
