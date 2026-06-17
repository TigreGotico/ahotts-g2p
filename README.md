# ahotts-g2p

Pure-Python, **zero-dependency** grapheme-to-phoneme (G2P) front-end for the
[AhoTTS](https://aholab.ehu.eus/) text-to-speech lineage, for **Basque
(euskara)** and Spanish.

`ahotts-g2p` is an **independent, clean-room reimplementation** of the AhoTTS
linguistic analysis in plain Python (stdlib only -- no C build, no runtime
dependencies). It turns text into the single-char IPA training string used by
StyleTTS2/VITS-style models, faithfully reproducing the behaviour of the
AhoTTS engine that phonemized the public HiTZ Basque voices.

## What it is

- **Pure Python, stdlib only.** No compiler, no `swig`, no shared libraries.
  The bundled Basque dictionary (`eu_dicc.dic`) is read straight from its HDIC
  binary format with `struct`.
- **Version-aware (planned).** AhoTTS has a real engine lineage -- V1
  (pyAhoTTS `libhtts`), V2 (the `ahotts_common` rewrite, flat 2nd-syllable
  stress) and V3 (`ahotts_common` with dictionary stress + the 2025 dict).
  The public API takes a `version` parameter so you can pin behaviour. This
  release ships **V3** Basque; V1/V2 and Spanish (`es`) land in upcoming
  releases. See [docs/versions.md](docs/versions.md).
- **Accurate.** The V3 Basque path reproduces **100%** of the official
  HiTZ/StyleTTS2-eu test split (25/25 lines, exact string match). See
  [docs/accuracy.md](docs/accuracy.md).

## Install

```bash
pip install ahotts-g2p
```

From source:

```bash
pip install -e .[test]
```

## Usage

```python
from ahotts_g2p import phonemize

phonemize("Bai.")
# 'bAj .'

phonemize("Ez, horrek ez du balio!")
# 'Eʂ , Orek eʂ tU βalIo !'

# version / lang are accepted now (V3 Basque today; V1/V2 + es later)
phonemize("Kaixo mundua", lang="eu", version="v3")
```

CLI:

```bash
python -m ahotts_g2p "Kaixo mundua"
# or pipe a file
cat sentences.txt | python -m ahotts_g2p
```

Also exposed: `SAMPA_TO_IPA`, the ordered SAMPA -> IPA mapping table.

## Pipeline

```
text -> normalize -> g2p -> syllabify -> stress -> SAMPA -> IPA -> single-char
```

Numbers, ordinals and roman numerals are expanded to Basque number words;
punctuation is preserved as separate tokens. Per-word lexical stress and the
no-palatalisation rule are driven by the decoded dictionary flags. Full
details in [docs/architecture.md](docs/architecture.md).

## Where it fits

| Project | Role |
|---|---|
| **AhoTTS** (Aholab, UPV/EHU) | upstream C++ engine; the algorithm source |
| **pyAhoTTS** | Python *bindings* to the AhoTTS C++ library (needs a build) |
| **ahotts-g2p** (this repo) | pure-Python *reimplementation* of the G2P, no build |
| **phoonnx** | downstream *consumer* -- ONNX TTS runtime that uses this G2P |

Use `ahotts-g2p` when you want the AhoTTS phoneme strings without compiling
the C++ engine -- e.g. in a TTS inference runtime or a dataset pipeline.

## License

Apache-2.0. This is an independent pure-Python reimplementation; no AhoTTS
(GPL) source is copied. The AhoTTS algorithms and dictionary are credited to
**Aholab (UPV/EHU)** in [NOTICE](NOTICE). See
[docs/licensing.md](docs/licensing.md).
