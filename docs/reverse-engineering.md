# Reverse engineering: binary <-> source <-> model

AhoTTS ships as several binaries built from related source trees, and different
released models were phonemized by different binaries. This page maps that
landscape: which source produced each binary, which binary phonemized each
model, and how each version's signature is identified. It is the factual basis
for the version definitions in [versions.md](versions.md).

## Sources

| id | source | what it is |
|---|---|---|
| ekaitz | [ekaitz-zarraga/AhoTTS](https://github.com/ekaitz-zarraga/AhoTTS) | AhoTTS before the Dec-2025 rewrite, with CMake/portability patches. Complete public C++; what `pyAhoTTS` bundles. |
| aholab-old | [aholab/AhoTTS](https://github.com/aholab/AhoTTS) (2022) | the same engine as ekaitz |
| aholab-new | [aholab/AhoTTS](https://github.com/aholab/AhoTTS) (Dec-2025) | the modern `ahotts_common` rewrite; a superset of the shipped binaries |
| ahoNT | [hitz-zentroa/ahoNT](https://github.com/hitz-zentroa/ahoNT) | Python wrapper + prebuilt `modulo1y2.so` (es/eu/gl/ca). No C source. |
| aHoTTS | [hitz-zentroa/aHoTTS](https://github.com/hitz-zentroa/aHoTTS) | VITS synth wrapper + prebuilt `ahotts/tts`. No C source. |
| arrandi | [arrandi/phonemizer-eus-esp](https://huggingface.co/spaces/arrandi/phonemizer-eus-esp) | prebuilt `modulo1y2` (es/eu) + `eu_dicc_20250326.dic` + `eu_phonemizer.py` wrapper. No C source. |
| ahotts_common | *not public* | the internal modern core behind ahoNT / aHoTTS / arrandi / aholab-new |

All four binaries carry `StressDicSingleWords` + `PhTIparralde` build strings,
so all descend from `ahotts_common`; ekaitz is its pre-rewrite ancestor.

## Binary fingerprints

| binary | langs | eu dict |
|---|---|---|
| pyAhoTTS `libhtts` (ekaitz fork) | es/eu | old `eu_dicc` |
| ahoNT `modulo1y2.so` | es/eu/gl/ca | old `eu_dicc` (= pyAhoTTS) |
| aHoTTS `ahotts/tts` (VITS) | eu/gl/ca/es | old `eu_dicc` |
| arrandi `modulo1y2` | es/eu | `eu_dicc_20250326` |

## Empirical signature table (eu)

Stress is shown as the capitalised vowel; "glide" = diphthong offglide as
`j`/`w` (or the VITS offglide ids 30/33); "full-vowel" = offglide kept as plain
`i`/`u`.

| word | pyAhoTTS (V1) | aholab-new *transcribe* (V2) | aHoTTS `tts` (VITS) | arrandi (V3) |
|---|---|---|---|---|
| horrek | `orEk` (2nd, rule) | `orEk` (2nd, rule) | `orEk` (2nd, rule) | `Orek` (1st, dict) |
| hizkuntza | `iʂkUntʂa` (2nd) | `iʂkUntʂa` (2nd) | `iʂkUntʂa` (2nd) | `'iskuntsa` (1st, dict) |
| bai | `bAj` (glide) | `bAi` (full-vowel) | `bA` + offglide (glide) | `bAj` (glide) |
| euskara | `Ewskara` (glide) | `eusk'ara` (full-vowel) | `E` + offglide (glide) | `Ewskara` (glide) |
| berri | `berI` | `berI` | `berI` | `berI` |

## Capture method

* pyAhoTTS and aholab-new are exercised through an added `transcribe_text` C
  export.
* ahoNT is exercised through `transkripzioa(mode=Phone)`.
* The aHoTTS `tts` VITS driver does not expose phonemes directly; its
  tokenisation is recovered by replacing `vits.onnx` with an identity graph,
  running `-Method=Vits`, reading the int64 token ids, and decoding them through
  the recovered 54-symbol map.
* arrandi is exercised through `modulo1y2 -Lang=eu`.

## Model -> version mapping

There are two model-facing eu phonemizations:

| model | phonemizer | version | distinctive |
|---|---|---|---|
| **HiTZ VITS** | aHoTTS `tts -Method=Vits` | **V1** | rule-stress, offglides, old dict |
| **HiTZ/StyleTTS2-eu** | arrandi `modulo1y2` + wrapper | **V3** | dict-stress, `eu_dicc_20250326`, `ʝ`, punctuation tokens |

The StyleTTS2-eu mapping is confirmed by the model's training distribution,
which uses dictionary first-syllable stress (`horrek -> Orek`,
`hizkuntza -> IʂkunPa`) -- the arrandi signature, not the rule-stress of the
other binaries.

The full-vowel-diphthong **V2** output is the `transcribe`-mode path of the
modern engine; the VITS tokenisation path of that same engine emits offglides,
so no shipped model consumes the V2 output. It is implemented for faithfulness
to that engine mode.
