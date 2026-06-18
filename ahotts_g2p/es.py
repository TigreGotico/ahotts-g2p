"""Spanish (es) grapheme-to-phoneme engine.

    phonemize_es(text, version="v1" | "v3") -> str

``version`` is the internal engine-config key; the public API exposes these as
``classic`` (-> ``v1``) and ``modern`` (-> ``v3``).

The full Spanish linguistic pipeline reproducing the final single-char training
representation of the AhoTTS generations:

  v1  Full engine: grapheme-to-phoneme with coarticulated approximants
      (b/d/g -> B/D/G between vowels), the Llisterri-Mariño r rule,
      syllabification, diphthong glides (i/u -> j/w next to a vowel in the same
      syllable), and the regular Spanish lexical-stress rule (penultimate for
      words ending in vowel/n/s, final otherwise, with a written-accent
      override and an atonic function-word list).
  v3  Same engine + glides on (= v1), but the modulo1y2 wrapper (a) emits
      punctuation as separate tokens, (b) re-interleaves one phoneme group per
      original source token (so number/unit expansions shift punctuation and
      drop trailing words), and (c) treats the haber monosyllables
      he/has/ha/han as atonic.

The pipeline mirrors the AhoTTS C++ Spanish engine (``es_phtr.cpp``
pausegr_ch2ph / iu2jw, ``es_syl.cpp`` word_syllab, ``es_uti.cpp`` helpers,
``es_stre.cpp`` word_stress, ``es_numexp.cpp`` number expansion, ``phone.c``
SAMPA table, ``es_lingp.hpp`` aliases, ``hts.cpp`` phone_tosampa).  AhoTTS /
Aholab (UPV/EHU) are the algorithm source.

Unlike Basque, Spanish stress is computed entirely from the surface phone
string plus a hardcoded atonic-word list -- it needs no dictionary lookup.  The
bundled es_dicc only matters for normalisation/abbreviations (not modelled
here); g2p and stress are dictionary-free.

Stdlib only; no subprocess, no C build.
"""
import os
import re
import struct
import unicodedata as _unicodedata
from collections import OrderedDict

# ==========================================================================
# Phone tables  (es_lingp.hpp PHES_* -> phone.h PH_* internal char -> SAMPA)
# ==========================================================================
# es_lingp.hpp maps each Spanish phone name to a PH_* code; phone.h gives the
# internal single char; phone.c phone_tosampa gives the SAMPA string.
# We fold PHES name -> SAMPA directly (the internal char is just an index).
PHES = {
    'a': 'a', 'e': 'e', 'i': 'i', 'o': 'o', 'u': 'u',
    'iaprox': 'j', 'uaprox': 'w',
    'b': 'b', 'baprox': 'B',
    'd': 'd', 'daprox': 'D',
    'g': 'g', 'gaprox': 'G',
    'p': 'p', 't': 't', 'k': 'k',
    'm': 'm', 'n': 'n', 'ntilde': 'J',
    'ch': 'tS',                 # PHES_ch -> PH_tS -> "tS"
    'f': 'f',
    'z': 'T',                   # PHES_z -> PH_T -> "T" (Castilian theta)
    's': 's',
    'y': 'jj',                  # PHES_y -> PH_jj -> "jj"
    'j': 'x',                   # PHES_j -> PH_x -> "x"
    'l': 'l', 'll': 'L',
    'r': 'r', 'rr': 'rr',       # PHES_r -> "r" (tap), PHES_rr -> "rr" (trill)
}

# SAMPA -> IPA + multichar->singlechar collapse (shared with eu; Spanish is a
# subset).  Authoritative source: arrandi eu_phonemizer / pyahotts SAMPA_TO_IPA.
SAMPA_TO_IPA = OrderedDict([
    ("p", "p"), ("b", "b"), ("t", "t"), ("c", "c"), ("d", "d"),
    ("k", "k"), ("g", "ɡ"), ("tS", "tʃ"), ("ts", "ts"), ("ts`", "tʂ"),
    ("gj", "ɟ"), ("jj", "ʝ"), ("f", "f"), ("B", "β"), ("T", "θ"),
    ("D", "ð"), ("s", "s"), ("s`", "ʂ"), ("S", "ʃ"), ("x", "x"),
    ("G", "ɣ"), ("m", "m"), ("n", "n"), ("J", "ɲ"), ("l", "l"),
    ("L", "ʎ"), ("r", "ɾ"), ("rr", "r"), ("j", "j"), ("w", "w"),
    ("i", "i"), ("e", "e"), ("a", "a"), ("o", "o"), ("u", "u"),
    ("y", "y"), ("Z", "ʒ"), ("h", "h"), ("ph", "pʰ"), ("kh", "kʰ"),
    ("th", "tʰ"),
])
MULTI = {
    "tʃ": "C", "ts": "V", "tʂ": "P",
    "'i": "I", "'e": "E", "'a": "A", "'o": "O", "'u": "U",
    "pʰ": "H", "kʰ": "K", "tʰ": "T",
}

# Character classes from es_phtr.cpp.  Accented vowels carry written stress.
VOWELS_PLAIN = "aeiou"
ACCENTED = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u'}
DIERESIS = {'ü': 'u'}                 # CS_uuml -> u (no stress)
EIETIT = set("ei") | {'é', 'í'}       # eietit = "ei" + e-tilde + i-tilde
NM = set("nm")                        # before b/g: keep stop (non-approx)
NML = set("nml")                      # before d: keep stop d
# vow set used in 'p'(ph) and 'w' rules: aeiou + all accented + dieresis
VOW = set("aeiou") | set("áéíóú") | {'ü'}


# ==========================================================================
# Engine configuration table  (the source is one engine; versions = config)
# ==========================================================================
#   glides      : iu2jw renders weak diphthong vowels as j/w (True = V1, V3)
#                 vs leaving them as full i/u (False = V2's libhtts output).
#                 Syllabification ALWAYS treats them as one syllable.
#   keep_punct  : modulo1y2/eu_phonemizer emits punctuation tokens (V3).
# lexicon    : apply the es_dicc exp respelling (jazz->yas, beethoven->betoven,
#              etc.).  The V2 (aholab Dec-2025) libhtts.so cannot load any HDIC
#              database (it warns "Can't use HDic database 'hdic.dic'") and so
#              applies NO lexicon -- every word is pure g2p (jazz -> xAθ,
#              beethoven -> beetOβen).  V1 and V3 do load the dict.
# The es_speller (no-vowel + unpronounceable-acronym spelling, "²" superscript)
# is engine-level and applies to all three versions.
_CONFIG = {
    "v1": {"glides": True, "keep_punct": False, "lexicon": True},
    "v3": {"glides": True, "keep_punct": True,  "lexicon": True},
}


# ==========================================================================
# es_dicc lexicon  (es_hdic.cpp format).  Unlike Basque, Spanish g2p/stress are
# dictionary-free; the dictionary's only contribution to the transcription is
# its EXPANSION field, which respells foreign words / proper names to Spanish
# phonotactics ("jazz" -> "yas", "beethoven" -> "betoven") and expands
# abbreviations ("etc." -> "etcétera").  Both are applied as a pre-g2p word
# substitution, exactly as the AhoTTS normalizer does.
# ==========================================================================
_HDIC_SIG = b"Aholab aHoTTS HDIC Database\x1A"
_HERE = os.path.dirname(os.path.abspath(__file__))
_ES_DICT_CANDIDATES = [
    os.path.join(_HERE, "es_dicc.dic"),
    "/home/miro/AgentWorkspaces/ml/pyAhoTTS/pyahotts/data_tts/dicts/es_dicc.dic",
]
_LEXICON = None


