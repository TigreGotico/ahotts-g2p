# Usage

## The `phonemize` function

```python
from ahotts_g2p import phonemize

phonemize(text, lang="eu", version="modern", dialect="standard") -> str
```

- **`text`** -- input text. Numbers (`1870`), ordinals (`1870.`), number +
  declension suffix (`1870eko`, `22an`) and roman numerals are expanded to
  number words. Punctuation (`.,!?;:`) is kept as separate tokens in `modern`.
- **`lang`** -- target language: `"eu"` (Basque) or `"es"` (Spanish).
- **`version`** -- AhoTTS engine to emulate: `"classic"` (the original engine,
  used by the HiTZ VITS voices) or `"modern"` (the default; the StyleTTS-era
  build that phonemized HiTZ/StyleTTS2-eu). Each emulates a distinct engine
  generation. See [versions.md](versions.md).
- **`dialect`** -- Basque dialect: `"standard"` (default, Southern) or
  `"northern"` (Iparralde / Iparrahotsa). `"northern"` is Basque-only and
  ignores `version` (it is a single `classic`-lineage fork). See [dialects.md](dialects.md).

Returns the AhoTTS **single-char IPA training string**: space-separated tokens
(one per word), stressed vowels prefixed, and multi-char phonemes folded to
single characters.

```python
phonemize("Bai.")                              # 'bAj .'  (eu, modern default)
phonemize("Ez, horrek ez du balio!")           # 'Eʂ , Orek eʂ tU βalIo !'
phonemize("Kaixo mundua.", "eu", "classic")    # 'kajʃO mundUa'  (no punct in classic)
phonemize("Hola mundo.", "es", "classic")      # 'Ola mUndo'
phonemize("Hola mundo.", "es", "modern")       # 'Ola mUndo .'

# Northern (Iparralde / Iparrahotsa) Basque dialect
phonemize("hori horrek", "eu", dialect="northern")   # 'hOɾi hoʁEk'
phonemize("bürü", "eu", dialect="northern")          # 'byʁy'
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

Unsupported `lang` (anything but `eu`/`es`) or `version` (anything but
`classic`/`modern`) raises `ValueError` with a message pointing at what is
supported. This lets you pin a language/version and get a clear failure rather
than silent wrong output.

---
[← Installation](installation.md) · [Home](README.md) · [Versions →](versions.md)
