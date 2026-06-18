# Reverse engineering: binary <-> source <-> model

AhoTTS ships as several binaries built from related source trees, and different
released models were phonemized by different binaries. This page maps that
landscape: which source produced each binary, which binary phonemized each
model, and how each version's signature is identified. It is the factual basis
for the version definitions in [versions.md](versions.md).

## Sources

| id | source | what it is |
|---|---|---|
| aholab (V1) | [aholab/AhoTTS](https://github.com/aholab/AhoTTS), original engine | the canonical AhoTTS C++ source; complete and public |
| aholab (V2) | [aholab/AhoTTS](https://github.com/aholab/AhoTTS), 2025 rewrite commit | the `ahotts_common` rewrite (same repo, later commit); a superset of the shipped binaries |
| ekaitz | [ekaitz-zarraga/AhoTTS](https://github.com/ekaitz-zarraga/AhoTTS) | a packaging fork of the original `aholab/AhoTTS` (CMake/portability only, no algorithmic change); what `pyAhoTTS` builds |
| ahoNT | [hitz-zentroa/ahoNT](https://github.com/hitz-zentroa/ahoNT) | Python wrapper + prebuilt `modulo1y2.so` (es/eu/gl/ca). No C source. |
| aHoTTS | [hitz-zentroa/aHoTTS](https://github.com/hitz-zentroa/aHoTTS) | VITS synth wrapper + prebuilt `ahotts/tts`. No C source. |
| arrandi | [arrandi/phonemizer-eus-esp](https://huggingface.co/spaces/arrandi/phonemizer-eus-esp) | prebuilt `modulo1y2` (es/eu) + `eu_dicc_20250326.dic` + `eu_phonemizer.py` wrapper. No C source. |
| ahotts_common | *not public* | the internal modern core behind ahoNT / aHoTTS / arrandi / the 2025 rewrite |
| Iparrahotsa | [aholab/AhoTTS_Iparrahotsa](https://github.com/aholab/AhoTTS_Iparrahotsa) | the **Northern (Iparralde) dialect** fork of the V1 engine, with `PhTIparralde` enabled and a Northern `eu_dicc`. Complete public C++ source. Off the V1->V3 line. |

All four prebuilt binaries carry `StressDicSingleWords` + `PhTIparralde` build
strings, so all descend from `ahotts_common`, whose ancestor is the original
`aholab/AhoTTS` engine.

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

| word | pyAhoTTS (V1) | aholab 2025 *transcribe* (V2) | aHoTTS `tts` (VITS) | arrandi (V3) |
|---|---|---|---|---|
| hori | `Oɾi` (1st, dict) | `oɾI` (2nd, flat) | `Oɾi` (1st, dict) | `oɾi` (unmarked) |
| horrek | `orEk` (2nd) | `orEk` (2nd) | `orEk` (2nd) | `Orek` (1st, dict) |
| hizkuntza | `iʂkUntʂa` (2nd) | `iʂkUntʂa` (2nd) | `iʂkUntʂa` (2nd) | `'iskuntsa` (1st, dict) |
| bai | `bAj` (glide) | `bAi` (full-vowel) | `bA` + offglide (glide) | `bAj` (glide) |
| euskara | `Ewskara` (glide) | `eusk'ara` (full-vowel) | `E` + offglide (glide) | `Ewskara` (glide) |
| berri | `berI` | `berI` | `berI` | `berI` |

`hori` is the discriminator: V1 and the VITS driver mark it first-syllable from
the original dictionary, V2 bypasses the dictionary (flat 2nd-syllable), and V3's
newer dictionary does not mark it -- while V3 *does* mark `horrek`/`hizkuntza`,
which the original dictionary leaves to the regular rule.

## Capture method

* pyAhoTTS and aholab-new are exercised through an added `transcribe_text` C
  export.
* ahoNT is exercised through `transkripzioa(mode=Phone)`.
* The aHoTTS `tts` VITS driver does not expose phonemes directly; its
  tokenisation is recovered by replacing `vits.onnx` with an identity graph,
  running `-Method=Vits`, reading the int64 token ids, and decoding them through
  the recovered 54-symbol map.
* arrandi is exercised through `modulo1y2 -Lang=eu`.
* AhoTTS_Iparrahotsa (the Northern dialect) is exercised through the same
  `transcribe_text` C export, rebuilt against the Iparrahotsa `libhtts` and the
  Northern `eu_dicc`; this is the oracle for the `dialect="northern"` corpus
  (see [dialects.md](dialects.md)).

## Model -> version mapping

There are two model-facing eu phonemizations:

| model | phonemizer | version | distinctive |
|---|---|---|---|
| **HiTZ VITS** | aHoTTS `tts -Method=Vits` | **V1** | original-dictionary `STR_MRK` stress, offglides |
| **HiTZ/StyleTTS2-eu** | arrandi `modulo1y2` + wrapper | **V3** | newer-dictionary `STR_MRK` stress, `eu_dicc_20250326`, `ʝ`, punctuation tokens |

The VITS mapping is confirmed on the discriminator `hori`: the VITS driver emits
`Oɾi` (first-syllable, from the original dictionary), exactly as V1 -- not the
flat `oɾI` of V2 nor the unmarked `oɾi` of V3. The StyleTTS2-eu mapping is
confirmed by the model's training distribution, which uses the newer dictionary's
first-syllable stress (`horrek -> Orek`, `hizkuntza -> IʂkunPa`) -- the arrandi
signature, which the original-dictionary binaries do not produce.

The full-vowel-diphthong, flat-2nd-syllable output (the `aholab 2025
transcribe` column above) is the `transcribe`-mode path of the modern engine.
The VITS tokenisation path of that same engine emits offglides and dictionary
stress, so **no released model consumes the `transcribe`-mode output** — which
is why it is not shipped as a public version of this port. The mapping is kept
here as a research record: if a future model is ever phonemized through that
mode, re-adding it is an informed change (the column above states exactly what
it produces) rather than a rediscovery.