def _hdic_blocks(data):
    off = len(_HDIC_SIG) + 1
    if data[:len(_HDIC_SIG)] != _HDIC_SIG:
        raise ValueError("not an HDIC database")
    off += 2 + 4                                       # type[2] + version[4]
    blocks = []
    for has_exp in (True, False, True, False):
        base, n = struct.unpack_from('<II', data, off)
        off += 8
        slen = struct.unpack_from('<H', data, off)[0]
        off += 2
        exlen = 0
        if has_exp:
            exlen = struct.unpack_from('<H', data, off)[0]
            off += 2
        blen = (2 + slen + 4 + 2 + exlen) if has_exp else (2 + slen + 4)
        blocks.append((base, n, slen, exlen, blen, has_exp))
    return blocks


def _load_lexicon():
    """Return {lowercased_word: [respelled tokens]} from the es_dicc exp field.
    Keeps the first expansion seen per word."""
    lex = {}
    path = next((p for p in _ES_DICT_CANDIDATES if os.path.exists(p)), None)
    if not path:
        return lex
    try:
        data = open(path, 'rb').read()
        for (base, n, slen, exlen, blen, has_exp) in _hdic_blocks(data):
            if not has_exp:
                continue
            for k in range(n):
                rec = base + blen * k
                wlen = struct.unpack_from('<H', data, rec)[0]
                try:
                    w = data[rec + 2:rec + 2 + wlen].decode('latin-1')
                except UnicodeDecodeError:
                    continue
                ep = rec + 2 + slen + 4
                elen = struct.unpack_from('<H', data, ep)[0]
                try:
                    exp = data[ep + 2:ep + 2 + elen].decode('latin-1').strip()
                except UnicodeDecodeError:
                    continue
                if not exp:
                    continue
                key = w.lower()
                if key not in lex:
                    lex[key] = exp.split()
    except (OSError, struct.error, ValueError):
        return {}
    return lex


def _lexicon():
    global _LEXICON
    if _LEXICON is None:
        _LEXICON = _load_lexicon()
    return _LEXICON


# ==========================================================================
# Grapheme -> phoneme  (es_phtr.cpp pausegr_ch2ph)
# ==========================================================================
# Faithful port.  Works across a whole pause group (so word-boundary context
# like n+b -> m sees the following word's first char), but the C uses
# charIsLast(URANGE_WORD) / charIsFirst(URANGE_WORD) for the within-word rules
# (ch, c+h, ll, l, p+h, q+u, r, x, y).  We therefore track per-char word index
# and first/last-in-word flags.
#
# Build:  s[] flat char list of the pause group; word_first/word_last per char.
# Emit:   one phone per output cell, tagging stress (from accented vowels) and
#         the original word index + source char.  'h' is silent (deleted).
#
# Note: #define is `xSIN_APROX`, NOT `SIN_APROX` -> approximants ARE produced
# (b/d/g -> B/D/G in the relevant contexts).  phtkatamotz = 0 (default ctor) so
# the Llisterri-Mariño r rule branch is used (not the katamotz weak-r branch).

def _g2p_group(words, glides=True):
    """words: list of lowercased word strings (accents preserved).
    Returns (phones, stress, word_of_phone) where stress[i] is True if that
    phone carries USTRESS_TEXT (written accent).  Glides are applied later by
    _iu2jw; here i/u always emit the plain vowel phone."""
    # flatten
    s, cw, wf, wl = [], [], [], []
    for wi, w in enumerate(words):
        for j, ch in enumerate(w):
            s.append(ch)
            cw.append(wi)
            wf.append(j == 0)
            wl.append(j == len(w) - 1)
    n = len(s)
    out, out_stress, out_word = [], [], []
    i = 0

    def at(idx):
        return s[idx] if 0 <= idx < n else '\x00'

    def emit(ph, stress=False):
        out.append(ph)
        out_stress.append(stress)
        out_word.append(cw[i])

    while i < n:
        ch = s[i]
        ch2 = at(i + 1)            # next char in pause group (0 if none)
        wlast = wl[i]              # last char of its word
        wfirst = wf[i]            # first char of its word
        # char-prev in PAUSE range (whole group, not word)
        ch3 = at(i - 1) if i > 0 else '\x00'

        if ch == 'a':
            emit(PHES['a'])
        elif ch == 'e':
            emit(PHES['e'])
        elif ch == 'i':
            emit(PHES['i'])
        elif ch == 'o':
            emit(PHES['o'])
        elif ch == 'u':
            emit(PHES['u'])
        elif ch in ACCENTED:
            emit(PHES[ACCENTED[ch]], stress=True)
        elif ch in DIERESIS:
            emit(PHES['u'])
        elif ch in ('v', 'b'):
            if wfirst and i == 0:
                # charIsFirst(PAUSE): first char of pause group -> b
                emit(PHES['b'])
            elif (not ch3) or ch3 in NM:
                emit(PHES['b'])
            else:
                emit(PHES['baprox'])
        elif ch == 'c':
            if ch2 and ch2 in EIETIT:
                emit(PHES['z'])                       # ce, ci -> theta
            elif (not wlast) and ch2 == 'h':
                emit(PHES['ch'])                      # ch -> tS, skip the h
                i += 1
            else:
                emit(PHES['k'])
        elif ch == 'd':
            if (i == 0) or (not ch3) or ch3 in NML:
                emit(PHES['d'])
            else:
                emit(PHES['daprox'])
        elif ch == 'f':
            emit(PHES['f'])
        elif ch == 'g':
            skip_u = False
            if ch2 and ch2 in EIETIT:
                emit(PHES['j'])                       # ge, gi -> x
                i += 1
                continue
            if ch2 == 'u':
                ch4 = at(i + 2)
                if ch4 and ch4 in EIETIT:
                    skip_u = True                    # gue/gui -> ge/gi (drop u)
            if (i == 0) or (not ch3) or ch3 in NM:
                emit(PHES['g'])
            else:
                emit(PHES['gaprox'])
            if skip_u:
                i += 1                                # consume the silent u
        elif ch == 'h':
            # h+ie at word start: h deleted, i -> y, skip the i.
            ch4 = at(i + 2)
            if wfirst and ch2 == 'i' and ch4 == 'e':
                emit(PHES['y'])                       # i -> y (replaces hi)
                i += 2                                # consume h's slot + i
                continue
            # otherwise h is silent (deleted): emit nothing
            pass
        elif ch == 'j':
            emit(PHES['j'])
        elif ch == 'k':
            emit(PHES['k'])
        elif ch == 'l':
            if (not wlast) and ch2 == 'l':
                emit(PHES['ll'])                      # ll
                i += 1
            else:
                emit(PHES['l'])
        elif ch == 'm':
            emit(PHES['m'])
        elif ch == 'n':
            if ch2 in ('b', 'm', 'p', 'v', 'f'):
                emit(PHES['m'])                       # n -> m before b/m/p/v/f
            else:
                emit(PHES['n'])
        elif ch == 'ñ':
            emit(PHES['ntilde'])
        elif ch == 'p':
            if (not wlast) and ch2 == 'h':
                ch4 = at(i + 2)
                if (not ch4) or ch4 in VOW or ch4 == 'y':
                    emit(PHES['f'])                   # ph -> f (h dropped later)
                    # NOTE: source does NOT skip the h here; the h is silent in
                    # its own iteration.  But emitting f then hitting h (silent)
                    # is correct.
                else:
                    emit(PHES['p'])
            else:
                emit(PHES['p'])
        elif ch == 'q':
            if ch2 == 'u':
                ch4 = at(i + 2)
                if not (ch4 == 'a' or not ch4):
                    i += 1                            # qu -> k, drop u
            emit(PHES['k'])
        elif ch == 'r':
            # Llisterri-Mariño rule (phtkatamotz = 0).
            if wfirst:
                emit(PHES['rr'])                      # word-initial r -> trill
            elif (not wlast) and ch3 in ('l', 'n', 's'):
                emit(PHES['rr'])                      # l/n/s + r -> trill
            elif (not wlast) and ch2 == 'r':
                emit(PHES['rr'])                      # rr -> trill, skip one r
                i += 1
            else:
                emit(PHES['r'])                       # else tap
        elif ch == 's':
            emit(PHES['s'])
        elif ch == 't':
            emit(PHES['t'])
        elif ch == 'w':
            if wfirst and (not wlast) and ch2 in VOW:
                # word-initial w + vowel -> g(aprox) + u
                if (i == 0) or (not ch3) or ch3 in NM:
                    emit(PHES['g'])
                else:
                    emit(PHES['gaprox'])
                # add a [u] cell after
                out.append(PHES['u'])
                out_stress.append(False)
                out_word.append(cw[i])
            else:
                emit(PHES['u'])
        elif ch == 'x':
            if not wfirst:
                emit(PHES['k'])                       # interior x -> k s
                out.append(PHES['s'])
                out_stress.append(False)
                out_word.append(cw[i])
            else:
                emit(PHES['s'])                       # word-initial x -> s
        elif ch == 'y':
            if (not ch2) or (ch2 not in VOW) or wlast:
                emit(PHES['i'])                       # y[C#] -> i
            else:
                emit(PHES['y'])                       # y + vowel -> jj
        elif ch == 'z':
            emit(PHES['z'])
        # default: unknown char -> skip
        i += 1

    return out, out_stress, out_word


