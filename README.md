# ahotts-g2p

[![license: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)
[![vibe coded](https://img.shields.io/badge/vibe--coded-%F0%9F%A4%96-ff69b4.svg)](docs/methodology.md)

Pure-Python, **zero-dependency** grapheme-to-phoneme (G2P) front-end for the
[AhoTTS](https://aholab.ehu.eus/) text-to-speech lineage, for **Basque
(euskara)** and Spanish.

`ahotts-g2p` is a pure-Python reimplementation of the AhoTTS linguistic analysis
(stdlib only -- no C build, no runtime dependencies). It turns text into the
single-char IPA training string used by StyleTTS2/VITS-style models, reproducing
the behaviour of the AhoTTS engine that phonemized the public HiTZ Basque voices.

> ### How this port was made, and its licence (please read)
>
> This is an **AI-assisted, human-guided, test-driven** port. An AI assistant
> read the public upstream AhoTTS C/C++ source and reimplemented the algorithms
> in Python; a human guided the effort, chose the targets, and validated every
> result against the real AhoTTS binaries (the binaries are the source of
> truth). The human collaborators **never read the upstream C source
> themselves** -- they drove and checked the work through the binary oracles.
>
> Because the AI implementer **did read the upstream source**, this is **not a
> clean-room reimplementation** and we make no such claim. It is a
> source-derived port. Upstream AhoTTS is **GPL-3.0**, so to honour the original
> work this project is licensed **GPL-3.0** as well (see
> [LICENSE](LICENSE) / [docs/licensing.md](docs/licensing.md)).
>
> **Open questions we want to be transparent about** (we are not lawyers; this
> is awareness, not legal advice):
>
> - *Was this clean-room?* No. The implementing agent read the GPL source, so
>   the usual clean-room defence does not apply.
> - *Could it be relicensed (MIT/Apache/etc.)?* Almost certainly not. A port
>   derived from GPL-3.0 source is a derivative work; GPL-3.0 is the safe,
>   honest choice and we keep it.
> - *Can an AI "assign" or originate a licence at all?* Unsettled. Authorship and
>   copyright of AI-generated code are legally unclear; a licence is a grant by a
>   rights-holder, and who that is here is genuinely uncertain. We apply GPL-3.0
>   as the conservative, upstream-respecting default rather than asserting any
>   novel rights.
>
> If you plan to redistribute or build on this, treat it as GPL-3.0 and read
> [docs/licensing.md](docs/licensing.md) first.

## What it is

- **Pure Python, stdlib only.** No compiler, no `swig`, no shared libraries.
  The bundled dictionaries (`eu_dicc_v1.dic`, `eu_dicc_v3.dic`, `es_dicc.dic`)
  are read straight from their HDIC binary format with `struct`.
- **Version-aware.** AhoTTS has a real engine lineage -- **V1**, **V2** and
  **V3** -- and different public voices were phonemized by different versions,
  with visibly different output. Each maps to a specific upstream repo + binary
  (see the table in [docs/versions.md](docs/versions.md)). The public API takes a
  `version` parameter (`v1`/`v2`/`v3`) and a `lang` parameter (`eu`/`es`) so you
  can pin behaviour.
- **Accurate.** The V3 Basque path reproduces **100%** of the official
  HiTZ/StyleTTS2-eu test split (25/25 lines, exact string match); Spanish is
  exact (100%) across all three versions, and the broader Basque corpus word
  parity is V1 99.45% / V2 99.75% / V3 99.80% against the respective binaries.
  See [docs/accuracy.md](docs/accuracy.md), and
  [Replicating the results](#replicating-the-results) to reproduce these numbers.

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

# version (v1/v2/v3) and lang (eu/es) select the engine generation
phonemize("Kaixo mundua", lang="eu", version="v1")   # 'kajʃO mundUa'
phonemize("Hola mundo.", lang="es", version="v1")    # 'Ola mUndo'
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

## Replicating the results

Correctness is defined as **parity with the real AhoTTS binaries**, not
resemblance to the source. Each version maps to one binary:

| Version | Binary (oracle) | Used by |
|---|---|---|
| `v1` | pyAhoTTS `libhtts` (`transcribe_text`) | pyAhoTTS users |
| `v2` | `ahotts_common` flat path (ahoNT / hitz `ahotts/tts`) | HiTZ VITS voices |
| `v3` | arrandi `modulo1y2` + 2025 dict | HiTZ/StyleTTS2-eu |

The exact-match oracle test needs no binaries:

```bash
pip install -e .[test]
pytest tests/test_oracle.py -q     # reproduces HiTZ/StyleTTS2-eu, 25/25
```

Per-version held-out corpus parity additionally needs the matching binary (it is
the oracle). Full detail in [docs/methodology.md](docs/methodology.md) and
[docs/versions.md](docs/versions.md).

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

**GPL-3.0-or-later**, matching upstream AhoTTS (Aholab / UPV/EHU). This is a
source-derived port (not clean-room -- the implementing AI read the GPL source),
so it is kept under GPL-3.0 to honour the original work. The AhoTTS algorithms
and dictionaries are credited to **Aholab (UPV/EHU)**. See
[docs/licensing.md](docs/licensing.md) for the full rationale and the open
licensing questions.
