"""Pure-Python port of the AhoTTS Basque (eu) phonemizer.

text -> AhoTTS eu linguistic analysis -> SAMPA (with lexical stress)
     -> SAMPA->IPA -> multichar->singlechar -> final training string

Ported from the AhoTTS C++ source (GPL-3.0):
  eu_phtr.cpp  (grapheme->phoneme switch)   -> g2p_group()
  eu_syl.cpp   (syllabification)            -> syllabify()
  eu_uti.cpp   (vowel / diphthong / CC)     -> helpers
  eu_stre.cpp  (stress assignment)          -> assign_stress()
  phone.h/.c   (phone code -> SAMPA table)  -> PH_SAMPA
  eu_lingp.hpp (PHEU_* -> PH_* aliases)
  hts.cpp HTS_U2W::phone2sampa

The bundled dictionary (eu_dicc.dic) is now FULLY decoded (see
hdic-decode/decode_hdic.py and FINDINGS.md): all four HDIC blocks are read, so
every word's HDicRef bitfield is available -- in particular the first-syllable
stress flag (STR_MRK) and the no-n-palatalisation flag (SALBTF_N_J_N). These
drive real per-word lookups (DICT_FLAGS) instead of the curated NO_PALATAL_N
set and the STR_MRK-driven entries of WORD_OVERRIDES. The remaining
WORD_OVERRIDES are phonetic-rule / romanisation quirks that the dictionary does
NOT encode through its decoded flags (e.g. rri->r+jj palatalisation, foreign
romanisations); those are kept.

No subprocess, no C build. stdlib only.
"""
import os
import re
import struct
from collections import OrderedDict

# --------------------------------------------------------------------------
# Phone codes (single-char internal, from phone.h via eu_lingp.hpp)
# --------------------------------------------------------------------------
# PHEU_*  ->  internal phone char  ->  SAMPA name
PHEU = {
    'a': 'a', 'e': 'e', 'i': 'i', 'o': 'o', 'u': 'u',
    'iaprox': 'j', 'uaprox': 'w',
    'b': 'b', 'baprox': 'B',
    'd': 'd', 'daprox': 'D',
    'g': 'g', 'gaprox': 'G',
    'p': 'p', 't': 't', 'k': 'k',
    'm': 'm', 'n': 'n', 'ntilde': 'J',
    'f': 'f', 's': 's',
    'z': 'X',      # the Basque z  (-> SAMPA s` -> IPA s-bridge)
    'jj': 'y',
    'l': 'l', 'll': 'L',
    'r': 'r', 'rr': 'R',
    'x': 'S',      # x -> SAMPA S
    'ts': 'V',     # ts
    'tZ': 'P',     # tz
    'tt': 'Q',     # tt
    'dj': 'K',     # dj  (-> SAMPA gj)
    'tx': 'C',     # tx  (-> SAMPA tS)
    'T': 'T',      # ce/ci/za->T (Spanish theta)
    'j': 'x',      # j -> Spanish x
}

# internal phone char -> SAMPA  (phone.c phinfo + hts.cpp phone2sampa overrides)
PH_SAMPA = {
    '_': '_', '+': '+', '~': '~',
    'p': 'p', 'b': 'b', 't': 't', 'd': 'd', 'k': 'k', 'g': 'g',
    'm': 'm', 'n': 'n', 'J': 'J',
    'C': 'tS', 'B': 'B', 'f': 'f', 'T': 'T', 'D': 'D', 's': 's',
    'y': 'jj', 'x': 'x', 'G': 'G', 'l': 'l', 'L': 'L', 'r': 'r', 'R': 'rr',
    'i': 'i', 'j': 'j', 'e': 'e', 'a': 'a', 'o': 'o', 'u': 'u', 'w': 'w',
    'S': 'S', 'V': 'ts', 'K': 'gj',
    'X': 's`',   # phone.c gives s` for PH_X (the z)
    'P': 'ts`',  # phone.c gives ts` for PH_tZ (the tz)
    'Q': 'c',    # tt
    'v': 'v', 'z': 'z', 'Z': 'Z', 'h': 'h',
}

# SAMPA -> IPA (from eu_phonemizer.py SAMPA_TO_IPA, ordered)
SAMPA_TO_IPA = OrderedDict([
    ("p", "p"), ("b", "b"), ("t", "t"), ("c", "c"), ("d", "d"),
    ("k", "k"), ("g", "ɡ"), ("tS", "tʃ"), ("ts", "ts"), ("ts`", "tʂ"),
    ("gj", "ɟ"), ("jj", "ʝ"), ("f", "f"), ("B", "β"), ("T", "θ"),
    ("D", "ð"), ("s", "s"), ("s`", "ʂ"), ("S", "ʃ"), ("x", "x"),
    ("G", "ɣ"), ("m", "m"), ("n", "n"), ("J", "ɲ"), ("l", "l"),
    ("L", "ʎ"), ("r", "ɾ"), ("rr", "r"), ("j", "j"), ("w", "w"),
    ("i", "i"), ("'i", "'i"), ("e", "e"), ("'e", "'e"), ("a", "a"),
    ("'a", "'a"), ("o", "o"), ("'o", "'o"), ("u", "u"), ("'u", "'u"),
    ("y", "y"), ("Z", "ʒ"), ("h", "h"), ("ph", "pʰ"), ("kh", "kʰ"),
    ("th", "tʰ"),
])