# ==========================================================================
# Utility predicates  (es_uti.cpp)
# ==========================================================================
def _is_vowel(ph):
    return ph in (PHES['a'], PHES['e'], PHES['i'], PHES['o'], PHES['u'])
    # NOTE: phIsVowel only counts a/e/i/o/u (NOT the j/w approximants);
    # iu2jw runs AFTER syllabification, so at syllab time i/u are still i/u.


# CC groups valid in onset (es_uti.cpp phIsValidCC, the INAKI version with
# approximants).  l-set and r-set; ph2 is the liquid (l or r).
_CC_L = {PHES['baprox'], PHES['b'], PHES['f'], PHES['gaprox'], PHES['g'],
         PHES['k'], PHES['p'], PHES['t']}
_CC_R = {PHES['baprox'], PHES['b'], PHES['daprox'], PHES['d'], PHES['f'],
         PHES['gaprox'], PHES['g'], PHES['k'], PHES['p'], PHES['t']}


def _is_valid_cc(ph1, ph2):
    if ph2 == PHES['l']:
        return ph1 in _CC_L
    if ph2 == PHES['r']:                  # only the tap r forms onsets, not rr
        return ph1 in _CC_R
    return False


def _is_diphthong(ph1, ph2, acc1, acc2):
    """es_uti.cpp phIsDiptongo.  ph1,ph2 are PHES vowels; acc = stressed bool.
    df / fd / dd unless the weak member that decides is stressed."""
    iu1 = ph1 in (PHES['i'], PHES['u'])
    iu2 = ph2 in (PHES['i'], PHES['u'])
    if iu1 and not iu2 and not acc1:
        return True
    if not iu1 and iu2 and not acc2:
        return True
    if iu1 and iu2 and not acc1:
        return True
    return False


def _is_triphthong(ph1, ph2, ph3, acc1, acc3):
    iu1 = ph1 in (PHES['i'], PHES['u'])
    iu2 = ph2 in (PHES['i'], PHES['u'])
    iu3 = ph3 in (PHES['i'], PHES['u'])
    if iu1 and not iu2 and iu3 and not acc1 and not acc3:
        return True
    return False


# ==========================================================================
# Syllabification  (es_syl.cpp word_syllab)
# ==========================================================================
# Faithful port of the C, which walks vowels left-to-right within a word and
# sets syllable boundaries.  Operates on one word's phone list.  Returns a
# list of syllables, each a list of phone indices (into the word-local list).
def _syllabify(phones, stress):
    n = len(phones)
    if n == 0:
        return []
    boundary = [False] * n
    # cur_start: index of the first phone of the syllable currently being built
    # (the C uses SPREV = phonePrev within URANGE_SYLLABLE, i.e. "stop at the
    # last boundary we set"); we model the syllable start explicitly.
    cur_start = 0

    def sprev(idx):
        """previous phone index within the current syllable, or -1."""
        return idx - 1 if (idx - 1) >= cur_start else -1

    i = 0
    while i < n:
        ph = phones[i]
        if not _is_vowel(ph):
            i += 1
            continue
        i2 = sprev(i)
        if i2 < 0:
            # #V  -> start syllable here
            boundary[i] = True
            cur_start = i
            i += 1
            continue
        ph2 = phones[i2]
        i3 = i2 - 1 if (i2 - 1) >= cur_start else -1
        if not _is_vowel(ph2):                          # CV
            if i3 < 0:
                boundary[i2] = True                    # #CV -> #-CV
                cur_start = i2
                i += 1
                continue
            ph3 = phones[i3]
            if _is_vowel(ph3):
                boundary[i2] = True                    # VCV -> V-CV
                cur_start = i2
                i += 1
                continue
            if _is_valid_cc(ph3, ph2):
                boundary[i3] = True                    # CCV -> -CCV
                cur_start = i3
                i += 1
                continue
            boundary[i2] = True                        # CCV -> C-CV
            cur_start = i2
            i += 1
            continue
        else:                                          # VV
            if i3 >= 0:
                ph3 = phones[i3]
                if _is_vowel(ph3):                      # VVV
                    if _is_triphthong(ph3, ph2, ph, stress[i3], stress[i]):
                        i3b = i3 - 1 if (i3 - 1) >= cur_start else -1
                        if i3b < 0:
                            i += 1                      # #VVV is triphthong
                            continue
                        if not _is_vowel(phones[i3b]):
                            i += 1                      # CVVV is triphthong
                            continue
                        # VVVV -> fall through, break the triphthong
                    boundary[i] = True                 # VVV -> VV-V
                    cur_start = i
                    i += 1
                    continue
            # #VV or CVV: check diphthong
            if _is_diphthong(ph2, ph, stress[i2], stress[i]):
                i += 1                                  # VV is diphthong
                continue
            boundary[i] = True                         # VV -> V-V
            cur_start = i
            i += 1
            continue

    # nota2: if the word does not start with a syllable boundary, move the
    # first boundary to the start (glue the leading consonant cluster onto the
    # first syllable).
    if n and not boundary[0]:
        for k in range(1, n):
            if boundary[k]:
                boundary[k] = False
                break
        boundary[0] = True

    # build syllable groups
    syls, cur = [], []
    for k in range(n):
        if boundary[k] and cur:
            syls.append(cur)
            cur = []
        cur.append(k)
    if cur:
        syls.append(cur)
    return syls


