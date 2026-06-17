# Usage

## The `phonemize` function

```python
from ahotts_g2p import phonemize

phonemize(text, lang="eu", version="v3") -> str
```

- **`text`** -- input text. Numbers (`1870`), ordinals (`1870.`), number +
  declension suffix (`1870eko`, `22an`) and roman numerals are expanded to
  Basque number words. Punctuation (`.,!?;:`) is kept as separate tokens.
- **`lang`** -- target language. `"eu"` (Basque) is implemented now. `"es"`
  (Spanish) lands in an upcoming release; passing it today raises `ValueError`.
- **`version`** -- AhoTTS engine version to emulate. `"v3"` (the engine that
  phonemized HiTZ/StyleTTS2-eu) is implemented now. `"v1"`/`"v2"` land in
  upcoming releases; passing them today raises `ValueError`. See
  [versions.md](versions.md).

Returns the AhoTTS **single-char IPA training string**: space-separated tokens
(one per word), stressed vowels prefixed, and multi-char phonemes folded to
single characters.

```python
phonemize("Bai.")
# 'bAj .'
phonemize("Ez, horrek ez du balio!")
# 'Eʂ , Orek eʂ tU βalIo !'
```

## SAMPA -> IPA table

```python
from ahotts_g2p import SAMPA_TO_IPA
SAMPA_TO_IPA["tS"]   # 'tʃ'
SAMPA_TO_IPA["s`"]   # 'ʂ'
```

This `OrderedDict` is the same mapping the pipeline uses internally, exposed
for callers that work in SAMPA.

## Command line

```bash
# single string
python -m ahotts_g2p "Kaixo mundua"

# a file via stdin (one sentence per line)
cat sentences.txt | python -m ahotts_g2p

# the console-script entry point (after install)
ahotts-g2p "Bai eta ez."
```

## Batch a dataset file

`ID|text` lines (LJSpeech / StyleTTS2 style) keep the ID and phonemize the
text field:

```bash
python examples/batch_file.py metadata.txt metadata_phonemes.txt
```

## Error handling

Unsupported `lang` or `version` raise `ValueError` with a message pointing at
what is supported and what is coming. This is deliberate: it lets you pin a
version today and get a clear failure rather than silent wrong output when a
not-yet-implemented path is requested.
