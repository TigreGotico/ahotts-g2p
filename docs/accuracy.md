# Accuracy

## The StyleTTS2-eu oracle

The reference for the V3 Basque path is the official **HiTZ/StyleTTS2-eu** test
split: 25 sentences with their AhoTTS-phonemized targets. Both files ship under
[`../tests/data/`](../tests/data):

- `test_tts_eu.txt` -- `ID|text` input lines;
- `test_tts_eu_phonemes.txt` -- `ID|phonemes` gold output.

`ahotts-g2p` reproduces **all 25 lines exactly** (100% string match). This is
asserted by [`tests/test_oracle.py`](../tests/test_oracle.py): each line is a
parametrized case, plus a `test_oracle_full_parity_100pct` guard that fails if
parity ever drops below 25/25.

```
$ pytest tests/test_oracle.py -q
26 passed
```

Example (line 5):

```
in : Tailandiara bidaiatzea gustatuko litzaidake, Bangkok ezagutu nahiko nuke.
out: taʎAndiaɾa βiðAʝaPea ɣustAtuko liPAjðake , bankOk eʂAɣutu naIko nukE .
```

## Why it generalises beyond 25 lines

Parity is not achieved by memorising the oracle. The pipeline drives
first-syllable stress (`STR_MRK`) and the no-palatalisation rule
(`SALBTF_N_J_N`) from the **decoded dictionary flags** -- hundreds of words
carry these -- and number expansion is computed, not tabulated. Only a small
set of phonetic-rule / foreign-romanisation quirks that the dictionary does not
encode through its bits remain as explicit per-word overrides.

## Per-version parity status

All paths are implemented. Parity is measured word-for-word against the
corresponding AhoTTS binary's output over a held-out corpus (`corpus.txt` /
`corpus_es.txt`, validated by `validate.py` / `validate_es.py` in the source
snapshot):

| Version | Lang | Status | Word parity | Oracle binary |
|---|---|---|---|---|
| **V3** | eu | implemented | **99.80%** | arrandi `modulo1y2` + `eu_dicc_20250326`; HiTZ/StyleTTS2-eu **100%** (25/25, fast-path) |
| **V1** | eu | implemented | **99.45%** | pyAhoTTS `libhtts` (`transcribe_text`) |
| **V2** | eu | implemented | **99.75%** | ahoNT / hitz `ahotts/tts` flat path |
| **V1** | es | implemented | **100.00%** | pyAhoTTS `libhtts` (es) |
| **V2** | es | implemented | **100.00%** | ahoNT (es) |
| **V3** | es | implemented | **100.00%** | arrandi `modulo1y2` (es) |
| V1-ipar | eu (Northern) | planned | -- | `AhoTTS_Iparrahotsa` |

(Word parity is measured against each version's binary over the held-out
`corpus.txt`; see [Replicating the results](../README.md#replicating-the-results).
The exact binary each version maps to is in [versions.md](versions.md).)

Spanish is exact (100% across all three versions) because Spanish g2p and
stress are fully rule-driven, with the bundled `es_dicc` only respelling a
short list of foreign words and abbreviations.

The hardened V3 Basque fast-path (`ahotts_eu_hdic`, the `lang="eu",
version="v3"` route) reproduces the StyleTTS2-eu oracle exactly (25/25); the
general `ahotts_versioned` V3 path scores 98.25% word parity over the broader
corpus.

### Documented residual (Basque OOV / foreign words)

The remaining Basque word mismatches are concentrated in out-of-vocabulary
**foreign / loan words** that the AhoTTS dictionary romanises with
word-specific rules the port does not encode bit-for-bit (e.g. `Bangkok`,
proper names, and a few roman-numeral edge cases in mixed numeric contexts).
These are an inherent property of OOV foreign-word romanisation and are
expected to persist; native Basque vocabulary is reproduced exactly via the
decoded dictionary flags.

The binaries are used only to **validate** a faithful source-based port, never
to reverse-engineer rules.