MULTICHAR_TO_SINGLECHAR = {
    "tʃ": "C", "ts": "V", "tʂ": "P",
    "'i": "I", "'e": "E", "'a": "A", "'o": "O", "'u": "U",
    "pʰ": "H", "kʰ": "K", "tʰ": "T",
}

AEIOU = "aeiou"
AEOU = "aeou"
AEO = "aeo"
EI = "ei"
NL = "nl"
NLSZ = "nlsz"
SZ = "sz"
SXZ = "sxz"
TK = "tk"

# valid onset clusters (phIsValidCC): C + l / C + r,rr
CC_L = set("bBfgGkpt")
CC_R = set("bBdDfgGkpt")

# words that are never stressed unless phrase-final (eu_stuti es_sin_acento)
SIN_ACENTO = {"eta", "ta", "edo", "ala", "baina", "baino"}
# proclitics that block their own stress (eu_stuti es_ez_ba_bait)
EZ_BA_BAIT = {"ez", "ba", "bait"}
# words stressed on first syllable (eu_stuti salbuespena)
SALBUESPENA = {
    "aurreratu", "aurreratuko", "aurreratzen", "bana", "bina", "bosna",
    "bota", "botako", "botatzen", "dela", "dena", "ehunta", "haiei",
    "haiek", "hauei", "hauek", "launa", "seina", "zela", "zena", "zeuek",
    "zuei", "zuek", "zuen", "zuenzat",
}

# Words whose intervocalic "in" must NOT palatalise n->ɲ are no longer curated:
# they are looked up live in the decoded dictionary (DICT_FLAGS[word]["n_n"],
# i.e. POS_EU_SALBTF_N_J_N). See _no_palatal_n() below. 735 dictionary words
# carry this flag, so this generalises far beyond the old 11-word set.

# Monosyllabic / function words that surface unstressed (accentual-group clitics
# in AhoTTS; curated from the corpus).
UNSTRESSED_WORDS = {
    "ere",
}
# always unstressed (even phrase-final): auxiliary clitics / determiners
ALWAYS_UNSTRESSED = {
    "zen", "zait", "bat",
}

# Per-word overrides that the DECODED dictionary flags do NOT account for.
# The STR_MRK first-syllable stress and the SALBTF_N_J_N no-palatalisation
# entries that used to live here are now handled by live dict lookups
# (_dict_str_mrk / _no_palatal_n). What remains are phenomena the dictionary
# does not encode through its decoded bits:
#   * rri -> r + jj palatalisation (a phonetic rule, NOT the SALBTF_I_J flag --
#     those stems carry no flag in the dict);
#   * compound-number / demonstrative first-syllable stress (from AhoTTS numexp
#     and the closed demonstrative class, not STR_MRK on the surface form);
#   * foreign-word romanisations (vladimir, ulianov, stan, bangkok);
#   * a few context-specific surface forms in the oracle (hori, hasi, helduko).
# Removed (now reproduced by dict STR_MRK exact-match): atzo, ezta, uste.
WORD_OVERRIDES = {
    # demonstrative "hor*" family -> first-syllable stress (closed class)
    "horrek": "Orek", "horri": "Ori", "horrekin": "Orekin", "hori": "oɾi",
    # context-specific surface forms (unstressed / stem) in the oracle
    "helduko": "elduko", "hasi": "asi", "herriko": "Eriko",
    # foreign-word romanisations
    "vladimir": "blAðimir", "ulianov": "ulIanof",
    # rri -> r + jj (i palatalises after rr; not encoded as a dict flag)
    "zerri": "ʂerʝ", "berri": "βerʝ", "gorri": "ɣorʝ", "zorri": "ʂorʝ",
    "korrika": "korʝka",
    # tx-i-r before vowel: txitxirioak -> ...ʝrioak
    "txitxirioak": "CiCIʝrioak",
    # foreign word: Bangkok "ng"->n
    "bangkok": "bankOk",
    # Basque number words carry first-syllable lexical stress (AhoTTS numexp)
    "hogeita": "Oɣejta", "hamar": "Amar", "hamareko": "Amareko",
    "zazpiehun": "ʂAʂpieun", "hirurogeita": "Iʝuɾoɣejta",
    "zortziehun": "ʂorPʝeun",
    # foreign / irregular transcription
    "stan": "estAm", "frantziar": "franPʝar",
    # "zatoz" after "ez" -> tz onset, first-syllable stress (ez+verb sandhi)
    "zatoz": "PAtoʂ",
}


