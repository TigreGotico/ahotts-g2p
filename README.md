# ahotts-g2p

[![license: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)

Pure-Python, **zero-dependency**, version-aware grapheme-to-phoneme (G2P) for
**Basque (euskara)** and **Spanish**, faithfully reproducing the
[AhoTTS](https://aholab.ehu.eus/) text-to-speech front-end.

`ahotts-g2p` turns text into the single-char IPA training string used by
StyleTTS2/VITS-style models, matching the AhoTTS engines that phonemized the
public HiTZ Basque voices. It is stdlib-only: no C build, no shared libraries,
no runtime dependencies.

## Install

```bash
pip install ahotts-g2p
```

From source:

```bash
pip install -e .[test]
```

## Quick start

```python
from ahotts_g2p import phonemize

phonemize("Bai.")                                    # 'bAj .'
phonemize("Ez, horrek ez du balio!")                 # 'Eʂ , Orek eʂ tU βalIo !'
phonemize("Kaixo mundua", lang="eu", version="v1")   # 'kajʃO mundUa'
phonemize("Hola mundo.", lang="es", version="v1")    # 'Ola mUndo'
```

CLI:

```bash
python -m ahotts_g2p "Kaixo mundua"
cat sentences.txt | python -m ahotts_g2p
```

Also exported: `SAMPA_TO_IPA`, the ordered SAMPA -> IPA mapping table.

## Versions

AhoTTS has a real engine lineage. Different public voices were phonemized by
different generations, with visibly different output, so the API takes a
`version` (`v1`/`v2`/`v3`). The default is `v3`.

| Version | Upstream source | Consuming model | Distinctive behaviour |
|---|---|---|---|
| `v1` | [aholab/AhoTTS](https://github.com/aholab/AhoTTS), original engine | **HiTZ VITS** voices | dictionary `STR_MRK` stress (original `eu_dicc`), vowel offglides (au -> aw) |
| `v2` | [aholab/AhoTTS](https://github.com/aholab/AhoTTS), 2025 `ahotts_common` rewrite (`transcribe` mode) | *none released* (completeness) | flat 2nd-syllable stress (bypasses `STR_MRK`), full-vowel diphthongs (no offglides) |
| `v3` | [arrandi/phonemizer-eus-esp](https://huggingface.co/spaces/arrandi/phonemizer-eus-esp) `modulo1y2` + `eu_dicc_20250326` | [HiTZ/StyleTTS2-eu](https://huggingface.co/HiTZ) | dictionary `STR_MRK` stress (newer dict), silent-`h` stress shift, `ʝ` palatalisation, punctuation tokens |

(`pyAhoTTS` builds the v1 engine from [ekaitz-zarraga/AhoTTS](https://github.com/ekaitz-zarraga/AhoTTS), a packaging fork of `aholab/AhoTTS` with build/portability changes only -- no algorithmic difference.)

Full detail in [docs/versions.md](docs/versions.md).

## Accuracy

Correctness is parity with the AhoTTS reference engines, measured per version on
held-out corpora (positional word match):

| Language | v1 | v2 | v3 |
|---|---|---|---|
| Spanish (`es`) | 100% | 100% | 100% |
| Basque (`eu`) | 99.94% | 100% | 99.90% |

The held-out corpora ship as test fixtures, so the figures reproduce with no
binaries: `pytest tests/test_oracle.py`. See [docs/accuracy.md](docs/accuracy.md).

## Pipeline

```
text -> normalize -> g2p -> syllabify -> stress -> SAMPA -> IPA -> single-char
```

Numbers, ordinals and roman numerals are expanded to the target-language number
words; punctuation is preserved as separate tokens (v3) or dropped (v1/v2). Per-
word lexical stress and the phonetic-exception rules are driven by the decoded
dictionary flags. See [docs/architecture.md](docs/architecture.md).

## Supported languages

- **Basque (`eu`)** -- full linguistic pipeline with HDIC-dictionary POS tagging
  and accentual-group stress.
- **Spanish (`es`)** -- dictionary-free g2p and stress.

## Where it fits

| Project | Role |
|---|---|
| **AhoTTS** (Aholab, UPV/EHU) | upstream C++ engine; the algorithm source |
| **pyAhoTTS** | Python bindings to the AhoTTS C++ library (needs a build) |
| **ahotts-g2p** (this repo) | pure-Python reimplementation of the G2P, no build |
| **phoonnx** | downstream consumer -- ONNX TTS runtime that uses this G2P |

## License

**GPL-3.0-or-later**, matching upstream AhoTTS. This is a derivative of the GPL
AhoTTS linguistic rules, so it is distributed under the same licence. The AhoTTS
algorithms and dictionaries are credited to **Aholab (UPV/EHU)**. See
[docs/licensing.md](docs/licensing.md).