def _syllable_vowel(phones, stress, syl):
    """es_uti.cpp syllable_vowel: strong vowel (aeo), else the stressed weak,
    else the first weak found.  Returns index into the word-local list."""
    v = None
    for idx in syl:
        p = phones[idx]
        if p in (PHES['a'], PHES['e'], PHES['o']):
            return idx
        if p in (PHES['i'], PHES['u']):
            if v is None or not stress[v]:
                v = idx
    return v


# ==========================================================================
# iu2jw  (es_phtr.cpp iu2jw)  -- run after syllabification
# ==========================================================================
def _apply_glides(phones, stress, syls):
    """es_phtr.cpp iu2jw: convert an unstressed i/u to j/w when it has a plain
    vowel neighbour within the SAME syllable.  CRUCIAL: the C iterates the phone
    list in order and mutates in place; phIsVowel returns FALSE for the j/w it
    has already written.  So in a weak-weak diphthong (iu/ui) only the FIRST
    weak vowel glides -- once it becomes j/w, the SECOND no longer sees a vowel
    to that side (e.g. ciudad -> T j u D ..., not T j w D ...)."""
    out = list(phones)
    plain_vowels = (PHES['a'], PHES['e'], PHES['i'], PHES['o'], PHES['u'])
    for syl in syls:
        for k, p in enumerate(syl):
            ph = out[p]                        # read the (possibly mutated) list
            if ph in (PHES['i'], PHES['u']) and not stress[p]:
                left = out[syl[k - 1]] if k - 1 >= 0 else None
                right = out[syl[k + 1]] if k + 1 < len(syl) else None
                lv = left in plain_vowels if left else False
                rv = right in plain_vowels if right else False
                if lv or rv:
                    out[p] = PHES['iaprox'] if ph == PHES['i'] \
                        else PHES['uaprox']
    return out


# ==========================================================================
# Stress  (es_stre.cpp word_stress)
# ==========================================================================
# Atonic monosyllables: do NOT get stress unless they are the last word of the
# pause group (es_stre.cpp: the `wordp != wordThis(phoneLast(...,PAUSE))` guard
# means "not the last word").
_ATONA_MONO = {
    "el", "la", "las", "los", "lo",
    "mi", "tu", "su", "mis", "tus", "sus",
    "me", "nos", "te", "os", "le", "les", "se",
    "que", "tan",
    "a", "al", "con", "de", "del", "en", "por", "sin", "tras",
    "y", "e", "ni", "o", "u", "mas", "si", "pues",
}
# Atonic polysyllables (return immediately, no stress) unless last word.
_ATONA_POLY = {
    "donde", "como", "cuando", "cuanto", "quien", "cuyo",
    "ante", "bajo", "contra", "desde", "entre", "hacia",
    "hasta", "para", "sobre", "durante", "mediante",
    "pero", "sino", "aunque",
}
# Possessives: atonic unless last word.
_ATONA_POSS = {
    "nuestro", "nuestra", "nuestros", "nuestras",
    "vuestro", "vuestra", "vuestros", "vuestras",
}
# V3 (modulo1y2) extends the atonic monosyllable list with the monosyllabic
# forms of the auxiliary *haber* (he/has/ha/han).  Verified against the
# modulo1y2 binary: mid-phrase "ha"/"han"/"he"/"has" come out unstressed
# (a/an/e/as) in v3 but stressed (A/An/E/As) in v1/v2 (libhtts es_stre.cpp,
# whose hardcoded atonic list does not contain them).  Polysyllabic haber
# forms (hemos/había/...) stay stressed in v3 too, so this is the regular
# monosyllable-atonic mechanism with an extended word set, not an exception.
_ATONA_MONO_V3 = _ATONA_MONO | {"he", "has", "ha", "han"}


def _word_stress(phones, stress, word, syls, is_last_word, src_chars,
                 atona_mono=_ATONA_MONO):
    """es_stre.cpp word_stress.  Mutates stress[] in place.  `word` is the
    lowercased plain (de-accented) surface word; `src_chars` is the original
    char that produced each phone (for the n->m correction).  Only called when
    the word is not already stressed (no written accent)."""
    if not phones or not syls:
        return
    last_syl = syls[-1]
    last = last_syl[-1]
    p = phones[last]
    nsyl_minus1 = len(syls) - 1           # u.syllablePos(last, WORD): 0-based

    if nsyl_minus1 == 0:                   # monosyllable -> aguda
        if (not is_last_word) and word in atona_mono:
            return
        _stress_syllable(phones, stress, last_syl)
        # fall through to the rest of the C function (it does NOT return after
        # stressing a monosyllable -- but the subsequent rules only re-stress,
        # and for a 1-syllable word syllablePrev == same syllable, so it is
        # idempotent here; we return to avoid double work).
        # Continue to atona checks below mirrors C control flow:
    # atona polysyllables / possessives (these checks run regardless of nsyl,
    # but only matter for polysyllables since monosyllables already returned-ish)
    if (not is_last_word) and word in _ATONA_POLY:
        return
    if (not is_last_word) and word in _ATONA_POSS:
        return
    if nsyl_minus1 == 0:
        return                             # monosyllable handled above

    # second-to-last phone within the last syllable
    p2 = None
    li = last_syl.index(last)
    if li - 1 >= 0:
        p2 = phones[last_syl[li - 1]]

    # [aeo]i ending -> aguda, stress the [aeo]
    if p == PHES['i'] and p2 in (PHES['a'], PHES['e'], PHES['o']):
        stress[last_syl[li - 1]] = True
        return
    # [nkp]s ending -> aguda
    if p == PHES['s'] and p2 in (PHES['n'], PHES['k'], PHES['p']):
        # stress the syllable containing p2 (i2 = phonePrev(last, SYLLABLE))
        _stress_syllable(phones, stress, last_syl)
        return
    # ends in vowel / n / s -> llana (penultimate)
    if _is_vowel(p) or p == PHES['n'] or p == PHES['s']:
        _stress_syllable(phones, stress, syls[-2])
        return
    # n that surfaced as m before p/m/b/f -> still llana
    if p == PHES['m'] and src_chars[last] == 'n':
        _stress_syllable(phones, stress, syls[-2])
        return
    # else aguda (last syllable)
    _stress_syllable(phones, stress, last_syl)