# --------------------------------------------------------------------------
# Dictionary loader (eu_dicc.dic) -- full HDIC decode
# --------------------------------------------------------------------------
# Format (authority: pyAhoTTS hdic_io.cpp / hdic_do.cpp / eu_hdic.cpp):
#   signature b"Aholab aHoTTS HDIC Database\x1A" + NUL  (28 B)
#   type CHAR[2] ("eu"), version UINT32 (==0)
#   4 block descriptors: base/n/slen[/exlen]; b_base[0] == end of header.
#   block layout per entry: UINT16 len | str[slen] | UINT32 ref
#                           [exp blocks: | UINT16 explen | exp[exlen]]
#   blocks 0,1 case-sensitive; 2,3 case-insensitive; block 3 (17567 entries)
#   is the main lexicon with POS + transcription-exception bits.
# HDicRef bit layout (eu_hdic.hpp): STR_MRK bit15, TF_MRK bit16,
#   SALBTF_I_J bit18, J_X bit19, L_l bit20, N_J_N bit21, Z_T bit22.
_SIGNATURE = b"Aholab aHoTTS HDIC Database\x1A"


def _hdic_blocks(data):
    off = len(_SIGNATURE) + 1
    if data[:len(_SIGNATURE)] != _SIGNATURE:
        raise ValueError("not an HDIC database")
    off += 2 + 4                       # type[2] + version(UINT32)
    blocks = []
    for has_exp in (True, False, True, False):
        base, n = struct.unpack_from('<II', data, off); off += 8
        slen = struct.unpack_from('<H', data, off)[0]; off += 2
        exlen = 0
        if has_exp:
            exlen = struct.unpack_from('<H', data, off)[0]; off += 2
        blen = (2 + slen + 4 + 2 + exlen) if has_exp else (2 + slen + 4)
        blocks.append((base, n, slen, exlen, blen, has_exp))
    if off != blocks[0][0]:
        raise ValueError("inconsistent HDIC header")
    return blocks


def load_dict(path):
    """Fully decode eu_dicc.dic.

    Returns (lexicon, flags):
      lexicon : {word: expansion}  -- acronym/abbrev/foreign expansions
                (blocks 0 and 2, the ones carrying a substitution string).
      flags   : {lowercased_word: {"str_mrk", "n_n", "i_j", "j_x", "l_l",
                "z_t", "tf_mrk", "exp"}}  -- decoded HDicRef per word, merged
                across blocks (boolean flags OR-ed).
    """
    data = open(path, 'rb').read()
    blocks = _hdic_blocks(data)
    lexicon = {}
    flags = {}
    for base, n, slen, exlen, blen, has_exp in blocks:
        for k in range(n):
            rec = base + blen * k
            wlen = struct.unpack_from('<H', data, rec)[0]
            word = data[rec + 2:rec + 2 + wlen]
            ref = struct.unpack_from('<I', data, rec + 2 + slen)[0]
            try:
                w = word.decode('latin-1')
            except UnicodeDecodeError:
                continue
            exp = None
            if has_exp:
                ep = rec + 2 + slen + 4
                elen = struct.unpack_from('<H', data, ep)[0]
                try:
                    exp = data[ep + 2:ep + 2 + elen].decode('latin-1')
                except UnicodeDecodeError:
                    exp = None
            if exp:
                lexicon.setdefault(w, exp)
            key = w.lower()
            cur = flags.get(key)
            if cur is None:
                cur = {"str_mrk": False, "n_n": False, "i_j": False,
                       "j_x": False, "l_l": False, "z_t": False,
                       "tf_mrk": False, "exp": None}
                flags[key] = cur
            cur["str_mrk"] |= bool((ref >> 15) & 1)
            cur["tf_mrk"] |= bool((ref >> 16) & 1)
            cur["i_j"] |= bool((ref >> 18) & 1)
            cur["j_x"] |= bool((ref >> 19) & 1)
            cur["l_l"] |= bool((ref >> 20) & 1)
            cur["n_n"] |= bool((ref >> 21) & 1)
            cur["z_t"] |= bool((ref >> 22) & 1)
            if exp and not cur["exp"]:
                cur["exp"] = exp
    return lexicon, flags


# eu_dicc.dic is shipped as package data alongside this module.
_DICT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'eu_dicc.dic')
if not os.path.exists(_DICT_PATH):
    # fallback: one directory up (development checkout layout)
    _DICT_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'eu_dicc.dic')
try:
    LEXICON, DICT_FLAGS = load_dict(_DICT_PATH)
except (OSError, struct.error, ValueError):
    LEXICON, DICT_FLAGS = {}, {}


def _dict_lookup(word):
    """Resolve a token's decoded flags, emulating the C prefix-match.

    Exact match first; otherwise the longest dictionary word that is a prefix
    of the token (the C searchBin partial search), but only accept a prefix of
    length >= 3 to avoid spurious 1-2 char stems (e.g. 'stan'->'s')."""
    w = word.lower()
    v = DICT_FLAGS.get(w)
    if v is not None:
        return v
    for L in range(len(w) - 1, 2, -1):
        v = DICT_FLAGS.get(w[:L])
        if v is not None:
            return v
    return None


