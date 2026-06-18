# Basque dialects: Northern (Iparralde / Iparrahotsa)

The standard `ahotts-g2p` Basque engine reproduces the Southern (Hegoalde,
Batua) AhoTTS phonemizer. AhoTTS also ships a separate Northern-dialect engine,
**AhoTTS_Iparrahotsa**, for the continental (Iparralde) varieties spoken in the
French Basque Country. It is a fork of the V1 engine with the `PhTIparralde`
configuration enabled, and it is exposed here as a **dialect**:

```python
from ahotts_g2p import phonemize

phonemize("Euskara Euskal Herriko hizkuntza da.", lang="eu", dialect="northern")
# 'Ewʂkaɾa ewʂkAl heʁIko hiskUnVa ðA'
```

`dialect="standard"` (the default) keeps the existing Southern behaviour, so all
existing calls are unchanged. `dialect="northern"` is only valid for `lang="eu"`.
Because the Northern engine is a single V1-lineage fork, it does not cross with
the `v1`/`v2`/`v3` versions; the `version` argument is ignored when
`dialect="northern"`.

## What makes it Northern

The Northern dialect differs from Southern Basque in its consonant and vowel
inventory. The Iparrahotsa engine implements these as a set of grapheme-to-
phoneme changes (gated on the `PhTIparralde` flag in the C source):

| Feature | Southern | Northern |
|---|---|---|
| `h` | silent | **pronounced /h/** (except mid-word after p/k/l/n/c/t/r: *ekharri* -> *ekarri*) |
| `ü` | /u/ | **French /y/** (*bürü* -> /byʁy/) |
| `u` + `e` | two vowels | glide /w/ + e (one diphthong syllable: *zuen* is monosyllabic) |
| strong `r` / `rr` | alveolar trill /r/ | **uvular /ʁ/** (tap /ɾ/ kept for *ur*/*zur* before a pause or consonant) |
| `s` | /s̺/ (ʂ) | laminal /s̻/ (ʂ -> the laminal series) |
| `z` | laminal /s̻/ | **/s/** |
| `ts` (orthographic) | /ts/ | /tʂ/ |
| `tz` (orthographic) | /tʂ/ | /ts/ |
| `c` before e/i | /θ/ | /s̻/ |
| `ch` | /tʃ/ | /ʃ/ |
| `j`, `y`, `dd` | /ɟ̞/ or /ʝ/ | **voiced palatal stop /ɟ/** (no Castilian /x/ exceptions) |
| `n`, `l` before a vowel | palatalise (/ɲ/, /ʎ/) | no palatalisation |
| `tch` (trigraph) | -- | rewritten to `tx` (*Etcheberry* -> *Etxeberry*) |
| word-final stop sandhi (st/ts/tz reductions) | applied | suppressed (*bortitz bat* keeps the affricate) |

Stress is the same V1 accentual-group machinery, driven by the Northern
dictionary's `STR_MRK` marks. One audible consequence of the `u+e` diphthong:
monosyllabic synthetic/auxiliary verbs such as *zuen*, *duen* lose their accent
after a conjugated verb (*egin zuen* -> *eɣIn swen*), where the Southern engine,
treating *zuen* as bisyllabic, keeps it (*eɣIn ʂuEn*).

## Phone inventory additions

The Northern output adds three phones to the standard map (see
[architecture.md](architecture.md) for the SAMPA/IPA tables):

| SAMPA | IPA | description |
|---|---|---|
| `R` | ʁ | uvular r |
| `J\` | ɟ | voiced palatal stop |
| `y` | y | French close front rounded vowel |

and pronounces `h` (/h/) and the laminal/apical sibilants that the Southern
engine also has but distributes differently.

## Source and provenance

* **Engine**: [AhoTTS_Iparrahotsa](https://github.com/aholab/AhoTTS_Iparrahotsa)
  (`libhtts`), Aholab (UPV/EHU) -- a fork of the V1 AhoTTS engine with
  `PhTIparralde` enabled. The Northern deltas are localised to a handful of
  `eu_*` source files (`eu_phtr.cpp` grapheme cases, `eu_uti.cpp` vowel/diphthong
  predicates, `eu_cap.cpp` `tch` rewrite, `eu_syl.cpp`/`eu_stre.cpp`
  syllabification and stress), ported here 1:1 on top of the shared engine.
* **Dictionary**: the Northern `eu_dicc.dic` shipped with that engine, bundled as
  `eu_dicc_northern.dic` and read by the same stdlib HDIC reader as the other
  dictionaries.
* **Encoding**: the engine expects WINDOWS-1252 (cp1252) input; the pure-Python
  port works on Unicode text directly, so no transcoding is needed at the API.

## Accuracy

Parity is measured against the AhoTTS_Iparrahotsa binary (driven through a
`transcribe_text` C export), over the 430-sentence Basque corpus shipped as the
`eu_northern_corpus.json` test fixture:

* **word parity ~99.0%**, **401/430 exact lines**.

The residual lines are documented faithful-artifacts, not approximation hacks:

* **Northern number/date normalisation** -- the Northern `eu_normal` expands some
  dates and number ranges differently from the Southern path.
* **Foreign / French proper names** -- names with their own Northern-dictionary
  transcriptions, some carrying nasal vowels (e.g. *Olympique* -> /ole~pIk/,
  *Bayonnais* -> /bajonE/, *Constantin* -> /ko~sta~tE/).
* **Post-(k-drop) stress** -- a word whose leading `k` is dropped by the
  cross-word geminate collapse can change accentual group membership.

See [accuracy.md](accuracy.md) for the methodology shared with the Southern
figures, and [reverse-engineering.md](reverse-engineering.md) for how the
Iparrahotsa oracle was captured.