# ==========================================================================
# Word-final cluster simplification (binary-only; not in the public
# es_phtr.cpp).  Verified deterministically against the libhtts binary:
#   rock -> rOk, act -> ak, att -> at, amm/ann -> an  (last consonant dropped)
#   art -> aɾt, alk -> alk, amp -> amp                (sonorant+stop kept)
#   ass/less/boss -> ...ss                            (final ss never collapses)
# and only WORD-FINALLY (rocka -> rokka, atta -> atta keep the geminate).
# Mechanism: at the word end, drop the last consonant phone when it is a stop
# and the preceding phone is the SAME consonant (geminate) or another stop;
# a final geminate of any non-/s/ consonant also collapses.  This is the
# compiled binary's final-cluster cleanup (absent from the public source);
# reproduced here as the algorithm, not a word list.
_STOPS = {PHES['p'], PHES['t'], PHES['k'], PHES['b'], PHES['d'], PHES['g'],
          PHES['baprox'], PHES['daprox'], PHES['gaprox']}
_FINAL_GEMINABLE = {  # consonants whose word-final geminate collapses
    PHES['b'], PHES['baprox'], PHES['d'], PHES['daprox'],
    PHES['g'], PHES['gaprox'], PHES['p'], PHES['t'], PHES['k'],
    PHES['f'], PHES['m'], PHES['n'], PHES['ll'], PHES['rr'],
    PHES['l'], PHES['r'], PHES['z'],
}


def _simplify_final_cluster(local_phones):
    """Return the word-local phone list with a word-final geminate / stop+stop
    cluster reduced (last consonant dropped).  Pure last-position rule."""
    if len(local_phones) < 2:
        return local_phones
    last = local_phones[-1]
    prev = local_phones[-2]
    if last == PHES['s']:                       # final s never collapses
        return local_phones
    drop = False
    if last == prev and last in _FINAL_GEMINABLE:
        drop = True                              # identical geminate (non-s)
    elif last in _STOPS and prev in _STOPS:
        drop = True                              # stop + stop
    if drop:
        return local_phones[:-1]
    return local_phones


def _stress_syllable(phones, stress, syl):
    v = _syllable_vowel(phones, stress, syl)
    if v is not None:
        stress[v] = True


# ==========================================================================
# Number expansion  (es_numexp.cpp)
# ==========================================================================
_FROM10TO29 = [
    "diez", "once", "doce", "trece", "catorce", "quince", "dieciséis",
    "diecisiete", "dieciocho", "diecinueve", "veinte", "veintiuno",
    "veintidós", "veintitrés", "veinticuatro", "veinticinco", "veintiséis",
    "veintisiete", "veintiocho", "veintinueve",
]
_TENS = ["veinti", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta",
         "ochenta", "noventa"]                      # index = num/10 - 2
_HUNDREDS = ["ciento", "doscientos", "trescientos", "cuatrocientos",
             "quinientos", "seiscientos", "setecientos", "ochocientos",
             "novecientos"]
_UNITS = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete",
          "ocho", "nueve"]
_THOUSAND = "mil"
_MILLION, _BILLION = "millones", "billones"
_MILLION_S, _BILLION_S = "millón", "billón"