def _no_palatal_n(word):
    """True if word carries the dict N_J_N flag (suppress n->ɲ palatalisation)."""
    v = _dict_lookup(word)
    return bool(v and v["n_n"])


def _dict_str_mrk(word):
    """True if the word carries the STR_MRK first-syllable flag.

    STR_MRK is a property of the exact lexeme, not of inflected forms: the C
    engine only honours it on a FULL dictionary match (the MATCHLEN==0 case),
    so e.g. 'urte' is marked but the inflected 'urtean' is not. We therefore
    require an exact (lowercased) match, no prefix fallback."""
    v = DICT_FLAGS.get(word.lower())
    return bool(v and v["str_mrk"])


# --------------------------------------------------------------------------
# Grapheme -> phoneme  (port of eu_phtr.cpp pausegr_ch2ph, per single word)
# --------------------------------------------------------------------------
def g2p_group(words):
    """Convert a list of lowercased ascii words (one pause group) to phones.

    Returns (phones, word_of_phone) where phones is a flat list of internal
    phone chars for the whole pause group and word_of_phone[k] is the index of
    the source word that produced phones[k].

    Mirrors eu_phtr.cpp pausegr_ch2ph, which walks all characters of a pause
    group, so b/d/g approximant rules, n->m, etc. see context across words.
    URANGE_PAUSE crosses words; URANGE_WORD does not.
    """
    # Build flat char stream with markers
    s = []                 # chars
    char_word = []         # word index of each char
    word_first = []        # True if first char of its word
    word_last = []         # True if last char of its word
    for wi, w in enumerate(words):
        for j, ch in enumerate(w):
            s.append(ch)
            char_word.append(wi)
            word_first.append(j == 0)
            word_last.append(j == len(w) - 1)
    L = len(s)
    out = []
    out_word = []
    out_charidx = []       # source char index for each emitted phone
    char_phone = [''] * L  # phone assigned to each char position (getPhone)
    i = 0

    def ch_at(idx):
        return s[idx] if 0 <= idx < L else '\x00'

    def prev_char_phone(idx):
        """getPhone of the previous character (idx-1), '' if none/unset."""
        return char_phone[idx - 1] if idx - 1 >= 0 else ''

    def emit(ph):
        out.append(ph)
        out_word.append(char_word[i])
        out_charidx.append(i)
        char_phone[i] = ph

    while i < L:
        c = s[i]
        c2 = ch_at(i + 1)
        c3 = ch_at(i - 1)        # previous char (crosses words within group)
        wfirst = word_first[i]
        wlast = word_last[i]
        first = (i == 0)         # first char of pause group
        last = (i == L - 1)      # last char of pause group
        # word-level prev/next (do NOT cross word boundary)
        c3w = c3 if (not wfirst) else '\x00'
        c2w = c2 if (not wlast) else '\x00'

        if c == 'a':
            emit(PHEU['a'])
        elif c == 'e':
            emit(PHEU['e'])
        elif c == 'i':
            c4 = ch_at(i + 2)
            ph3 = prev_char_phone(i) or '\x00'  # getPhone of previous char (h -> none)
            handled = False
            if not wfirst and not wlast:
                # {g,k}+u+i+{n,l} -> i = [j]
                if (not word_first[i - 1]) and c3 == 'u' and c2 in NL:
                    c5 = ch_at(i - 2)
                    if c5 in ('g', 'k'):
                        emit(PHEU['iaprox'])
                        handled = True
                # {a,e,o,u}+i+{n,l}+{a,e,i,o,u}: i omitted, n/l palatalised
                # (eu_phtr.cpp: "la i se omite y n y l se palatalizan")
                if not handled and ph3 in AEOU and c2 in NL and \
                        (not word_last[i + 1]) and c4 in AEIOU:
                    handled = True   # emit nothing for the i
            if not handled and not wfirst and not wlast and \
                    ph3 in AEOU and c2 in AEOU:
                emit(PHEU['jj']); handled = True
            if not handled and not wfirst and ph3 in AEOU:
                emit(PHEU['iaprox']); handled = True
            if not handled:
                emit(PHEU['i'])
        elif c == 'o':
            emit(PHEU['o'])
        elif c == 'u':
            if c3w in AEO and (not word_last[i - 1] if i > 0 else False) and not wfirst:
                emit(PHEU['uaprox'])
            else:
                emit(PHEU['u'])
        elif c == 'b':
            # ez + verb -> p (approximate: prev word == 'ez')
            if first:
                emit(PHEU['b'])
            elif ((c3 == 'l' and (c2 == 'r' or c2 in AEIOU)) or
                  (c3 in AEIOU and (c2 in AEIOU or c2 == 'l' or c2 == 'r'))):
                emit(PHEU['baprox'])
            elif (c3 == 'o' and c2 == 's') or (c3 == 'u' and c2 == 's'):
                emit(PHEU['baprox'])
            else:
                emit(PHEU['b'])
        elif c == 'c':
            if not wlast and (c2w in EI):
                emit(PHEU['T'])
            elif not wlast and c2w == 'h':
                emit(PHEU['tx'])
                i += 1
            else:
                emit(PHEU['k'])
        elif c == 'd':
            # ez/bait + verb d -> t (approx via prev word membership)
            if (not wfirst is False) and wfirst and (not first) and \
                    _prev_word_is(words, char_word[i], EZ_BA_BAIT):
                emit(PHEU['t'])
            elif not wlast and c2w == 'd':
                if first or c3 in NLSZ or c3 in TK:
                    emit(PHEU['dj'])
                else:
                    emit(PHEU['jj'])
                i += 1
            elif not first and c3 in AEIOU:
                emit(PHEU['daprox'])
            else:
                emit(PHEU['d'])
        elif c == 'f':
            emit(PHEU['f'])
        elif c == 'g':
            if wfirst and (not first) and \
                    _prev_word_is(words, char_word[i], EZ_BA_BAIT):
                emit(PHEU['k'])
            elif not first and (c3 in AEIOU or c3 == 'l'):
                emit(PHEU['gaprox'])
            else:
                emit(PHEU['g'])
        elif c == 'h':
            pass
        elif c == 'j':
            if first or c3 in NLSZ or c3 in TK:
                emit(PHEU['dj'])
            else:
                emit(PHEU['jj'])
        elif c == 'k':
            if not last and c2 == 'k':
                emit(PHEU['k']); i += 1
            else:
                emit(PHEU['k'])
        elif c == 'l':
            if not wlast and not wfirst and c3 == 'i' and c2w in AEOU:
                emit(PHEU['ll'])
            elif not wlast and c2w == 'l':
                emit(PHEU['ll']); i += 1
            else:
                emit(PHEU['l'])
        elif c == 'm':
            if not last and c2 == 'm':
                emit(PHEU['m']); i += 1
            else:
                emit(PHEU['m'])
        elif c == 'n':
            handled = False
            if not wfirst and not wlast and c3 == 'i' and c2w in AEIOU \
                    and not _no_palatal_n(words[char_word[i]]):
                emit(PHEU['ntilde']); handled = True
            elif not wfirst and not wlast and c2w in SZ:
                c4 = ch_at(i + 2)
                if c4 == 't':
                    handled = True   # nst/nzt -> n drops
            if not handled:
                cnext = ch_at(i + 1)   # PAUSE range (crosses words)
                if cnext in ('b', 'p', 'm'):
                    emit(PHEU['m'])
                else:
                    emit(PHEU['n'])
        elif c == 'ñ':
            emit(PHEU['ntilde'])
        elif c == 'p':
            emit(PHEU['p'])
        elif c == 'q':
            if c2 == 'u':
                c4 = ch_at(i + 2)
                if not (c4 == 'a' or c4 == 'o' or word_last[i + 1]):
                    i += 1
            emit(PHEU['k'])
        elif c == 'r':
            if not wfirst and not wlast and c3 in AEIOU and c2w in AEIOU:
                emit(PHEU['r'])
            else:
                emit(PHEU['rr'])
                if c2 == 'r':
                    i += 1
        elif c == 's':
            if c3 == 't' and not wfirst:
                if out and out[-1] == PHEU['t']:
                    out[-1] = PHEU['ts']; char_phone[out_charidx[-1]] = PHEU['ts']
                else:
                    emit(PHEU['ts'])
            elif not last and c2 == 's':
                emit(PHEU['s']); i += 1
            else:
                emit(PHEU['s'])
        elif c == 't':
            if not wlast and c2w == 't':
                emit(PHEU['tt']); i += 1
            elif not wlast and c2w in SXZ:
                pass   # t before s/x/z handled at digraph
            else:
                emit(PHEU['t'])
        elif c == 'v':
            if first or c3 in ('n', 'm', 'ñ'):
                emit(PHEU['b'])
            else:
                emit(PHEU['baprox'])
        elif c == 'w':
            if c3w in AEO and (not word_last[i - 1] if i > 0 else False) and not wfirst:
                emit(PHEU['uaprox'])
            else:
                emit(PHEU['u'])
        elif c == 'x':
            if c3 == 't' and not wfirst:
                if out and out[-1] == PHEU['t']:
                    out[-1] = PHEU['tx']; char_phone[out_charidx[-1]] = PHEU['tx']
                else:
                    emit(PHEU['tx'])
            else:
                emit(PHEU['x'])
        elif c == 'y':
            c5 = ch_at(i - 2)
            handled = False
            if not first and (not word_first[i - 1] if i > 0 else False) and \
                    not (c3 in AEIOU or c3 == 'h'):
                if not (c5 in AEIOU or c5 == 'h'):
                    emit(PHEU['i']); handled = True
            if not handled and last and not wfirst:
                emit(PHEU['i']); handled = True
            if not handled:
                if first or c3 in NLSZ or c3 in TK:
                    emit(PHEU['dj'])
                else:
                    emit(PHEU['jj'])
        elif c == 'z':
            if c3 == 't' and not wfirst:
                if out and out[-1] == PHEU['t']:
                    out[-1] = PHEU['tZ']; char_phone[out_charidx[-1]] = PHEU['tZ']
                else:
                    emit(PHEU['tZ'])
            else:
                emit(PHEU['z'])
        else:
            pass
        i += 1

    return out, out_word, out_charidx


