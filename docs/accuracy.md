# Accuracy

Correctness is parity with the AhoTTS reference engines, measured per version on
held-out corpora that ship as test fixtures (`tests/data/eu_corpus.json`,
`tests/data/es_corpus.json`). Each row pairs a source sentence with the
reference engine's phonemized output; scoring is positional (space-split) word
match plus exact-line match.

## Per-version parity

| Language | v1 | v3 |
|---|---|---|
| Spanish (`es`) | 100% | 100% |
| Basque (`eu`) | 99.94% | 99.90% |

The Northern Basque dialect (`dialect="northern"`) reaches **98.97%** word
parity (401/430 exact lines) against the AhoTTS_Iparrahotsa binary, over the
`tests/data/eu_northern_corpus.json` fixture. See [dialects.md](dialects.md).

Each figure is enforced by `tests/test_oracle.py`, which fails if parity drops
below the verified threshold. Spanish is exact across both versions
because Spanish g2p and stress are fully rule-driven; the bundled `es_dicc` only
respells a short list of foreign words and abbreviations.

## Reproducing

The parity tests need no external binaries -- the reference corpora are bundled:

```bash
pip install -e .[test]
pytest tests/test_oracle.py -q
```

## Documented residual (Basque OOV / foreign words)

The small number of Basque mismatches are concentrated in out-of-vocabulary
**foreign / loan words** that AhoTTS romanises with word-specific rules the port
does not encode bit-for-bit (e.g. some proper names and roman-numeral edge cases
in mixed numeric contexts). These are an inherent property of OOV foreign-word
romanisation; native Basque vocabulary is reproduced exactly via the decoded
dictionary flags.
