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

| Version | Lang | Status | Oracle |
|---|---|---|---|
| **V3** | eu | implemented, **100%** | HiTZ/StyleTTS2-eu (25/25) |
| V1 | eu | planned | pyAhoTTS `libhtts` outputs |
| V2 | eu | planned | ahoNT / hitz VITS outputs |
| V1-ipar | eu (Northern) | planned | `AhoTTS_Iparrahotsa` outputs |
| (any) | es | planned | AhoTTS Spanish outputs |

The binaries are used only to **validate** a faithful source-based port, never
to reverse-engineer rules.