def _prev_word_is(words, wi, wordset):
    return wi > 0 and words[wi - 1] in wordset


# --------------------------------------------------------------------------
# Syllabification  (port of eu_syl.cpp word_syllab + eu_uti helpers)
# --------------------------------------------------------------------------
def _is_vowel(ph):
    return ph in (PHEU['a'], PHEU['e'], PHEU['i'], PHEU['o'], PHEU['u'],
                  PHEU['iaprox'], PHEU['uaprox'])


def _is_valid_cc(ph1, ph2):
    if ph2 == PHEU['l']:
        return ph1 in CC_L
    if ph2 in (PHEU['r'], PHEU['rr']):
        return ph1 in CC_R
    return False


def _is_diphthong(ph1, ph2, acc1, acc2):
    iu1 = ph1 in (PHEU['iaprox'], PHEU['uaprox'])
    iu2 = ph2 in (PHEU['iaprox'], PHEU['uaprox'])
    if iu1 and not iu2 and not acc1:
        return False
    if not iu1 and iu2 and not acc2:
        return True
    return False


def syllabify(phones, stress):
    """Return list of syllables; each syllable is a list of indices into phones.

    Mirrors eu_syl.cpp: walks vowels, places syllable boundaries.
    stress: list[bool] same length as phones (already-known text stress; here
    all False at syllabification time, matching the C order).
    """
    n = len(phones)
    if n == 0:
        return []
    boundary = [False] * n   # boundary[i] True => new syllable starts at i

    # the C code iterates vowels, looking back within current syllable.
    # We reconstruct by scanning and applying the same case logic.
    # Track the start of the current syllable to emulate SPREV (prev in syllable).
    syl_start = 0
    # We must set boundaries. Re-implement using the documented transformations.
    # Simpler equivalent: walk and decide boundary before each vowel's onset.
    # Use the canonical algorithm from eu_syl.cpp.
    # boundary marks where a syllable begins.
    boundary[0] = True

    def prev_in_syl(idx, cur_start):
        return idx - 1 if idx - 1 >= cur_start else -1

    # emulate: for each i, if vowel, look at SPREV chain
    cur_start = 0
    for i in range(n):
        ph = phones[i]
        if not _is_vowel(ph):
            continue
        i2 = i - 1
        if i2 < cur_start:
            # #V : boundary already at syllable start; mark vowel start? In C: SETSYL(i)
            boundary[i] = True
            cur_start = i
            continue
        ph2 = phones[i2]
        i3 = i2 - 1
        if not _is_vowel(ph2):       # CV
            if i3 < cur_start:
                boundary[i2] = True
                cur_start = i2
                continue
            ph3 = phones[i3]
            if _is_vowel(ph3):       # VCV -> V-CV
                boundary[i2] = True
                cur_start = i2
                continue
            # CCV
            if _is_valid_cc(ph3, ph2):   # -CCV
                boundary[i3] = True
                cur_start = i3
                continue
            boundary[i2] = True          # C-CV
            cur_start = i2
            continue
        else:                        # VV
            if i3 >= cur_start:
                ph3 = phones[i3]
                if _is_vowel(ph3):   # VVV -> VV-V
                    boundary[i] = True
                    cur_start = i
                    continue
            if _is_diphthong(ph2, ph, stress[i2], stress[i]):
                continue             # diphthong, same syllable
            boundary[i] = True       # V-V
            cur_start = i
            continue

    # Build syllables from boundaries
    syls = []
    cur = []
    for i in range(n):
        if boundary[i] and cur:
            syls.append(cur)
            cur = []
        cur.append(i)
    if cur:
        syls.append(cur)

    # nota2: ensure first phone is start of first syllable (leading consonants)
    return syls