def _upto99(num, out, primero):
    if num == 0:
        out.append("cero")
        return
    while num:
        if num <= 9:
            out.append(_UNITS[num])
            num = 0
        elif num < 30:
            out.append(_FROM10TO29[num - 10])
            num = 0
        else:
            out.append(_TENS[num // 10 - 2])
            num %= 10
            if num:
                out.append("y")


def _upto999(num, out):
    if num < 100:
        _upto99(num, out, True)
        return
    if num == 100:
        out.append("cien")
        return
    cent = num // 100
    out.append(_HUNDREDS[cent - 1])
    num -= cent * 100
    if num:
        _upto99(num, out, False)


def _get1e3n(numtern, singular):
    if numtern > 5:
        return None
    if numtern == 1:
        return _THOUSAND
    if numtern == 2:
        return _MILLION_S if singular else _MILLION
    if numtern == 3:
        return _THOUSAND
    if numtern == 4:
        return _BILLION_S if singular else _BILLION
    if numtern == 5:
        return _THOUSAND
    return None


def expnum(digits):
    """es_numexp.cpp expnum.  Returns a list of Spanish number words."""
    out = []
    inp = digits
    numceros = 0
    while len(inp) > 1 and inp[0] == '0':
        numceros += 1
        inp = inp[1:]
    out += ["cero"] * numceros
    if len(inp) > 18:
        return out
    L = len(inp)
    resto = L % 3
    numtern = (L - resto) // 3
    numzone = [False] * 6

    if resto:
        terna = int(inp[:resto])
        if terna != 1:
            if terna == 0 and L != 1:
                _upto99(terna, out, True)
            if terna != 0 or (terna == 0 and L == 1):
                _upto999(terna, out)
                g = _get1e3n(numtern, False)
                if g:
                    out.append(g)
        else:
            if numtern == 0:
                _upto99(terna, out, True)
            elif numtern in (1, 3, 5):
                g = _get1e3n(numtern, True)
                if g:
                    out.append(g)
            elif numtern in (2, 4):
                out.append("un")
                g = _get1e3n(numtern, True)
                if g:
                    out.append(g)
        inp = inp[resto:]
        numzone[numtern] = True

    for j in range(numtern):
        terna = int(inp[:3])
        k = numtern - (j + 1)
        if terna != 0:
            if terna != 1:
                _upto999(terna, out)
                g = _get1e3n(k, False)
                if g:
                    out.append(g)
            else:
                if k == 0:
                    _upto99(terna, out, True)
                elif k in (1, 3, 5):
                    g = _get1e3n(k, False)
                    if g:
                        out.append(g)
                elif k == 2:
                    if numzone[3]:
                        _upto99(terna, out, True)
                        g = _get1e3n(k, False)
                        if g:
                            out.append(g)
                    else:
                        g = _get1e3n(k, False)
                        if g:
                            out.append(g)
                        _upto99(terna, out, True)
                elif k == 4:
                    if numzone[5]:
                        _upto99(terna, out, True)
                        g = _get1e3n(k, False)
                        if g:
                            out.append(g)
                    else:
                        g = _get1e3n(k, False)
                        if g:
                            out.append(g)
                        _upto99(terna, out, True)
            numzone[k] = True
        else:
            if k == 2:
                if numzone[3]:
                    out.append(_MILLION)
            elif k == 4:
                if numzone[5]:
                    out.append(_BILLION)
            elif k == 0:
                if terna == 0 and resto == 0 and not numzone[j]:
                    _upto99(terna, out, True)
        inp = inp[3:]
    return out


# ==========================================================================
# Roman numerals (es_romanhilvl.cpp expRoman -- read as ORDINALS up to 999,
# as a cardinal-with-"mil" above 1000).
# ==========================================================================
def _roman_to_int(s):
    if not s or not re.fullmatch(r'[IVXLCDM]+', s):
        return None
    vals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    total = prev = 0
    for ch in reversed(s):
        v = vals[ch]
        if v < prev:
            total -= v
        else:
            total += v
            prev = v
    return total if total > 0 else None


# Ordinal stems (es_romanhilvl.cpp).  The final masculine "o" is appended by
# extendStr; "primer"/"tercer" thus surface as "primero"/"tercero".
_ROMAN_ORD = ["primer", "segund", "tercer", "cuart", "quint", "sext",
              "septim", "octav", "noven", "décim", "undécim", "duodécim"]
_ROMAN_TENS = ["décim", "vigésim", "trigésim", "cuadragésim", "quincuagésim",
               "sexagésim", "septuagésim", "octogésim", "nonagésim"]
_ROMAN_HUND = ["centésim", "ducentésim", "tricentésim", "cuadrigentésim",
               "quingentésim", "sexcentésim", "septingentésim",
               "octingentésim", "noningentésim"]


def _roman_ordinal_words(num):
    """es_romanhilvl.cpp expRoman.  Returns the list of ordinal words for a
    Roman value (1..999); each `extendStr` appends to the current word, each
    `insafter` starts a new word.  Final masculine "o" appended."""
    if num > 999:
        # cardinal with "mil" (inaxio branch).
        r = num % 1000
        thou = num // 1000
        out = []
        if thou != 1:
            _upto999(thou, out)
        out.append("mil")
        if r:
            _upto999(r, out)
        return out
    words = []
    while num:
        if num <= 12:
            words.append(_ROMAN_ORD[num - 1])
            num = 0
        elif num < 100:
            words.append(_ROMAN_TENS[num // 10 - 1])
            num %= 10
            if num:
                words[-1] += "o"            # extendStr masculine, then loop
        else:
            words.append(_ROMAN_HUND[num // 100 - 1])
            num %= 100
            if num:
                words[-1] += "o"
    if words:
        words[-1] += "o"                    # final extendStr masculine
    return words


# ==========================================================================
# Token expansion
# ==========================================================================
_PUNCT = set(".,!?;:")


def _merge_thousands(tokens):
    """A '.' between a number and a 3-digit group is a thousands separator
    (es_numhilvl).  A ',' between two digit groups is a decimal point read as
    "<int> coma <fraction-as-number>"."""
    out = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t.isdigit():
            num = t
            j = i + 1
            while (j + 1 < len(tokens) and tokens[j] == '.'
                   and tokens[j + 1].isdigit() and len(tokens[j + 1]) == 3):
                num += tokens[j + 1]
                j += 2
            out.append(num)
            # decimal: digits , digits -> int  coma  fraction(read as number)
            if (j + 1 < len(tokens) and tokens[j] == ','
                    and tokens[j + 1].isdigit()):
                out.append('\x00coma')          # sentinel handled in _expand_one
                out.append(tokens[j + 1])
                j += 2
            i = j
        else:
            out.append(t)
            i += 1
    return out


def _expand_one(tok):
    if tok == '\x00coma':
        return ["coma"]
    if tok in _PUNCT or not tok.strip():
        return [tok]
    m = re.fullmatch(r'%(\d+)', tok) or re.fullmatch(r'(\d+)%', tok)
    if m:
        return ["por", "ciento"] + expnum(m.group(1))
    if tok.isdigit():
        return expnum(tok)
    # Roman numeral (es_romanhilvl isRomanN: pattern 'l', all-uppercase).  In
    # Spanish, even a SINGLE uppercase roman letter is read as an ordinal
    # (Alfonso X -> "décimo", siglo I -> "primero"); lowercase stays a word.
    if tok == tok.upper():
        rn = _roman_to_int(tok)
        if rn is not None:
            return _roman_ordinal_words(rn)
    return [tok]


def _expand_tokens(tokens):
    out = []
    for t in _merge_thousands(tokens):
        out.extend(_expand_one(t))
    return out


# ==========================================================================
# Per-pause-group phonemization
# ==========================================================================
def _group_to_singlechar(words, version, nonfinal=None):
    """words: list of lowercased surface words (accents preserved).
    Returns a list of single-char IPA strings, one per word.  `nonfinal[wi]`
    forces word wi to be treated as not phrase-final for stress (used for the
    non-last part of a hyphenated compound under V3)."""
    cfg = _CONFIG[version]
    if nonfinal is None:
        nonfinal = [False] * len(words)

    # 1) g2p over the whole pause group (so n+b->m sees the next word)
    phones, stress, pword = _g2p_group(words, glides=cfg["glides"])

    # map original char for each phone (for the n->m stress correction).
    # _g2p_group emits in source order; re-derive the source char per emitted
    # phone by replaying word strings: simplest is to track within _g2p_group,
    # but here we approximate src_char as the phone's word's char that yields
    # an 'n'.  The only consumer is the m/n llana rule, which needs to know if
    # the FINAL phone came from a written 'n'.  We recompute below per word.

    nwords = len(words)
    word_phones = [[] for _ in range(nwords)]
    for k in range(len(phones)):
        word_phones[pword[k]].append(k)

    # 1b) word-final cluster simplification (binary-only): drop a trailing
    # geminate / stop+stop consonant.  Done by trimming the word's phone-index
    # list so the dropped phone is gone from syllabification, stress and output.
    for wi in range(nwords):
        idxs = word_phones[wi]
        if len(idxs) >= 2:
            local = [phones[k] for k in idxs]
            simplified = _simplify_final_cluster(local)
            if len(simplified) < len(local):
                word_phones[wi] = idxs[:len(simplified)]

    # 2) syllabify + 3) glides + 4) stress, per word.
    for wi in range(nwords):
        idxs = word_phones[wi]
        if not idxs:
            continue
        local = [phones[k] for k in idxs]
        local_stress = [stress[k] for k in idxs]
        syls = _syllabify(local, local_stress)

        # glides (iu2jw) -- runs in ALL versions because it changes which vowel
        # is the syllable nucleus and therefore the stress placement (rousseau
        # -> rowsseAw / rousseAu, both aguda; veinticinco -> -sjEte / -siEte,
        # same stressed vowel).  V2 (libhtts VITS-era) computes stress from the
        # glided form but REVERTS the glide to the full i/u in its phone output;
        # V1/V3 keep the glide.  So we always glide here, and only the output
        # stage (controlled by cfg["glides"]) decides whether to render j/w.
        local = _apply_glides(local, local_stress, syls)
        for off, k in enumerate(idxs):
            phones[k] = local[off]

        # stress: only if the word has no written accent already.
        already = any(local_stress)
        if not already:
            surf = _deaccent(words[wi])
            src_chars = _src_chars_for_word(words[wi], local)
            is_last = (wi == nwords - 1) and not nonfinal[wi]
            atona = _ATONA_MONO_V3 if version == "v3" else _ATONA_MONO
            _word_stress(local, local_stress, surf, syls, is_last, src_chars,
                         atona_mono=atona)
        # write stress back
        for off, k in enumerate(idxs):
            stress[k] = local_stress[off]

    # 5) phones -> single-char IPA.  For versions with glides OFF (V2) revert
    # the j/w produced by iu2jw back to the full vowel i/u in the output (the
    # glide was only needed for the stress computation above).
    revert = {PHES['iaprox']: PHES['i'], PHES['uaprox']: PHES['u']}
    result = []
    for wi in range(nwords):
        toks = []
        for k in word_phones[wi]:
            sampa = phones[k]
            if not cfg["glides"]:
                sampa = revert.get(sampa, sampa)
            ipa = SAMPA_TO_IPA.get(sampa, sampa)
            if stress[k] and ipa in ('a', 'e', 'i', 'o', 'u'):
                ipa = "'" + ipa
            toks.append(MULTI.get(ipa, ipa))
        result.append("".join(toks))
    return result


def _deaccent(word):
    return ''.join(ACCENTED.get(c, DIERESIS.get(c, c)) for c in word)


def _src_chars_for_word(word, local_phones):
    """Best-effort: for the n->m llana correction we only need to know whether
    the LAST phone derives from a written 'n'.  The 'n'->'m' coarticulation
    only fires inside a word before b/m/p/v/f, never word-finally, so a
    word-final m can only come from a written 'm'.  Thus the correction (which
    targets a word-FINAL m that came from 'n') never fires for an isolated
    word; it only matters across the pause group, handled by the full-group n
    rule.  Return a list mapping each phone to '' except where we can be sure.

    We map by replaying: count letters that produce a phone.  Simpler: return
    the de-accented word's final letter for the final phone slot."""
    n = len(local_phones)
    src = [''] * n
    if n and word:
        src[-1] = word[-1]
    return src


# ==========================================================================
# Top level
# ==========================================================================
_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)
_NORMAL_KEEP = "abcdefghijklmnopqrstuvwxyzñáéíóúü"
# V3 (modulo1y2 + eu_phonemizer) re-inserts every char in Python's
# string.punctuation as a separate token; V1/V2 (libhtts) keep only the pause
# punctuation.  We emit the broader set for V3.
_PUNCT_V3 = set('!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~')


# es_speller.cpp / es_getchexp letter-name table (the char-spelling expansion).
# A token with no vowel is spelled letter-by-letter using these Spanish letter
# names, which are then phonemized normally (verified char-by-char against the
# libhtts binary: km -> "ka eme", spn -> "ese pe ene", cm -> "ce eme", ...).
_LETTER_NAME = {
    'a': 'a', 'b': 'be', 'c': 'ce', 'd': 'de', 'e': 'e', 'f': 'efe',
    'g': 'ge', 'h': 'hache', 'i': 'i', 'j': 'jota', 'k': 'ka', 'l': 'ele',
    'm': 'eme', 'n': 'ene', 'ñ': 'eñe', 'o': 'o', 'p': 'pe', 'q': 'cu',
    'r': 'erre', 's': 'ese', 't': 'te', 'u': 'u', 'v': 'uve',
    'w': 'uve doble', 'x': 'equis', 'y': 'i', 'z': 'zeta',
}
# y counts as a vowel for the "has a vowel?" pronounceability test (kyk reads
# as a word in the binary), so it is NOT in this trigger set.
_VOWEL_CHARS = set("aeiouáéíóúü")


def _has_vowel(nw):
    return any(c in _VOWEL_CHARS or c == 'y' for c in nw)


# isPronun (es_speller.cpp): an all-uppercase acronym is read as a word only if
# its letter sequence is syllabifiable as Spanish; otherwise it is spelled
# letter-by-letter (CERN -> "ce e erre ene", DNI -> "de ene i", but OTAN/NASA/
# OVNI/PSOE are read).  We model this with a maximal-onset syllabifier over the
# raw letters using the engine's onset/coda inventory.  Verified against the
# libhtts binary on a battery of real and synthetic acronyms.
_PRON_ONSET2 = ({a + b for a in 'bcdfgkpt' for b in 'lr'}
                | {'tl', 'ps', 'pn', 'gn'})
_PRON_CODA1 = set('nsrldzkxbptcmgfvyjñ')


def _is_pronounceable(token):
    """True if `token` (letters only) can be syllabified as a Spanish word."""
    w = token.lower()
    n = len(w)
    i = 0
    while i < n and w[i] not in _VOWEL_CHARS:
        i += 1
    if i == n:
        return False                          # no vowel -> not a word
    onset = w[:i]
    if len(onset) > 2:
        return False
    if len(onset) == 2 and onset not in _PRON_ONSET2:
        return False
    while i < n:
        while i < n and w[i] in _VOWEL_CHARS:
            i += 1
        if i >= n:
            break
        j = i
        while j < n and w[j] not in _VOWEL_CHARS:
            j += 1
        cl = w[i:j]
        if j >= n:                            # final coda
            if len(cl) == 1 and cl in _PRON_CODA1:
                return True
            if (len(cl) == 2 and cl[0] in 'nsrl'
                    and cl[1] in 'sptkcbdgmfx'):
                return True
            return len(cl) == 0
        ok = False                            # split intervocalic cluster
        for split in range(len(cl) + 1):
            coda, ons = cl[:split], cl[split:]
            coda_ok = (len(coda) == 0
                       or (len(coda) == 1 and coda in _PRON_CODA1)
                       or (len(coda) == 2 and coda[0] in 'nsrl'))
            ons_ok = (len(ons) <= 1 or (len(ons) == 2 and ons in _PRON_ONSET2))
            if coda_ok and ons_ok:
                ok = True
                break
        if not ok:
            return False
        i = j
    return True


def _spell_word(nw):
    """es_speller.cpp spellCell: spell a no-vowel token letter-by-letter,
    returning the list of letter-name words (digits read as numbers)."""
    out = []
    for c in nw:
        if c.isdigit():
            out.extend(expnum(c))
        else:
            name = _LETTER_NAME.get(c)
            if name:
                out.extend(name.split())
    return out


def _normalize_word(word):
    """Lowercase, keep Spanish letters + accents; drop other chars."""
    w = word.lower()
    return ''.join(c for c in w if c in _NORMAL_KEEP)


# ASCII string.punctuation -- the set the upstream getPhonemes wrapper uses.
# Kept for reference; the engine uses the Unicode-aware test below.
_PUNCT_STRING = set('!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~')


def _is_punct_token(w):
    """A single punctuation character (Unicode category P*), including the
    Spanish inverted marks ¿ ¡ and «»/“”/–— that ASCII string.punctuation
    misses."""
    return len(w) == 1 and _unicodedata.category(w).startswith('P')


def _v3_interleave(orig_text, cleaned):
    """Port of arrandi eu_phonemizer.getPhonemes word/group interleaving, with
    the upstream punctuation-counting bug FIXED: tokenize the ORIGINAL line into
    word/punct tokens, emit each punctuation char as-is, and consume one phoneme
    group (in order) per non-punct token; leftover groups past the last source
    word are dropped.

    BUGFIX vs upstream: getPhonemes classifies "non-punctuation words" with
    Python's ASCII-only `string.punctuation`, so `¿`/`¡` (and «»/“”/–—) are
    miscounted as words.  The binary emits no phoneme group for them, so the
    non-punct count overshoots and the wrapper's pad-with-last-group loop
    DUPLICATES the final group (¿Qué hora es? -> kE Oɾa Es Es ?).  There is no
    linguistic ambiguity -- it is simply wrong -- so the port counts punctuation
    Unicode-aware (`_is_punct_token`), keeping the group/word counts aligned and
    yielding the correct output with no doubling (¿Qué hora es? -> kE Oɾa Es ?).
    The legitimate fewer-groups-than-words pad remains."""
    words = _TOKEN_RE.findall(orig_text)
    non_punct = [w for w in words if not _is_punct_token(w)]
    groups = list(cleaned)
    while len(groups) < len(non_punct):
        groups.append(groups[-1] if groups else "a")
    out = []
    pi = 0
    for w in words:
        if _is_punct_token(w):
            out.append(w)
            continue
        if pi < len(groups):
            out.append(groups[pi])
            pi += 1
    return ' '.join(out)


def phonemize_es(text, version="v1"):
    """text -> final single-char IPA training string for the given AhoTTS
    Spanish version ("v1", "v3").  Words space-separated.  For v3,
    punctuation is emitted as separate tokens (matching the modulo1y2
    pipeline); v1 drops punctuation."""
    if version not in _CONFIG:
        raise ValueError("version must be v1 or v3")
    keep_punct = _CONFIG[version]["keep_punct"]
    use_lexicon = _CONFIG[version]["lexicon"]

    text = re.sub(r'\.{2,}', '.', text)
    orig_text = text                       # original tokens, for V3 interleave
    # es_pow1 / symbolexp superscript: the binary expands a trailing "²" to the
    # words "al cuadrado" (verified: km² -> "ka eme al cuadrado", a² -> "a al
    # cuadrado").  "³"/"¹" are silently dropped.  A "²"-suffixed token also has
    # its unit lexicon bypassed (m² -> "eme al cuadrado", not "metro ..."), so
    # we tag those letter-parts to force the spell/read path without lexicon.
    raw_tokens = _TOKEN_RE.findall(text)
    tokens = []
    forced_spell = set()                   # indices into `tokens` to not lex-up
    for rt in raw_tokens:
        m = re.match(r'^(.*?)([²³¹]+)$', rt)
        if m and m.group(1):
            forced_spell.add(len(tokens))
            tokens.append(m.group(1))
            if '²' in m.group(2):
                tokens.extend(['al', 'cuadrado'])
            # ³/¹ are dropped
        elif rt in ('²', '³', '¹'):
            if rt == '²':
                tokens.extend(['al', 'cuadrado'])
        else:
            tokens.append(rt)
    # _expand_tokens may reorder; superscript tags are only used for word tokens
    # that survive expansion unchanged, so re-tag by value after expansion.
    forced_norm = {_normalize_word(tokens[k]) for k in forced_spell}
    forced_norm.discard('')
    tokens = _expand_tokens(tokens)

    # V1/V2 (libhtts) only see the pause punctuation; V3 (modulo1y2 wrapper)
    # re-inserts every string.punctuation char as a token.
    punct_set = _PUNCT_V3 if keep_punct else _PUNCT
    # A word token directly touching a hyphen in the source is part of a
    # hyphenated compound.  modulo1y2 (V3) does NOT spell a no-vowel part of a
    # hyphenated compound -- it emits it literally (i-spn-ya -> 'i | spn | ʝa,
    # the "spn" passed through raw).  Mark those tokens so the speller is
    # skipped for them under V3.
    hyphenated = set()
    for k, tok in enumerate(tokens):
        if tok == '-':
            for nb in (k - 1, k + 1):
                if 0 <= nb < len(tokens) and tokens[nb] not in punct_set:
                    hyphenated.add(nb)
    # A word is "hyphen-non-final" if it is immediately followed by a hyphen
    # that is itself followed by another word (i.e. it is not the last part of
    # its hyphenated compound).  modulo1y2 keeps the whole compound in one
    # phrase, so such a part is NOT phrase-final and a monosyllabic atonic
    # (al/de/...) stays unstressed there (Al-Ándalus -> "al ándalus").
    hyphen_nonfinal = set()
    for k, tok in enumerate(tokens):
        if tok == '-' and (k - 1) in hyphenated and (k + 1) in hyphenated:
            hyphen_nonfinal.add(k - 1)
    seq = []
    for k, tok in enumerate(tokens):
        if len(tok) == 1 and tok in punct_set:
            seq.append(('p', tok, False, False))
        elif tok.strip():
            seq.append(('w', tok, k in hyphenated, k in hyphen_nonfinal))

    # Build the ordered phoneme groups + (for V1/V2) interleaved punctuation.
    out_tokens = []   # V1/V2 output (and, for V3, the ordered group list)
    i = 0
    while i < len(seq):
        if seq[i][0] == 'p':
            if keep_punct:
                out_tokens.append(seq[i][1])
            i += 1
            continue
        group = []
        while i < len(seq) and seq[i][0] == 'w':
            group.append((seq[i][1], seq[i][2], seq[i][3]))
            i += 1
        norm = []
        norm_nonfinal = []     # parallel: this norm word must not be last-word
        literals = []          # V3: words to emit as a raw literal group
        lex = _lexicon() if use_lexicon else {}
        for w, is_hyph, nonfinal in group:
            nw = _normalize_word(w)
            if not nw:
                continue
            # es_dicc respelling / abbreviation expansion (foreign words,
            # proper names): replace the surface form with its dict spelling.
            # A "²"-suffixed letter-part bypasses the (unit) lexicon.
            sub = None if nw in forced_norm else lex.get(nw)
            if sub:
                for s in sub:
                    sn = _normalize_word(s)
                    if sn:
                        norm.append(sn)
                        norm_nonfinal.append(nonfinal)
            elif (not _has_vowel(nw)
                  or (len(nw) >= 2 and w.isupper()
                      and not _is_pronounceable(nw))):
                # es_speller.cpp isPronun: a no-vowel token, OR an all-uppercase
                # acronym whose letters are not syllabifiable as Spanish (CERN,
                # DNI, ...), is spelled letter-by-letter (km->ka eme, CERN->ce e
                # erre ene).  Pronounceable acronyms (OTAN, NASA, OVNI) are read.
                if keep_punct and is_hyph and not _has_vowel(nw):
                    # V3 hyphenated no-vowel part: emit literally (raw letters).
                    literals.append(nw)
                else:
                    for sw in _spell_word(nw):
                        norm.append(sw)
                        norm_nonfinal.append(nonfinal)
            else:
                norm.append(nw)
                norm_nonfinal.append(nonfinal)
        if not norm and not literals:
            continue
        if literals and not norm:
            # whole group is hyphenated no-vowel literal(s) (V3): emit raw.
            out_tokens.extend(literals)
            continue
        sc = _group_to_singlechar(norm, version, nonfinal=norm_nonfinal)
        for s in sc:
            if s:
                out_tokens.append(s)

    if not keep_punct:
        return ' '.join(out_tokens)

    # V3 (modulo1y2 + getPhonemes wrapper): the binary emits one phoneme group
    # per *expanded* word (numbers/units expand to many), but the authors'
    # getPhonemes re-interleaves those groups against the ORIGINAL source
    # tokens, consuming one group per non-punctuation source token in order and
    # dropping any leftover groups (and, if groups run short, leftover source
    # words).  That count mismatch is what shifts punctuation inside long
    # numbers and drops trailing words -- a faithful artifact of the wrapper.
    cleaned = [t for t in out_tokens if t not in _PUNCT_V3]
    return _v3_interleave(orig_text, cleaned)


if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else "Hola, el caballo come."
    for v in ("v1", "v3"):
        print(f"{v}: {phonemize_es(t, version=v)}")
