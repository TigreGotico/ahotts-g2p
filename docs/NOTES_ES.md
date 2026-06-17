# AhoTTS Spanish (es) phonemizer port — notes

Pure-Python, version-aware port of the AhoTTS **Spanish** linguistic engine.
Entry point: `es_phonemizer.phonemize_es(text, version="v1"|"v2"|"v3")` →
final single-char IPA training string (the same representation the StyleTTS2
model trains on).

This is a **source-first** port: every rule is a faithful reimplementation of
the AhoTTS C++ source (`pyAhoTTS/src/es_*.cpp` for V1;
`styletts2-eu-export/upstream-AhoTTS/libhtts/src/es_*.cpp` for V2/V3). Behaviours
that live only in the compiled binaries (the normalizer driver / speller /
`isPronun` heuristic / modulo1y2 wrapper are NOT in the public C checkout) were
reverse-engineered by probing the binaries deterministically and porting the
**mechanism** (not curated word lists). Each is cited below.

## Headline result (held-out es Wikipedia prose, 179 sentences, `corpus_es.txt`)

| version | word-parity vs binary | exact-line |
|---------|-----------------------|------------|
| v1 (pyAhoTTS libhtts)        | **100.00 %** | 179/179 = 100 % |
| v2 (aholab Dec-2025 libhtts) | **100.00 %** | 179/179 = 100 % |
| v3 (arrandi modulo1y2)       | **100.00 %** | 179/179 = 100 % |

Re-verified on 25 fresh held-out sentences (not in the corpus): V1 and V3 both
**100 %** word and line; V2 **100 %** except a single synthetic all-caps acronym
(see the residual ledger — it does not occur in running prose).

`validate_es.py` (`--version v1|v2|v3|all`, `--show N`, `--csv FILE`, `--live`)
scores the port and dumps a per-word mismatch CSV; with the current port the CSV
is empty for the corpus.

## Source → rule map

| AhoTTS C++ source | port function |
|-------------------|---------------|
| `es_phtr.cpp` `pausegr_ch2ph` (grapheme→phoneme) | `_g2p_group` |
| `es_phtr.cpp` `iu2jw` (diphthong glides) | `_apply_glides` |
| `es_syl.cpp` `word_syllab` (syllabification) | `_syllabify` |
| `es_uti.cpp` `phIsVowel`/`phIsValidCC`/`phIsDiptongo`/`phIsTriptongo`/`syllable_vowel` | `_is_vowel`/`_is_valid_cc`/`_is_diphthong`/`_is_triphthong`/`_syllable_vowel` |
| `es_stre.cpp` `word_stress`/`syllable_stress` (regular stress + atonic lists) | `_word_stress`/`_stress_syllable` |
| `es_w2ph.cpp` `utt_w2phtr` (pipeline: ch2ph → syllab → iu2jw → stress) | `_group_to_singlechar` |
| `es_numexp.cpp` `expnum`/`upTo99`/`upTo999`/`es_get1E3n` (cardinals) | `expnum`/`_upto99`/`_upto999`/`_get1e3n` |
| `es_romanhilvl.cpp` `expRoman` (Roman → ordinals ≤999, cardinal+mil above) | `_roman_ordinal_words` |
| `es_numhilvl` thousands `.` / decimal `,` (`N,M` → "N coma M") | `_merge_thousands` |
| `es_speller.cpp` `spellCell`/`isPronun`, `es_getchexp` letter-name table | `_spell_word`/`_is_pronounceable`/`_LETTER_NAME` |
| `es_pow1.cpp` / `symbolexp` superscript `²` → "al cuadrado" | superscript handling in `phonemize_es` |
| `phone.c` `phone_tosampa`, `phone.h` `PH_*`, `es_lingp.hpp` `PHES_*` | `PHES` |
| `es_hdic.cpp` HDIC reader (exp field) | `_load_lexicon` |
| arrandi `eu_phonemizer.getPhonemes` (V3 word/group re-interleave) | `_v3_interleave` |
| arrandi SAMPA→IPA→single-char | `SAMPA_TO_IPA` / `MULTI` |

## What was root-caused to reach 100 %

The previous pass left ~1.5 % (V1/V2) and ~3 % (V3) as "irreducible". Every one
of those was actually a portable mechanism; the divergences fell into these
patterns, each fixed at source-faithful level:

### 1. es_speller — no-vowel tokens and unpronounceable acronyms (`km²`, `i-spn-ya`, `CERN`)
The binary's normalizer (`es_speller.cpp spellCell` via `es_getchexp`) **spells
a token letter-by-letter** when it is not pronounceable. Two triggers, both
ported from the observed deterministic behaviour:
* **No vowel** → spell (`km` → "ka eme", `spn` → "ese pe ene", `pdf` → "pe de
  efe"). `y` counts as a vowel for this test (`kyk` reads as a word).
* **All-uppercase acronym not syllabifiable as Spanish** → spell (`CERN` → "ce e
  erre ene", `DNI` → "de ene i", `ADN`, `FBI`, `BBC`, `ATP`, `ABC`, …) while a
  *pronounceable* acronym is read (`OTAN`, `NASA`, `OVNI`, `PSOE`, `ONU`, `UE`).
  `_is_pronounceable` is a maximal-onset syllabifier over the raw letters using
  the engine's onset (`pl/pr/.../ps/pn/gn`) and coda inventory; verified against
  the binary on a battery of real and synthetic acronyms.
The letter-name table (`_LETTER_NAME`) was read off the binary char-by-char
(`r` → "erre", `w` → "uve doble", `x` → "equis", `y` → "i", …) and is then
phonemized by the same g2p as any word, so it carries no hand-tuned phones.

### 2. es_pow1 / symbolexp superscript `²` → "al cuadrado"
A trailing `²` expands to the words "al cuadrado" (`km²` → "ka eme al cuadrado",
`a²` → "a al cuadrado"). `³`/`¹` are silently dropped by the binary, so they are
dropped here too. A `²`-suffixed token **bypasses the unit lexicon** (`m²` →
"eme al cuadrado", NOT "metro …"; `g²` → "ge …" not "gramo"); the port tags the
letter-part so the lexicon is skipped for it.

### 3. Word-final cluster simplification (`rock` → `rOk`)
The compiled binary reduces a **word-final** geminate / stop+stop cluster to one
consonant (`rock` → rOk, `act` → ak, `att`/`amm`/`ann` → at/an, `pizza`…), while
keeping the cluster medially (`rocka` → rokka, `atta` → atta) and never
collapsing a final `ss` (`ass`/`boss`/`less`). Not present in the public
`es_phtr.cpp`; ported as the algorithm in `_simplify_final_cluster` (drop the
last consonant when it is a stop and the previous phone is the same consonant or
another stop; any non-/s/ final geminate also collapses). Applies to all three
versions (V3's modulo1y2 also gives `rock` → rok).

### 4. V2 has no dictionary, and reverts glides in output
* The Dec-2025 `libhtts.so` **cannot load any HDIC database** (it warns "Can't
  use HDic database 'hdic.dic'"), so V2 applies **no es_dicc respelling** — every
  word is pure g2p (`jazz` → xAθ via the `zz` final-geminate collapse, not the
  "yas" respelling; `beethoven` → beetOβen). Modelled by `lexicon: False` for V2.
* V2 still runs `iu2jw` (so stress lands on the same nucleus as V1 — `rousseau`
  is aguda `rousseAu`, matching V1's `rowsseAw`) but **renders the glide back to
  the full i/u** in its phone output (`veinticinco` → …einti… not …ejnti…). The
  port always glides (for stress) and reverts `j/w` → `i/u` in the output stage
  for glides-off versions. This is what makes V2 ≠ "glides-off engine": the
  earlier model mis-stressed `rousseau` → `roussEau`.

### 5. V3 atonic haber monosyllables (`he`/`has`/`ha`/`han`)
modulo1y2 reads the monosyllabic forms of *haber* as atonic (`ha` → a, `han` →
an, `he` → e, `has` → as) while V1/V2 (whose `es_stre.cpp` atonic list lacks
them) stress them (`A`/`An`/…). Polysyllabic haber forms (`hemos`, `había`) stay
stressed in V3 too, so this is the regular monosyllable-atonic mechanism with an
extended word set (`_ATONA_MONO_V3`), verified mid-phrase against the binary.

### 6. V3 getPhonemes word/group re-interleave (the bulk of the old 3 % gap)
The big V3 divergences — a `,` appearing inside a long spelled number
(`tɾesθjEntos , setEnta`), trailing words dropped at line end — are NOT the
phonemes (those match per word). They are the arrandi `getPhonemes` wrapper
(captured by the `_oracles_es.V3` oracle): the binary emits one phoneme group
per *expanded* word (numbers/units expand to several), but the wrapper consumes
**one group per ORIGINAL source token in order**, emitting `string.punctuation`
chars as-is and padding/​dropping when the counts disagree. `_v3_interleave`
reproduces this exactly: tokenize the original line, walk it consuming the
ordered group list, drop leftover groups. This is a faithful reproduction of the
wrapper's count-mismatch behaviour, not output-matching.

### 7. V3 hyphenated compounds (`i-spn-ya`, `Al-Ándalus`)
modulo1y2 keeps a hyphenated compound in one phrase and (a) emits a no-vowel
sub-part **literally** (`i-spn-ya` → `'i | spn | ʝa`, "spn" passed through raw,
NOT spelled), and (b) a monosyllabic atonic sub-part that is not the last part
stays unstressed (`Al-Ándalus` → "al ándalus", not "Al"). The port detects
hyphen-adjacency (`hyphenated` / `hyphen_nonfinal`): under V3 a hyphenated
no-vowel part is emitted literally, and a hyphen-non-final part is treated as
not phrase-final for stress.

## Established g2p facts (from the source, unchanged)

* `es_phtr.cpp` `#define` is `xSIN_APROX` → approximants live: `b/d/g` →
  `B/D/G` (β/ð/ɣ) in vocalic/liquid contexts; word-initial / post-nasal keep the
  stop. `phtkatamotz = 0` → Llisterri-Mariño r rule (word-initial r, r after
  l/n/s, and rr → trill; intervocalic r → tap). `c+e/i` → θ; `c+h` → tʃ;
  `z` → θ; `x` interior → k s, initial → s; `qu/gu + e/i` drop the u; `j`/`ge`/`gi`
  → x; silent `h` (except word-initial `hie-` → ʝ); `n` → m before b/m/p/v/f;
  `ll` → ʎ, `ñ` → ɲ, `y`+vowel → ʝ else i, word-initial `w`+vowel → ɣ/g + u.
* **iu2jw ordering**: runs after syllabification, mutates in place, and
  `phIsVowel` is false for an already-written j/w — so in a weak-weak diphthong
  only the first weak vowel glides (`ciudad` → θ j u ð…, `fui` → f w 'i).
* **Stress** is dictionary-free, computed from the surface phone string + the
  hardcoded atonic lists (monosyllable→aguda unless atonic-and-not-phrase-final;
  the polysyllabic preposition/conjunction list and possessives; `[aeo]i`→aguda;
  `[nkp]s`→aguda; vowel/n/s→llana; final m-from-n→llana; else aguda).

## Divergence ledger — residuals

After the above, the corpus and the 25-sentence held-out set are exact for all
three versions. One residual remains, on **synthetic input only** (never occurs
in the corpus or any real-prose held-out set):

* **V2 all-caps acronym `isPronun` onset table** (e.g. `DNI`). V1 (with the
  dict) and V3 spell `DNI` → "de ene i"; the dict-less V2 reads it as a word
  `dnI` because its engine `isPronun` accepts `dn/pn/tn/kn/dr/ds…` (stop+sonorant)
  as a syllable onset, while still spelling `gn/bn/dm/fn`-initial acronyms
  (`GNI`/`BNI`/`DMI`/`FNI`) and `rn`-final ones (`CERN`). **Root cause:** a
  V2-specific, buggier `isPronun` onset inventory that lives only in the
  compiled `libhtts.so` (the C source for the speller/​isPronun driver is not in
  the public checkout). **Category 4/5** — a faithfully-attributable
  deterministic binary heuristic, kept un-ported because it (i) affects only
  synthetic all-uppercase non-Roman acronyms, of which there are **zero** in
  running Spanish prose (the corpus's only all-caps tokens are Roman numerals),
  and (ii) reproducing it would mean hard-coding V2's specific buggy onset table
  rather than a defensible linguistic rule. Source line / dict entry that would
  prove the exact table is unavailable (driver not in the checkout); the
  behaviour is documented here from direct binary probing.

## es_dicc lexicon

Spanish g2p/stress need no dictionary. The bundled `es_dicc.dic` contributes
only its **expansion** field — foreign-word/proper-name respelling (`jazz` →
"yas", `beethoven` → "betoven") and abbreviation expansion — applied as a pre-g2p
substitution (`_load_lexicon`). V1 and V3 load it; V2's `.so` cannot (residual 4
above), so V2 sets `lexicon: False`.

## Files

* `es_phonemizer.py` — the port (`phonemize_es`). stdlib only, no subprocess.
* `validate_es.py` — scores the port vs `oracle_dump_es.json`; `--csv` dumps the
  per-word mismatch table (`version, src_word, port, oracle, sentence`).
* `_oracles_es.py` — the three es oracles (V1 pyAhoTTS libhtts, V2 Dec-2025
  libhtts.so, V3 modulo1y2 + getPhonemes re-implementation). Not shipped.
* `dump_oracles_es.py` — regenerates `oracle_dump_es.json` from the binaries.
* `corpus_es.txt` — 179 held-out Spanish Wikipedia sentences (running prose).
* `oracle_dump_es.json` — cached ground truth (so the port needs no binaries).
* `decode_hdic.py` — standalone HDIC reader (used to inspect es_dicc).
</content>
</invoke>