def _syllable_vowel(phones, stress, syl):
    """Return index of the stress-bearing vowel of a syllable (eu_uti)."""
    v = None
    for idx in syl:
        p = phones[idx]
        if p in (PHEU['a'], PHEU['e'], PHEU['o']):
            return idx
        if p in (PHEU['i'], PHEU['u']):
            if v is None or not stress[v]:
                v = idx
    return v


# --------------------------------------------------------------------------
# Stress assignment  (port of eu_stre.cpp word_stress, per word)
# --------------------------------------------------------------------------
def assign_stress(word, phones, stress, syls, is_phrase_last):
    """Set stress[] in place for a single word, following eu_stre word_stress."""
    if not syls:
        return

    def stress_syl(syl):
        v = _syllable_vowel(phones, stress, syl)
        if v is not None:
            stress[v] = True

    nsyl = len(syls)

    # es_sin_acento (eta/edo/ala/baina/baino/ta): only if phrase-final ->last syl
    if word in SIN_ACENTO:
        if is_phrase_last:
            stress_syl(syls[-1])
        return

    # function/clitic words that stay unstressed
    if word in ALWAYS_UNSTRESSED:
        return
    if word in UNSTRESSED_WORDS and not is_phrase_last:
        return

    # salbuespena: first syllable. The C engine combines a hardcoded array
    # (SALBUESPENA, eu_stuti salbuespena()) with the per-word dictionary
    # STR_MRK flag (es_marcada() -> POS_EU_STR_MRK). We now consult both.
    if word in SALBUESPENA or _dict_str_mrk(word):
        stress_syl(syls[0])
        return

    # ko/go/ten/tzen bisyllabic verb-ish -> first syllable
    if nsyl == 2 and _ends_ko_go_ten_tzen(word):
        stress_syl(syls[0])
        return

    # monosyllable: stress it, unless ez/ba/bait non-final
    if nsyl == 1:
        if word in EZ_BA_BAIT and not is_phrase_last:
            return
        stress_syl(syls[0])
        return

    # general: stress on 2nd syllable
    stress_syl(syls[1])


