# Methodology

`ahotts-g2p` is a faithful reimplementation of the AhoTTS linguistic pipeline
in pure Python. This page states how correctness is defined and verified.

## Correctness is parity with the reference engines

Correctness is **behavioural parity with the AhoTTS reference engines**, not
resemblance to the source. Each version maps to a specific reference:

* **V1** -- the pyAhoTTS `libhtts` build (`transcribe_text`).
* **V2** -- the modern `ahotts_common` flat `transcribe` path.
* **V3** -- the `arrandi` `modulo1y2` build with the 2025 dictionary.

Where a binary diverges from its own published source, the port reproduces the
**binary** -- the runtime ground truth -- since that is what each released model
was phonemized with.

## How parity is verified

Two complementary checks back every figure.

1. **Oracle parity (in CI, no binaries needed).** Per-version held-out corpora
   ship as test fixtures under [`../tests/data/`](../tests/data)
   (`eu_corpus.json`, `es_corpus.json`). Each row pairs a source sentence with
   the reference engine's phonemized output. `tests/test_oracle.py` scores the
   package against these corpora and fails if word parity or exact-line counts
   drop below the verified thresholds.

2. **Distribution check.** The V3 eu path is additionally checked against the
   convention used in the HiTZ/StyleTTS2-eu training distribution (dictionary
   first-syllable stress), confirming the default path matches the data the
   released model was trained on.

## Why it generalises

Parity is not achieved by memorising the corpus. First-syllable stress
(`STR_MRK`), the no-palatalisation rule (`SALBTF_*`), part-of-speech tagging,
and the other dictionary-driven behaviours are read from the **decoded
dictionary bitfields** via the faithful HDIC binary search and the
`eu_categ`/`pos1` POS cascade. Number, ordinal, and roman-numeral expansion is
computed. Only a small set of out-of-vocabulary foreign-word romanisation
quirks that the dictionary does not encode through its bits remain as explicit
per-word handling; native vocabulary generalises from the decoded data.

## Reproducing the numbers

The oracle parity test runs with no external binaries:

```bash
pip install -e .[test]
pytest tests/test_oracle.py -q
```

The reference corpora were captured from the AhoTTS engines themselves; see
[reverse-engineering.md](reverse-engineering.md) for the capture method and
[accuracy.md](accuracy.md) for the figures.