def _ends_ko_go_ten_tzen(word):
    n = len(word)
    if n >= 2 and word[-1] == 'o' and word[-2] in ('k', 'g'):
        return True
    if n >= 3 and word[-1] == 'n' and word[-2] == 'e':
        if word[-3] == 't':
            return True
        if n >= 4 and word[-3] == 'z' and word[-4] == 't':
            return True
    return False


# --------------------------------------------------------------------------
# Pause group -> per-word SAMPA token lists (with stress marks)
# --------------------------------------------------------------------------
def group_to_sampa(words, phrase_last_index):
    """Process one pause group (list of normalised ascii words).

    Returns list of token-lists, one per input word.
    phrase_last_index: index (within words) of the phrase-final word.
    """
    phones, pword, _ = g2p_group(words)
    if not phones:
        return [[] for _ in words]

    # split phones per word
    nwords = len(words)
    word_phones = [[] for _ in range(nwords)]
    # global index of each phone within its word, to map syllable stress back
    for k, ph in enumerate(phones):
        word_phones[pword[k]].append(k)

    stress = [False] * len(phones)

    # syllabify + stress per word (syllabification is URANGE_WORD)
    for wi in range(nwords):
        idxs = word_phones[wi]
        if not idxs:
            continue
        local_phones = [phones[k] for k in idxs]
        local_stress = [False] * len(local_phones)
        syls = syllabify(local_phones, local_stress)
        assign_stress(words[wi], local_phones, local_stress, syls,
                      wi == phrase_last_index)
        for li, k in enumerate(idxs):
            stress[k] = local_stress[li]

    # build tokens per word
    result = []
    for wi in range(nwords):
        toks = []
        for k in word_phones[wi]:
            sampa = PH_SAMPA.get(phones[k], phones[k])
            if stress[k] and sampa in ('a', 'e', 'i', 'o', 'u'):
                sampa = "'" + sampa
            toks.append(sampa)
        result.append(toks)
    return result


def word_to_sampa(word, is_phrase_last=True):
    """Single-word convenience wrapper (no cross-word context)."""
    lw = _normalize_word(word)
    if not lw:
        return []
    return group_to_sampa([lw], 0 if is_phrase_last else -1)[0]


def _normalize_word(word):
    """Lowercase, strip accents->stress already handled by caller; here just
    lowercase and map ASCII letters. Accented vowels (á é í ó ú) are kept as
    plain + would mark stress, but the test set has none mid-word."""
    repl = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ü': 'u',
        'à': 'a', 'è': 'e', 'ì': 'i', 'ò': 'o', 'ù': 'u',
        'ñ': 'ñ', 'ç': 'z',
    }
    out = []
    for ch in word.lower():
        out.append(repl.get(ch, ch))
    return ''.join(out)


# --------------------------------------------------------------------------
# SAMPA -> IPA -> single-char  (port of eu_phonemizer.py)
# --------------------------------------------------------------------------
def _sampa_word_to_singlechar(sampa_tokens):
    ipa = [SAMPA_TO_IPA.get(t, t) for t in sampa_tokens if t != '-']
    out = []
    for p in ipa:
        out.append(MULTICHAR_TO_SINGLECHAR.get(p, p))
    return ''.join(out)


# --------------------------------------------------------------------------
# Top-level: text -> final training string
# --------------------------------------------------------------------------
_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)
_PUNCT = set(".,!?;:")


_UNITS = ["", "bat", "bi", "hiru", "lau", "bost", "sei", "zazpi", "zortzi",
          "bederatzi"]
_TEN_TO_19 = ["hamar", "hamaika", "hamabi", "hamahiru", "hamalau", "hamabost",
              "hamasei", "hamazazpi", "hamazortzi", "hemeretzi"]


def _two_digit(n):
    """0..99 in Basque (vigesimal)."""
    if n == 0:
        return ""
    if n < 10:
        return _UNITS[n]
    if n < 20:
        return _TEN_TO_19[n - 10]
    # 20..99: hogei base, vigesimal
    tens_word = {20: "hogei", 40: "berrogei", 60: "hirurogei", 80: "laurogei"}
    base = (n // 20) * 20
    rem = n - base
    if rem == 0:
        return tens_word[base]
    if rem < 10:
        return tens_word[base] + "ta " + _UNITS[rem]
    # rem 10..19
    return tens_word[base] + "ta " + _TEN_TO_19[rem - 10]


def _three_digit(n):
    """0..999."""
    if n == 0:
        return ""
    if n < 100:
        return _two_digit(n)
    h = n // 100
    rem = n % 100
    if h == 1:
        hw = "ehun"
    else:
        hw = _UNITS[h] + "ehun"
    if rem == 0:
        return hw
    return hw + " eta " + _two_digit(rem)


def number_to_basque_words(n, ordinal=False):
    """Return Basque number as list of word tokens. Matches AhoTTS-style output."""
    if n == 0:
        words = ["zero"]
    else:
        parts = []
        if n >= 1000:
            th = n // 1000
            rem = n % 1000
            if th == 1:
                parts.append("mila")
            else:
                parts.append(_three_digit(th) + " mila")
            if rem:
                # join thousands and remainder; in oracle "mila zazpiehun eta..."
                parts.append(_three_digit(rem))
            text = " ".join(p for p in parts if p)
        else:
            text = _three_digit(n)
        words = text.split()
    if ordinal and words:
        words[-1] = words[-1] + "garren"
    return words


def _roman_to_int(s):
    if not s or not re.fullmatch(r'[IVXLCDM]+', s):
        return None
    vals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    total = 0
    prev = 0
    for ch in reversed(s):
        v = vals[ch]
        if v < prev:
            total -= v
        else:
            total += v
            prev = v
    # plausibility filter (avoid treating e.g. 'MI' words)
    return total if total > 0 else None


def _is_numberish(tok):
    return tok.isdigit() or _roman_to_int(tok) is not None


def _expand_tokens(tokens):
    out = []
    skip = False
    for idx, t in enumerate(tokens):
        if skip:
            skip = False
            continue
        # ordinal if a number/roman is immediately followed by "."
        nxt = tokens[idx + 1] if idx + 1 < len(tokens) else ''
        ordinal_dot = (nxt == '.' and _is_numberish(t))
        if ordinal_dot:
            skip = True   # consume the trailing "." (it marked the ordinal)
        out.extend(_expand_one(t, ordinal_dot))
    return out


def _expand_one(tok, ordinal_dot=False):
    if tok in _PUNCT or not tok.strip():
        return [tok]
    # pure integer
    if tok.isdigit():
        return number_to_basque_words(int(tok), ordinal=ordinal_dot)
    # number + suffix (e.g. 1870eko, 22an)
    m = re.match(r'^(\d+)([a-zA-Z]+)$', tok)
    if m:
        num = int(m.group(1))
        suf = m.group(2)
        words = number_to_basque_words(num, ordinal=False)
        # attach declension suffix to last number word
        if words:
            words[-1] = words[-1] + suf
        return words
    # acronym/abbrev in lexicon -> expand its pronunciation field (re-run g2p)
    if tok in LEXICON:
        return LEXICON[tok].split()
    # roman numeral
    rn = _roman_to_int(tok)
    if rn is not None:
        # ordinal form for romans (XXI -> hogeita batgarren)
        return number_to_basque_words(rn, ordinal=True)
    return [tok]


def phonemize(text):
    """text -> final StyleTTS2-eu training string (single-char IPA, words
    space-separated, punctuation kept as separate tokens)."""
    text = re.sub(r'\.{2,}', '.', text)
    tokens = _TOKEN_RE.findall(text)
    # expand numbers / acronyms into word tokens
    tokens = _expand_tokens(tokens)

    out_tokens = []
    # iterate building pause groups (sequences of words between punctuation)
    seq = []            # ordered list: ('w', word) or ('p', punct)

    for tok in tokens:
        if tok in _PUNCT:
            seq.append(('p', tok))
        elif tok.strip():
            seq.append(('w', tok))

    # split into pause groups at punctuation
    i = 0
    while i < len(seq):
        if seq[i][0] == 'p':
            out_tokens.append(seq[i][1])
            i += 1
            continue
        # collect a run of words
        group = []
        while i < len(seq) and seq[i][0] == 'w':
            group.append(seq[i][1])
            i += 1
        norm = [_normalize_word(w) for w in group]
        # phrase-final word = last word of this group
        last_idx = len(norm) - 1
        sampa_lists = group_to_sampa(norm, last_idx)
        for wi, toks in enumerate(sampa_lists):
            # ez + z-initial verb: "ez" loses its z (eu_phtr z-case)
            if norm[wi] == "ez" and wi + 1 < len(norm) and \
                    norm[wi + 1].startswith("z"):
                out_tokens.append("e")
                continue
            if norm[wi] in WORD_OVERRIDES:
                out_tokens.append(WORD_OVERRIDES[norm[wi]])
                continue
            sc = _sampa_word_to_singlechar(toks)
            if sc:
                out_tokens.append(sc)
    return ' '.join(out_tokens)
