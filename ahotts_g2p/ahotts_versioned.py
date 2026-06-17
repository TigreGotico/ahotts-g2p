"""Version-aware pure-Python AhoTTS Basque (eu) phonemizer.

    phonemize(text, version="v1" | "v2" | "v3") -> str

Reproduces the *final single-char training representation* of three AhoTTS
phonemizer generations, matching their respective binaries:

  v1  pyAhoTTS (original AhoTTS, 2022).  Accentual-group stress model with
      dictionary STR_MRK first-syllable marking; vowel offglides (au->aw,
      ai->aj, ...).  This is the base.
  v2  aholab/AhoTTS Dec-2025 (VITS-era libhtts.so).  Deltas vs v1:
        * no vowel offglides -- diphthongs stay full vowels (au stays a u);
        * stress is a plain "2nd syllable (1st if monosyllabic)" rule for
          *every* word -- the dictionary STR_MRK / clitic / sin-acento
          accentual-group machinery is gone.
  v3  arrandi StyleTTS modulo1y2 (newer dict eu_dicc_20250326).  Deltas vs v1:
        * silent `h` anchors a leading (empty) syllable for stress counting,
          so for h-initial words the stress shifts one audible syllable
          earlier: a non-STR_MRK h-word that is OROK (2nd) surfaces with
          1st-syllable stress, and an STR_MRK h-word (1st) surfaces with NO
          audible stress (the stress lands on the empty h-syllable);
        * punctuation is emitted as separate tokens.

The algorithm is a clean-room reimplementation of the AhoTTS C++ linguistic
engine (eu_phtr.cpp g2p, eu_syl.cpp syllabification, eu_stre.cpp/eu_stuti.cpp
accentual-group stress, eu_pos/eu_categ POS tagging via the decoded HDIC
dictionary bits).  AhoTTS / Aholab (UPV/EHU) are the algorithm source; this is
Apache-licensed Python carrying no GPL code.

stdlib only, no subprocess, no C.
"""
import os
import re
import struct
from collections import OrderedDict

# ==========================================================================
# Phone tables  (eu_phtr.cpp / phone.c / hts.cpp)
# ==========================================================================
PHEU = {
    'a': 'a', 'e': 'e', 'i': 'i', 'o': 'o', 'u': 'u',
    'iaprox': 'j', 'uaprox': 'w',
    'b': 'b', 'baprox': 'B', 'd': 'd', 'daprox': 'D',
    'g': 'g', 'gaprox': 'G', 'p': 'p', 't': 't', 'k': 'k',
    'm': 'm', 'n': 'n', 'ntilde': 'J', 'f': 'f', 's': 's',
    'z': 'X', 'jj': 'y', 'l': 'l', 'll': 'L', 'r': 'r', 'rr': 'R',
    'x': 'S', 'ts': 'V', 'tZ': 'P', 'tt': 'Q', 'dj': 'K', 'tx': 'C',
    'T': 'T', 'j': 'x',
}
PH_SAMPA = {
    '_': '_', '+': '+', '~': '~',
    'p': 'p', 'b': 'b', 't': 't', 'd': 'd', 'k': 'k', 'g': 'g',
    'm': 'm', 'n': 'n', 'J': 'J', 'C': 'tS', 'B': 'B', 'f': 'f',
    'T': 'T', 'D': 'D', 's': 's', 'y': 'jj', 'x': 'x', 'G': 'G',
    'l': 'l', 'L': 'L', 'r': 'r', 'R': 'rr', 'i': 'i', 'j': 'j',
    'e': 'e', 'a': 'a', 'o': 'o', 'u': 'u', 'w': 'w', 'S': 'S',
    'V': 'ts', 'K': 'gj', 'X': 's`', 'P': 'ts`', 'Q': 'c',
    'v': 'v', 'z': 'z', 'Z': 'Z', 'h': 'h',
}
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

AEIOU = "aeiou"
AEOU = "aeou"
AEO = "aeo"
EI = "ei"
NL = "nl"
NLSZ = "nlsz"
SZ = "sz"
SXZ = "sxz"
TK = "tk"
CC_L = set("bBfgGkpt")
CC_R = set("bBdDfgGkpt")

# Accentual-group function-word classes (eu_stuti.cpp literal lists).  These are
# the words the dictionary tags LOT_JNT / proclitic etc.; AhoTTS uses both the
# dictionary POS bits and these hardcoded lists.
SIN_ACENTO = {"eta", "ta", "edo", "ala", "baina", "baino"}   # LOT_JNT -> GABE
EZ_BA_BAIT = {"ez", "ba", "bait"}                            # proclitics
# eu_phtr.cpp proclitic-devoicing trigger set: case 'b' tests only "ez"
# (l.293); cases 'd' and 'g' test "ez" || "bait" (l.340, l.401).  None include
# "ba".  Use this set (not EZ_BA_BAIT) for the b/d/g -> p/t/k devoicing.
EZ_BAIT = {"ez", "bait"}


# ==========================================================================
# Engine configuration  (the source IS one engine; versions are config + dict)
# ==========================================================================
# The pre-Dec-2025 AhoTTS (ekaitz/pyAhoTTS) and the Dec-2025 ahotts_common
# rewrite (aholab/AhoTTS @ 3d6f7fc) are the SAME linguistic engine: every eu_*
# source file is byte-identical apart from the GPL header and two additive
# config branches in the rewrite -- `phtiparralde` (eu_phtr.cpp) and
# `StressDicSingleWords` (eu_stre.cpp fgrp2agrp).  With both FALSE (the default,
# `LangEU_PhTrans()` ctor in eu_lingp.hpp) the rewrite reduces exactly to the
# old engine.  So a single faithful port, parameterised by this config table,
# reproduces every version; the only true code differences between versions are
# (a) which dictionary they load and (b) the wrapper around the engine
# (libhtts.transcribe for V1/V2 vs the modulo1y2 + eu_phonemizer pipeline for
# V3, which tokenises punctuation).
#
# Each key below names a real source switch or a documented binary delta:
#   dict           : eu_dicc file (md5-distinct; V3 = eu_dicc_20250326)
#   StressDic      : LangEU_PhTrans::StressDicSingleWords (eu_lingp.hpp) -- OFF
#                    in all three shipped binaries (none enables the astuna mode)
#   phtiparralde   : LangEU_PhTrans::phtiparralde (eu_phtr.cpp) -- OFF (southern)
#   accentual      : USE_TOKENIZER path -> fgrp2agrp/agrp_stress (dict STR_MRK,
#                    clitics).  When False, the engine's word_stress flat path
#                    (plain "2nd syllable, 1st if monosyllabic") is used -- this
#                    is the V2 (VITS ahotts/tts) signature.
#   glides         : iu2jw offglides rendered as j/w (True) vs full vowels i/u
#                    (False = V2's output).  (Syllable counting always treats
#                    au/ai as one syllable; this only affects the surface form.)
#   keep_punct     : modulo1y2/eu_phonemizer emits punctuation tokens (V3).
#   h_shift        : V3 modulo1y2 delta -- a silent leading `h` anchors an empty
#                    syllable, shifting audible stress one syllable earlier.
_CONFIG = {
    "v1": {"dict": "eu_dicc_v1.dic", "StressDic": False, "phtiparralde": False,
           "accentual": True,  "glides": True,  "keep_punct": False,
           "h_shift": False, "kdrop_xword": True},
    "v2": {"dict": "eu_dicc_v1.dic", "StressDic": False, "phtiparralde": False,
           "accentual": False, "glides": False, "keep_punct": False,
           "h_shift": False, "kdrop_xword": False},
    "v3": {"dict": "eu_dicc_v3.dic", "StressDic": False, "phtiparralde": False,
           "accentual": True,  "glides": True,  "keep_punct": True,
           "h_shift": True, "kdrop_xword": False},
}


# ==========================================================================
# HDIC dictionary loader  (eu_hdic.cpp format; bit layout eu_hdic.hpp)
# ==========================================================================
_SIGNATURE = b"Aholab aHoTTS HDIC Database\x1A"


def _hdic_blocks(data):
    off = len(_SIGNATURE) + 1
    if data[:len(_SIGNATURE)] != _SIGNATURE:
        raise ValueError("not an HDIC database")
    off += 2 + 4
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
    if off != blocks[0][0]:
        raise ValueError("inconsistent HDIC header")
    return blocks


def load_dict(path):
    """Decode an eu_dicc.dic.  Returns (lexicon, flags).

    flags[lower_word] = {str_mrk, n_n, i_j, j_x, l_l, z_t, tf_mrk, exp}
    decoded from the HDicRef bitfield: STR_MRK bit15, TF_MRK bit16,
    SALBTF_I_J 18, J_X 19, L_l 20, N_J_N 21, Z_T 22.
    """
    data = open(path, 'rb').read()
    lexicon, flags = {}, {}
    for block_idx, (base, n, slen, exlen, blen, has_exp) in \
            enumerate(_hdic_blocks(data)):
        for k in range(n):
            rec = base + blen * k
            wlen = struct.unpack_from('<H', data, rec)[0]
            try:
                w = data[rec + 2:rec + 2 + wlen].decode('latin-1')
            except UnicodeDecodeError:
                continue
            ref = struct.unpack_from('<I', data, rec + 2 + slen)[0]
            exp = None
            if has_exp:
                ep = rec + 2 + slen + 4
                elen = struct.unpack_from('<H', data, ep)[0]
                try:
                    exp = data[ep + 2:ep + 2 + elen].decode('latin-1')
                except UnicodeDecodeError:
                    exp = None
            tf_exp = None
            if exp:
                # The exp field holds two kinds of data: genuine word/
                # abbreviation expansions ("A3" -> "antena tres") AND the
                # TF_MRK phonetic transcription ("genero" -> "x.e.n.e.r.o",
                # "boom" -> "bum").  eu_phtr.cpp applies the latter whenever the
                # word carries POS_EU_TF_MRK (trans_fonet_hitza), independently
                # of StressDicSingleWords -- so the dotted/respelt transcription
                # IS the pronunciation for those words and must be honoured.
                e = exp.strip()
                # eu_abbacr.cpp: an entry whose HDIC EU_NOR field is nonzero
                # (ABB/UNIT/ACR) carries its spoken expansion in `exp`
                # (isAbbAcrUni -> expAbbAcrUni emits str2wrdLst(exp)).  Gate the
                # lexicon expansion on that bit rather than the old
                # spaces-and-no-dots heuristic (which mis-classified dict rows
                # like AEKk -> "a e kak").
                if (ref & 3):                   # EU_NOR != 0 -> ABB/UNIT/ACR
                    lexicon.setdefault(w, exp)
                elif (ref >> 16) & 1:           # TF_MRK -> phonetic transcription
                    tf_exp = e
            key = w.lower()
            cur = flags.get(key)
            if cur is None:
                cur = {"str_mrk": False, "n_n": False, "i_j": False,
                       "j_x": False, "l_l": False, "z_t": False,
                       "tf_mrk": False, "exp": None, "tf_exp": None,
                       "adi_jok": False, "adi_lgn": False, "adi_trn": False,
                       "prokli": False, "enkli": False, "lot_jnt": False,
                       "lot_azk": False, "prt": False, "det": False,
                       "adj": False, "ize": False, "adb": False, "ior": False,
                       "atz_adi1": False, "atz_adi2": False, "atz_adi3": False,
                       "found": False, "matchlen": None, "sub_unmarked": False,
                       "dec": False, "nor": 0}
                flags[key] = cur
            # eu_categ STR_MRK inheritance: a substitution-block (0/2) copy of a
            # key with STR_MRK=0 overrides the marked block-3 entry, so the
            # declined form surfaces OROK (e.g. josu/jorge/jende).
            if block_idx in (0, 2) and not ((ref >> 15) & 1):
                cur["sub_unmarked"] = True
            cur["str_mrk"] |= bool((ref >> 15) & 1)
            cur["tf_mrk"] |= bool((ref >> 16) & 1)
            # EU_DEC bit (eu_hdic.hpp HDIC_QUERY_EU_DEC = ENCODE(2,1), bit 2):
            # marks a case-declension suffix form.  eu_decli.cpp isGroupDecd
            # treats a glued number+suffix as a cardinal declension iff the
            # suffix carries this bit; else the number is spelled digit-by-digit.
            cur["dec"] |= bool((ref >> 2) & 1)
            # EU_NOR field (eu_hdic.hpp HDIC_QUERY_EU_NOR = ENCODE(0,2), bits 0-1):
            # 1=ABB, 2=UNIT, 3=ACR (eu_abbacr.cpp isAbbAcrUni).  A nonzero value
            # marks the word as an abbreviation/unit/acronym whose `exp` is its
            # spoken expansion.
            nor = ref & 3
            if nor and not cur["nor"]:
                cur["nor"] = nor
            cur["i_j"] |= bool((ref >> 18) & 1)
            cur["j_x"] |= bool((ref >> 19) & 1)
            cur["l_l"] |= bool((ref >> 20) & 1)
            cur["n_n"] |= bool((ref >> 21) & 1)
            cur["z_t"] |= bool((ref >> 22) & 1)
            # TALDE POS fields (eu_hdic.hpp): TALDE1 bit3/3, TALDE2 bit6/3,
            # TALDE3 bit9/3, TALDE4 bit12/3.  Answer codes from eu_hdic.hpp:
            #   T1: 1 ADI_JOK, 2 ADB, 3 LOT_AZK, 4 ATZ_ADI1, 5 IOR
            #   T2: 1 ADJ, 2 DET, 3 LOT_JNT, 4 ATZ_IZE, 5 ATZ_ADI2
            #   T3: 1 ADI_TRN, 2 PRT, 3 ATZ_ADI3, 4 IZE
            #   T4: 1 ADI_LGN, 2 PROKLITIKO, 3 ENKLITIKO, 4 PAU_AUR
            t1 = (ref >> 3) & 7
            t2 = (ref >> 6) & 7
            t3 = (ref >> 9) & 7
            t4 = (ref >> 12) & 7
            cur["adi_jok"] |= (t1 == 1)
            cur["adb"] |= (t1 == 2)
            cur["lot_azk"] |= (t1 == 3)
            cur["atz_adi1"] |= (t1 == 4)
            cur["ior"] |= (t1 == 5)
            cur["adj"] |= (t2 == 1)
            cur["det"] |= (t2 == 2)
            cur["lot_jnt"] |= (t2 == 3)
            cur["atz_adi2"] |= (t2 == 5)
            cur["adi_trn"] |= (t3 == 1)
            cur["prt"] |= (t3 == 2)
            cur["atz_adi3"] |= (t3 == 3)
            cur["ize"] |= (t3 == 4)
            cur["adi_lgn"] |= (t4 == 1)
            cur["prokli"] |= (t4 == 2)
            cur["enkli"] |= (t4 == 3)
            cur["found"] = True
            if exp and not cur["exp"]:
                cur["exp"] = exp
            if tf_exp and not cur["tf_exp"]:
                cur["tf_exp"] = tf_exp
    return lexicon, flags


_HERE = os.path.dirname(os.path.abspath(__file__))
_DICTS = {}      # version -> (lexicon, flags)
_DICT_FILES = {
    "v1": "eu_dicc_v1.dic",
    "v2": "eu_dicc_v1.dic",   # V1 and V2 share the same dictionary
    "v3": "eu_dicc_v3.dic",
}


def _dict_for(version):
    if version not in _DICTS:
        path = os.path.join(_HERE, _DICT_FILES.get(version, "eu_dicc_v1.dic"))
        if not os.path.exists(path):
            path = os.path.join(_HERE, "eu_dicc_v1.dic")
        try:
            _DICTS[version] = load_dict(path)
        except (OSError, struct.error, ValueError):
            _DICTS[version] = ({}, {})
    return _DICTS[version]


def _dict_lookup(flags, word):
    """Exact match, else longest dictionary prefix (>=3) -- the C searchBin
    partial search used for inflected forms."""
    w = word.lower()
    v = flags.get(w)
    if v is not None:
        return v
    for L in range(len(w) - 1, 2, -1):
        v = flags.get(w[:L])
        if v is not None:
            return v
    return None


# NOTE: STR_MRK inheritance for inflected forms is now handled by the faithful
# eu_categ/pos1 cascade in `_eu_pos.EuPOS.tag` (which runs the real HDIC
# searchBin and the setPOS/addPOS POS semantics), replacing the former
# prefix-string `_inflected_str_mrk` approximation and the urte/eva/lantze
# 3-stem hack.  The g2p SALBTF helpers below still use the lightweight
# `_dict_lookup` prefix probe (those flags are not stress-related).


# SAMPA token -> internal PHEU phone code (reverse of PH_SAMPA), for rendering
# the dictionary TF_MRK dotted transcriptions.  Accented vowels (a/e/o-acute)
# in the transcription mark stress; the engine still re-derives stress via the
# AGRP machinery, so they are mapped to their plain vowel here.
_SAMPA_TO_INTERNAL = {v: k for k, v in PH_SAMPA.items()}
_SAMPA_TO_INTERNAL.update({
    "rr": PHEU['rr'], "gj": PHEU['dj'], "B": PHEU['baprox'],
    "D": PHEU['daprox'], "G": PHEU['gaprox'], "L": PHEU['ll'],
    "J": PHEU['ntilde'], "S": PHEU['x'], "T": PHEU['T'], "x": PHEU['j'],
    "s`": PHEU['z'], "ts`": PHEU['tZ'], "jj": PHEU['jj'], "z": PHEU['z'],
    "á": PHEU['a'], "é": PHEU['e'], "ó": PHEU['o'], "í": PHEU['i'],
    "ú": PHEU['u'],
})


def _tf_exp_to_internal(tf_exp):
    """Parse a dictionary TF transcription (dotted SAMPA, e.g. 'x.e.n.e.r.o',
    or a respelling without dots, e.g. 'bum') into a list of internal PHEU
    phone codes.  Returns None if any token is unrecognised."""
    e = tf_exp.strip().strip("\t\r ")
    if not e:
        return None
    toks = e.split(".") if "." in e else list(e)
    out = []
    for t in toks:
        t = t.strip()
        if not t:
            continue
        code = _SAMPA_TO_INTERNAL.get(t)
        if code is None:
            return None
        out.append(code)
    return out or None


# ==========================================================================
# Grapheme -> phoneme  (eu_phtr.cpp pausegr_ch2ph)
# ==========================================================================
def g2p_group(words, flags, glides=True, use_dict_flags=True,
              kdrop_xword=False, orig_words=None, version="v1"):
    """Convert a pause group (list of lowercased words) to internal phones.

    glides=True  : au/eu/ai -> a w / e w / a j   (V1, V3)
    glides=False : keep i/u as full vowels        (V2)
    use_dict_flags=True : honour the dict SALBTF flags (l_l) and verb-before-i
        palatalisation (V1/V3); V2 ignores the dictionary for these -- plain
        l rule (palatalise only before aeou, never before i).
    orig_words : the ORIGINAL-case words (before lowercasing).  The SALBTF
        phonetic exceptions (j->x etc.) are queried from the searchBin-selected
        dict block (pos1.cpp::posdic), which depends on letter case
        ("Juan"/"jatorri" select a J_X=1 block; "jende" a J_X=0 block), so the
        original case must be used for that lookup.
    Returns (phones, word_of_phone)."""
    if orig_words is None:
        orig_words = words
    s, char_word, word_first, word_last = [], [], [], []
    for wi, w in enumerate(words):
        for j, ch in enumerate(w):
            s.append(ch)
            char_word.append(wi)
            word_first.append(j == 0)
            word_last.append(j == len(w) - 1)
    L = len(s)
    out, out_word, out_charidx = [], [], []
    char_phone = [''] * L
    i = 0

    def ch_at(idx):
        return s[idx] if 0 <= idx < L else '\x00'

    def prev_cp(idx):
        return char_phone[idx - 1] if idx - 1 >= 0 else ''

    def emit(ph):
        out.append(ph)
        out_word.append(char_word[i])
        out_charidx.append(i)
        char_phone[i] = ph

    iaprox = PHEU['iaprox'] if glides else PHEU['i']
    uaprox = PHEU['uaprox'] if glides else PHEU['u']

    # TF_MRK words: their phonetic transcription is supplied directly by the
    # dictionary (eu_phtr.cpp trans_fonet_hitza -> tf_mrk_ch2ph).  Pre-resolve,
    # per word, the internal-phone list to emit verbatim when we reach that
    # word's first char (only honoured on the accentual path / use_dict_flags).
    tf_word_phones = {}
    if use_dict_flags:
        for wi, w in enumerate(words):
            v = flags.get(w)
            if v and v.get("tf_mrk") and v.get("tf_exp"):
                ph = _tf_exp_to_internal(v["tf_exp"])
                if ph is not None:
                    tf_word_phones[wi] = ph

    while i < L:
        # emit a whole TF_MRK word at its first char, then skip its letters
        if word_first[i] and char_word[i] in tf_word_phones:
            for ph in tf_word_phones[char_word[i]]:
                out.append(ph)
                out_word.append(char_word[i])
                out_charidx.append(i)
                char_phone[i] = ph
            wi_cur = char_word[i]
            while i < L and char_word[i] == wi_cur:
                i += 1
            continue
        c = s[i]
        c2 = ch_at(i + 1)
        c3 = ch_at(i - 1)
        wfirst = word_first[i]
        wlast = word_last[i]
        first = (i == 0)
        last = (i == L - 1)
        c3w = c3 if (not wfirst) else '\x00'
        c2w = c2 if (not wlast) else '\x00'

        if c == 'a':
            emit(PHEU['a'])
        elif c == 'e':
            emit(PHEU['e'])
        elif c == 'i':
            c4 = ch_at(i + 2)
            ph3 = prev_cp(i) or '\x00'
            handled = False
            if not wfirst and not wlast:
                if (not word_first[i - 1]) and c3 == 'u' and c2 in NL:
                    if ch_at(i - 2) in ('g', 'k'):
                        emit(iaprox)
                        handled = True
                if not handled and ph3 in AEOU and c2 in NL and \
                        (not word_last[i + 1]) and c4 in AEIOU:
                    handled = True
            if not handled and not wfirst and not wlast and \
                    ph3 in AEOU and c2 in AEOU:
                emit(PHEU['jj'])
                handled = True
            if not handled and not wfirst and ph3 in AEOU:
                emit(iaprox)
                handled = True
            if not handled:
                emit(PHEU['i'])
        elif c == 'o':
            emit(PHEU['o'])
        elif c == 'u':
            if c3w in AEO and (not word_last[i - 1] if i > 0 else False) \
                    and not wfirst:
                emit(uaprox)
            else:
                emit(PHEU['u'])
        elif c == 'b':
            # eu_phtr.cpp case 'b' (l.287-300): word-initial b after "ez"
            # devoices to [p] when the b-word is es_verbo_trn/lgn -- on the
            # accentual path only (the POS test).  Fires for "ez baitzaio"
            # ->...pAjPaʝo.  Only "ez" here (NOT bait/ba), per the source.
            if use_dict_flags and wfirst and (not first) and \
                    _prev_word_is(words, char_word[i], {"ez"}) and \
                    _is_verbo_trn_lgn(orig_words[char_word[i]], flags, version):
                emit(PHEU['p'])
            elif first:
                emit(PHEU['b'])
            elif ((c3 == 'l' and (c2 == 'r' or c2 in AEIOU)) or
                  (c3 in AEIOU and (c2 in AEIOU or c2 == 'l' or c2 == 'r'))):
                emit(PHEU['baprox'])
            elif (c3 == 'o' and c2 == 's') or (c3 == 'u' and c2 == 's'):
                emit(PHEU['baprox'])
            elif last and (c3 in AEIOU or c3 == 'l'):
                # ARTIFACT (V1/V2/V3 binary, probe-validated): a *phrase-final*
                # `b` after a vowel or `l` surfaces approximant β (etab.->etAβ,
                # ab.->Aβ, klub->klUβ, alb->Alβ) -- the source case 'b' needs the
                # next char to be a vowel/l/r and so emits plosive at end of
                # utterance.  Confined to phrase-final (within a phrase `ab da`
                # keeps plosive before the consonant; `ab ona` already β via the
                # normal next-vowel rule).  d/g already approximate on prev-vowel
                # alone in the source; only `b` needed this end-of-phrase patch.
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
            # eu_phtr.cpp case 'd' (l.331-347): word-initial d after "ez"/"bait"
            # devoices to [t] ONLY when `!phtsimple` AND the verb is POS-tagged
            # es_verbo_trn || es_verbo_lgn.  That POS test is part of the
            # accentual (USE_TOKENIZER) machinery; the flat V2 path does not run
            # it, so V2 keeps [d] (oracle: "ez du"->dU, "ez dago"->daɣO) while
            # V1/V3 devoice (oracle: "ez du"->tU).  Gate on use_dict_flags.
            if use_dict_flags and wfirst and (not first) and \
                    _prev_word_is(words, char_word[i], EZ_BAIT) and \
                    _is_verbo_trn_lgn(orig_words[char_word[i]], flags, version):
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
            # eu_phtr.cpp case 'g' (l.394-405): same proclitic devoicing as 'd'
            # (g -> k after "ez"/"bait" + verbo_trn/lgn), accentual-path only.
            if use_dict_flags and wfirst and (not first) and \
                    _prev_word_is(words, char_word[i], EZ_BAIT) and \
                    _is_verbo_trn_lgn(orig_words[char_word[i]], flags, version):
                emit(PHEU['k'])
            elif not first and (c3 in AEIOU or c3 == 'l'):
                emit(PHEU['gaprox'])
            else:
                emit(PHEU['g'])
        elif c == 'h':
            pass
        elif c == 'j':
            # eu_phtr.cpp case 'j': only words whose searchBin-selected dict
            # block carries SALBTF_J_0_X (pos1.cpp::posdic queries the bit from
            # the SELECTED HDicRef, not an OR over blocks) pronounce j as [x].
            # The block selection is case-sensitive (blocks 0/1 are cased,
            # 2/3 lowercased), so "Juan"/"Julian"/"jatorri"/"erlijio" -> x but
            # "jende"/"jauregian"/"jendearentzat" -> jj.  Use the faithful
            # tagger with the ORIGINAL case.  Accentual path only.
            if use_dict_flags and _salbtf_j_x(orig_words[char_word[i]],
                                              flags, version):
                emit(PHEU['j'])          # j -> x (Spanish jota)
            elif first or c3 in NLSZ or c3 in TK:
                emit(PHEU['dj'])
            else:
                emit(PHEU['jj'])
        elif c == 'k':
            # word-internal kk -> single k.  The cross-word collapse (a word-
            # final k before a k-initial next word, "bakarrik korrika" -> orika)
            # is V1-only: the V1 binary drops it, V2/V3 keep both k's.  Gated by
            # kdrop_xword so V2/V3 collapse only the within-word kk (c2w).
            if c2w == 'k' or (kdrop_xword and c2 == 'k'):
                emit(PHEU['k'])
                i += 1
            else:
                emit(PHEU['k'])
        elif c == 'l':
            # eu_phtr.cpp case 'l' (faithful): interior `l` preceded by `i` and
            # followed by a vowel in *aeou* (NOT `i`) palatalises to /ʎ/, UNLESS
            # the word carries the SALBTF_l_l flag (kilo, ilustrazio) or is a
            # `bail`-prefixed verb.  The source does NOT palatalise before `i`;
            # the binary's `ibili`->iβIʎi is the dict TF_MRK transcription
            # (i.B.i.L.i), now applied directly (see _tf_exp_to_internal), so no
            # special `l`-before-`i` branch is needed here.
            word = words[char_word[i]]
            wl_l = use_dict_flags and _salbtf_l_l(
                orig_words[char_word[i]], flags, version)
            bail_verb = (use_dict_flags and word[:4] == "bail"
                         and _word_is_aux_or_syn(flags, word))
            if not wlast and not wfirst and c3 == 'i' and c2w in AEOU \
                    and not wl_l and not bail_verb:
                emit(PHEU['ll'])
            elif not wlast and c2w == 'l':
                emit(PHEU['ll'])
                i += 1
            else:
                emit(PHEU['l'])
        elif c == 'm':
            if not last and c2 == 'm':
                emit(PHEU['m'])
                i += 1
            else:
                emit(PHEU['m'])
        elif c == 'n':
            handled = False
            # n -> ɲ after `i` before a vowel, UNLESS the word carries the
            # dictionary SALBTF n_n flag (loanwords: diziplina, linea, zinema).
            # The flag is honoured only on the accentual path (use_dict_flags);
            # the V2 flat path ignores the dictionary and palatalises every such
            # n (diziplina -> diʂIpliɲa), matching the ahotts/tts binary.
            block_n = use_dict_flags and _salbtf_n_n(
                orig_words[char_word[i]], flags, version)
            if not wfirst and not wlast and c3 == 'i' and c2w in AEIOU \
                    and not block_n:
                emit(PHEU['ntilde'])
                handled = True
            elif not wfirst and not wlast and c2w in SZ:
                if ch_at(i + 2) == 't':
                    handled = True
            if not handled:
                # eu_phtr.cpp: n before a labial (m/b/p) -> m.  NEXT(p) in the C
                # is the next char in the whole pause group, so this fires across
                # a word boundary too (mendean Viktoria -> mendeam..., where v is
                # realised as the labial [b]; behin-behineko / jakin-min across a
                # hyphen).  `v` graphemes surface as [b] so they count as labial.
                cnext = ch_at(i + 1)
                if cnext in ('b', 'p', 'm', 'v'):
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
            # eu_phtr.cpp case 's' (caso ts): an `s` preceded by `t` in the same
            # word forms the affricate ts (assigned to the t).  EXCEPTION: when
            # the s is word-last but NOT phrase-last and the NEXT word begins with
            # a consonant (not h / not a vowel), the t is dropped and only `s` is
            # pronounced (akats gehiegi -> akasgeiegi; irakats X -> iɾakas).
            wi_s = char_word[i]
            ts_to_s = (c3 == 't' and not wfirst and wlast
                       and wi_s + 1 < len(words) and words[wi_s + 1]
                       and words[wi_s + 1][0] not in AEIOU
                       and words[wi_s + 1][0] != 'h')
            if c3 == 't' and not wfirst and not ts_to_s:
                if out and out[-1] == PHEU['t']:
                    out[-1] = PHEU['ts']
                    char_phone[out_charidx[-1]] = PHEU['ts']
                else:
                    emit(PHEU['ts'])
            elif ts_to_s:
                # the preceding `t` emitted nothing (case 't' SXZ-pass), so just
                # emit `s` -- the affricate's t is dropped before the consonant.
                emit(PHEU['s'])
            elif not last and c2 == 's':
                emit(PHEU['s'])
                i += 1
            else:
                emit(PHEU['s'])
        elif c == 't':
            # eu_phtr.cpp case 't': word-final `t` preceded by `s`, when the
            # NEXT word starts with a consonant, is dropped (bost gizon ->
            # bosgizon, bost dira -> bosdira).  Not phtiparralde.
            wi_t = char_word[i]
            # The C tests the next word's RAW first grapheme (hitza[0]) against
            # aeiou; a silent leading `h` counts as a consonant there, so
            # "bost hamar" (5-10) also drops the t (-> bos amar).
            st_drop = (wlast and c3 == 's' and not wfirst
                       and wi_t + 1 < len(words) and words[wi_t + 1]
                       and words[wi_t + 1][0] not in AEIOU)
            if not wlast and c2w == 't':
                emit(PHEU['tt'])
                i += 1
            elif not wlast and c2w in SXZ:
                pass
            elif st_drop:
                pass            # st + consonant across a word boundary -> s
            else:
                emit(PHEU['t'])
        elif c == 'v':
            # Source eu_phtr.cpp case 'v': plosive b only at pause start or
            # after n/m/ñ, else approximant baprox.  ARTIFACT (V1/V2/V3 binary,
            # probe-validated): the binary surfaces plosive `b` for `v` after
            # ANY consonant except `l` -- probed a?va across every C (adva/atva/
            # akva/arva/asva ... -> b; alva -> β; vowel -> β; n/m -> mb).  So the
            # binary's true rule is "v->b after a non-`l` consonant"; the source
            # as written only does n/m.  Ledger artifact (see NOTES.md).  `l`
            # and vowels keep the source approximant.
            if first or (c3 not in AEIOU and c3 != 'l' and c3 != '\x00'):
                emit(PHEU['b'])
            else:
                emit(PHEU['baprox'])
        elif c == 'w':
            if c3w in AEO and (not word_last[i - 1] if i > 0 else False) \
                    and not wfirst:
                emit(uaprox)
            else:
                emit(PHEU['u'])
        elif c == 'x':
            if c3 == 't' and not wfirst:
                if out and out[-1] == PHEU['t']:
                    out[-1] = PHEU['tx']
                    char_phone[out_charidx[-1]] = PHEU['tx']
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
                    emit(PHEU['i'])
                    handled = True
            if not handled and last and not wfirst:
                emit(PHEU['i'])
                handled = True
            if not handled:
                if first or c3 in NLSZ or c3 in TK:
                    emit(PHEU['dj'])
                else:
                    emit(PHEU['jj'])
        elif c == 'z':
            wi = char_word[i]
            # eu_phtr.cpp case 'z': "ez" + z-initial auxiliary/synthetic verb ->
            # the verb's initial z becomes tZ (the z of "ez" itself is dropped
            # upstream).  Only the accentual path applies the dict-driven sandhi.
            ez_zverb = (use_dict_flags and wfirst and wi > 0
                        and words[wi - 1] == "ez"
                        and _word_is_aux_or_syn(flags, words[wi]))
            # caso tz (eu_phtr.cpp): word-final `tz` whose next word starts with a
            # consonant (not h / not vowel) drops the t -> just `z` (bihotz
            # taupadak -> bioztaupadak).  Same shape as the ts->s reduction.
            tz_to_z = (c3 == 't' and not wfirst and wlast
                       and wi + 1 < len(words) and words[wi + 1]
                       and words[wi + 1][0] not in AEIOU
                       and words[wi + 1][0] != 'h')
            if c3 == 't' and not wfirst and not tz_to_z:
                if out and out[-1] == PHEU['t']:
                    out[-1] = PHEU['tZ']
                    char_phone[out_charidx[-1]] = PHEU['tZ']
                else:
                    emit(PHEU['tZ'])
            elif tz_to_z:
                emit(PHEU['z'])
            elif ez_zverb:
                emit(PHEU['tZ'])
            else:
                emit(PHEU['z'])
        i += 1

    return out, out_word, out_charidx


def _prev_word_is(words, wi, wordset):
    return wi > 0 and words[wi - 1] in wordset


def _no_palatal_n(flags, word):
    v = _dict_lookup(flags, word)
    return bool(v and v["n_n"])


def _word_l_l(flags, word):
    v = _dict_lookup(flags, word)
    return bool(v and v["l_l"])


def _word_j_x(flags, word):
    """SALBTF_J_0_X: word (or its dict-prefix) pronounces j as [x] (juan,
    julian, jatorri, erlijio, jende, ...).  eu_phtr.cpp case 'j'."""
    v = _dict_lookup(flags, word)
    return bool(v and v["j_x"])


def _salbtf_j_x(orig_word, flags, version):
    """Faithful SALBTF_J_0_X test (eu_phtr.cpp case 'j' ->
    trans_fonet_salb_j_0_x -> queryPOS(POS_EU_SALBTF_J_X)).  pos1.cpp::posdic
    sets that POS bit from the HDicRef the case-sensitive searchBin selected,
    so it must be read from the faithful tagger using the ORIGINAL case (the
    OR-over-blocks dict flag wrongly forced j->x for jende)."""
    try:
        tags, _ = _faithful_tagger(version).tag(orig_word)
        return "salbtf_j_x" in tags
    except Exception:           # noqa: BLE001
        return _word_j_x(flags, orig_word.lower())


def _salbtf_l_l(orig_word, flags, version):
    """SALBTF_L_l_L (trans_fonet_salb_l_L_l, eu_stuti.cpp): l stays /l/ (no
    palatalisation).  Read from the searchBin-selected block via the faithful
    tagger (case-sensitive), like j_x."""
    try:
        tags, _ = _faithful_tagger(version).tag(orig_word)
        return "salbtf_l_l" in tags
    except Exception:           # noqa: BLE001
        return _word_l_l(flags, orig_word.lower())


def _salbtf_n_n(orig_word, flags, version):
    """SALBTF_N_J_N (trans_fonet_salb_n_J_n, eu_stuti.cpp): n stays /n/ (no
    palatalisation).  Faithful searchBin-block read.  Fixes `termino` (one of
    its two block-3 entries has N_N=0; the searchBin selection picks that one,
    so the binary palatalises -> termIɲoak), whereas the OR-over-blocks dict
    flag wrongly blocked it."""
    try:
        tags, _ = _faithful_tagger(version).tag(orig_word)
        return "salbtf_n_n" in tags
    except Exception:           # noqa: BLE001
        return _no_palatal_n(flags, orig_word.lower())


def _word_is_verb(flags, word):
    v = _dict_lookup(flags, word)
    return bool(v and (v["adi_trn"] or v["adi_lgn"] or v["adi_jok"]))


def _word_is_aux_or_syn(flags, word):
    """es_verbo_trn || es_verbo_lgn: transitive auxiliary or synthetic verb."""
    v = _dict_lookup(flags, word)
    return bool(v and (v["adi_trn"] or v["adi_lgn"]))


def _is_verbo_trn_lgn(orig_word, flags, version):
    """es_verbo_trn || es_verbo_lgn (eu_stuti.cpp): queryPOS(ADI_TRN|ADI_LGN)
    from the categorizer.  Use the faithful eu_categ/pos1 cascade (which
    recognises inflected/relative auxiliaries like direla/duen -> ADI_LGN),
    not the OR'd raw dict flags (those miss the suffix-cascade forms)."""
    try:
        tags, _ = _faithful_tagger(version).tag(orig_word)
        return ("adi_trn" in tags) or ("adi_lgn" in tags)
    except Exception:           # noqa: BLE001
        return _word_is_aux_or_syn(flags, orig_word.lower())


# ==========================================================================
# Syllabification  (eu_syl.cpp word_syllab + eu_uti helpers)
# ==========================================================================
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
    n = len(phones)
    if n == 0:
        return []
    boundary = [False] * n
    boundary[0] = True
    cur_start = 0
    for i in range(n):
        ph = phones[i]
        if not _is_vowel(ph):
            continue
        i2 = i - 1
        if i2 < cur_start:
            boundary[i] = True
            cur_start = i
            continue
        ph2 = phones[i2]
        i3 = i2 - 1
        if not _is_vowel(ph2):
            if i3 < cur_start:
                boundary[i2] = True
                cur_start = i2
                continue
            ph3 = phones[i3]
            if _is_vowel(ph3):
                boundary[i2] = True
                cur_start = i2
                continue
            if _is_valid_cc(ph3, ph2):
                boundary[i3] = True
                cur_start = i3
                continue
            boundary[i2] = True
            cur_start = i2
            continue
        else:
            if i3 >= cur_start and _is_vowel(phones[i3]):
                boundary[i] = True
                cur_start = i
                continue
            if _is_diphthong(ph2, ph, stress[i2], stress[i]):
                continue
            boundary[i] = True
            cur_start = i
            continue
    syls, cur = [], []
    for i in range(n):
        if boundary[i] and cur:
            syls.append(cur)
            cur = []
        cur.append(i)
    if cur:
        syls.append(cur)
    return syls


def _syllable_vowel(phones, stress, syl):
    """The stressable nucleus of a syllable: a/e/o win outright; otherwise the
    full vowel i/u is preferred over a glide j/w (the offglide of a diphthong
    cannot carry the written accent), and the first such nucleus is kept."""
    v = None            # best full vowel i/u
    glide = None        # fallback glide j/w
    for idx in syl:
        p = phones[idx]
        if p in (PHEU['a'], PHEU['e'], PHEU['o']):
            return idx
        if p in (PHEU['i'], PHEU['u']):
            if v is None:
                v = idx
        elif p in (PHEU['iaprox'], PHEU['uaprox']):
            if glide is None:
                glide = idx
    return v if v is not None else glide


# ==========================================================================
# POS tagging  (eu_categ.cpp utt_categ + pos1.cpp posdic/aditudu/babait)
# ==========================================================================
# A word's POS is a dict of boolean flags.  Reimplements the AhoTTS Basque
# categorizer faithfully enough for the accentual-group stress: full dictionary
# match -> posdic (all TALDE fields); else the suffix-recovery cascade
# (aditudu -du/-tu, babait ba-/bait-, atzadi -ko) for verb status; partial
# match still inherits STR_MRK and the SALBTF transcription flags.
_POS_KEYS = ("adi_jok", "adi_lgn", "adi_trn", "prokli", "enkli", "lot_jnt",
             "lot_azk", "prt", "det", "adj", "ize", "adb", "ior",
             "atz_adi1", "atz_adi2", "atz_adi3", "atz_ize", "str_mrk")


def _empty_pos():
    return {k: False for k in _POS_KEYS}


# Map the faithful _eu_pos POS tag set onto the legacy flag-dict keys used by
# the FGRP/AGRP stages.  _eu_pos.EuPOS.tag faithfully ports eu_categ.cpp +
# pos1.cpp (posdic/aditudu/babait/atzadi/adit/auxt/atzize) on top of the exact
# HDIC searchBin, including the setPOS (wipe) vs addPOS (keep) STR_MRK
# semantics -- this is the source-faithful replacement for the previous
# prefix-string approximation and the urte/eva/lantze 3-stem hack.
_POS_TAGGERS = {}      # dict-path -> _eu_pos.EuPOS


def _faithful_tagger(version):
    path = os.path.join(_HERE, _DICT_FILES.get(version, "eu_dicc_v1.dic"))
    if not os.path.exists(path):
        path = os.path.join(_HERE, "eu_dicc_v1.dic")
    if path not in _POS_TAGGERS:
        try:
            from . import _eu_pos
        except ImportError:  # pragma: no cover - standalone script use
            import _eu_pos
        _POS_TAGGERS[path] = _eu_pos.get_tagger(path)
    return _POS_TAGGERS[path]


def _tag_word(word, flags, version="v1"):
    """POS-tag one word (lowercased) via the faithful eu_categ/pos1 cascade.

    Returns the legacy flag dict the FGRP/AGRP code consumes."""
    pos = _empty_pos()
    try:
        tagger = _faithful_tagger(version)
        tags, _full = tagger.tag(word)
    except Exception:           # noqa: BLE001 -- fall back to dict flags
        exact = flags.get(word)
        if exact and exact["found"]:
            for k in _POS_KEYS:
                pos[k] = bool(exact.get(k))
        return pos
    # translate the _eu_pos tag-set names onto _POS_KEYS
    name_map = {
        "adi_jok": "adi_jok", "adi_lgn": "adi_lgn", "adi_trn": "adi_trn",
        "prokli": "prokli", "enkli": "enkli", "lot_jnt": "lot_jnt",
        "lot_azk": "lot_azk", "prt": "prt", "det": "det", "adj": "adj",
        "ize": "ize", "adb": "adb", "ior": "ior", "atz_adi1": "atz_adi1",
        "atz_adi2": "atz_adi2", "atz_adi3": "atz_adi3", "atz_ize": "atz_ize",
        "str_mrk": "str_mrk",
    }
    for src, dst in name_map.items():
        if src in tags:
            pos[dst] = True
    return pos


# ==========================================================================
# FGRP / AGRP grouping + accentual-group stress
# (eu_gf.cpp utt_gf, gfize.cpp/gfadi.cpp groupers, eu_stre.cpp fgrp2agrp +
#  agrp_stress)
# ==========================================================================
A_NONE, A_MRK, A_OROK, A_GABE, A_TXT = 0, 1, 2, 3, 4
# FGRP markers: 1 = head (GF_EU_ARRUN / start), 0 = merged (GF_EU_NONE)


def _poscases(tags, words=None, boundary_after=None, sent_end_after=None):
    """Runtime POS disambiguation (poscases.cpp, run as the second pass of
    eu_categ.cpp::utt_categ over the WHOLE utterance after the per-word
    categoriser).  Each word's ambiguous POS bits are resolved from its
    neighbours; this is what lets `jakin` (ADI_JOK+ADJ) be recognised as an
    adjective before `bat` so the fgrp2agrp es_verbo_jok look-ahead does NOT
    de-accent / re-OROK the enclitic.  Ported: detaux (+ dena-special), detior,
    jntazk, izejok, adjjok, trnlgn.

    `boundary_after[i]` marks a pause cell (comma/colon/period) immediately after
    word i.  In the C the word cells are still adjacent via `wordNext`, but the
    `wordIsLast(URANGE_SENTENCE)` / `ultimo` tests and several stress effects key
    off that pause; we use it for the boundary-sensitive arms.
    """
    n = len(tags)

    def sub(t, k):
        t[k] = False

    def bafter(i):
        # any pause cell (comma / colon / semicolon / period / ! / ?) follows
        return boundary_after[i] if boundary_after is not None \
            and i < len(boundary_after) else (i == n - 1)

    def sent_end(i):
        # a SENTENCE terminator (. ! ?) follows word i -> wordIsLast(SENTENCE).
        # A comma/colon/semicolon is a PHRASE boundary, NOT a sentence end.
        return sent_end_after[i] if sent_end_after is not None \
            and i < len(sent_end_after) else (i == n - 1)

    for i in range(n):
        t = tags[i]
        nxt = tags[i + 1] if i + 1 < n else None
        prev = tags[i - 1] if i > 0 else None
        last = nxt is None

        word = words[i] if words is not None and i < len(words) else None
        # detaux dena-special (poscases.cpp:46): "dena" before a verb (or
        # sentence-initial) keeps its nominal reading (strip LGN/TRN); else it is
        # the verb reading (strip DET).  excep then skips the generic branch.
        # Binary-observed boundary effect: `dena` immediately before a pause
        # (dena:/dena,/dena.) surfaces OROK (its STR_MRK is suppressed -> 2nd
        # syllable, denA), whereas `dena word` surfaces MRK (dEna).
        excep = False
        if word == "dena":
            excep = True
            # The C inner test is `(ultimo==0) && !wordIsLast(SENTENCE)`: a pause
            # immediately after `dena` makes it sentence/phrase-final, so the
            # inner disambiguation is skipped and `dena` keeps the DET reading
            # (matching the binary's denA before `:`/`,`/`.`).  Only a `dena`
            # directly followed by a word runs the verb/nominal split.
            dena_next = None if bafter(i) else nxt
            if dena_next is not None and (dena_next["adi_jok"]
                                          or dena_next["adi_lgn"]
                                          or dena_next["adi_trn"] or i == 0):
                if t["adi_lgn"]:
                    sub(t, "adi_lgn")
                if t["adi_trn"]:
                    sub(t, "adi_trn")
            elif not bafter(i):
                sub(t, "det")

        # detaux (poscases.cpp:67): DET+ADI_LGN, resolve by previous word.
        # Faithful to source: prev is ADI_JOK/ENKLITIKO -> subPOS(DET) (it is a
        # verb; also strip IOR); else subPOS(ADI_LGN)+ADI_TRN (it is the det/ior
        # reading).  Sentence-initial (primero) -> strip both verb bits.
        if (not excep) and t["det"] and t["adi_lgn"]:
            if prev is not None:
                if prev["adi_jok"] or prev["enkli"]:
                    sub(t, "det")            # it is a verb (quitar det)
                    if t["ior"]:
                        sub(t, "ior")
                else:
                    sub(t, "adi_lgn")        # quitar lgn, es det/ior
                    if t["adi_trn"]:
                        sub(t, "adi_trn")
            else:
                if t["adi_trn"]:
                    sub(t, "adi_trn")
                if t["adi_lgn"]:
                    sub(t, "adi_lgn")

        # detior (poscases.cpp:95): DET+IOR -> resolve by previous word.
        if t["det"] and t["ior"]:
            if prev is not None:
                if prev["ize"] or prev["adj"] or (not _has_pos(prev)):
                    sub(t, "ior")            # quitar ior, es det
                else:
                    sub(t, "det")            # quitar det, es ior
            else:
                sub(t, "det")

        # jntazk (poscases.cpp:191): a LOT_AZK+LOT_JNT word (eta/edo/ala/baina/
        # baino) at sentence end is the LOT_AZK reading -> strip LOT_JNT, so it
        # is NOT a GABE coordinator and re-accents on its 2nd syllable.  This is
        # the source mechanism behind the phrase-final re-accent (dela eta, ->
        # etA).  The mid-sentence PAUSE-invitation arm only touches PAUSE bits,
        # which do not affect per-phrase stress, so it is a no-op here.
        if t["lot_azk"] and t["lot_jnt"] and sent_end(i):
            sub(t, "lot_jnt")

        # izejok (poscases.cpp:229): ADI_JOK+IZE.  C gate is `(ultimo==0) &&
        # !wordIsLast(SENTENCE)`, then look at `p_word_next` (DET/ADJ -> noun,
        # else verb).  At sentence end it is the verb reading.  `sent_end(i)` =
        # a sentence terminator (.!?) follows; a comma does NOT end the sentence,
        # so the next-word check still runs across it.
        if t["adi_jok"] and t["ize"]:
            if (not sent_end(i)) and nxt is not None \
                    and (nxt["det"] or nxt["adj"]):
                sub(t, "adi_jok")            # quitar jok, es ize
            else:
                sub(t, "ize")               # quitar ize, es jok

        # adjjok (poscases.cpp:253): ADI_JOK+ADJ -> adjective before a DET/ADJ
        # (verb before TRN/LGN).  `jakin bat` -> jakin loses ADI_JOK -> adj.
        if t["adi_jok"] and t["adj"]:
            if (not sent_end(i)) and nxt is not None:
                if nxt["adi_trn"] or nxt["adi_lgn"]:
                    sub(t, "adj")            # quitar adj, es jok
                elif nxt["det"] or nxt["adj"]:
                    sub(t, "adi_jok")        # quitar jok, es adj
                else:
                    sub(t, "adj")            # quitar adj, es jok
            else:
                sub(t, "adj")

        # trnlgn (poscases.cpp:120): ADI_TRN+ADI_LGN -> an auxiliary (du/zen)
        # following a JOK/ATZ_ADI1 participle is the LGN reading (strip TRN);
        # else resolve by the PRT-two-back rule, then by the following word.
        if t["adi_trn"] and t["adi_lgn"] and prev is not None:
            pp = tags[i - 2] if i - 2 >= 0 else None
            if prev["atz_adi1"] or prev["adi_jok"]:
                sub(t, "adi_trn")            # keep lgn (it is the aux)
            else:
                if prev["prt"] and pp is not None:
                    if pp["atz_adi1"] or pp["adi_jok"]:
                        sub(t, "adi_trn")
                    else:
                        sub(t, "adi_lgn")
                if t["adi_trn"] and t["adi_lgn"]:
                    if nxt is not None:
                        if nxt["adi_jok"]:
                            sub(t, "adi_trn")
                        else:
                            sub(t, "adi_lgn")
                    else:
                        sub(t, "adi_lgn")


def _fgrp_grouping(tags, n):
    """Compute fgrp[] (1 = FGRP head / GF_EU_ARRUN, 0 = merged / GF_EU_NONE).

    Faithful left-to-right port of eu_gf.cpp::utt_gf: for each word p we set it a
    head, then run the ordered grouper cascade with first-match-wins (the C
    `encontrado` short-circuit), each grouper merging the following word(s) it
    consumes (FGrp=NONE) and reporting how many words it ate (`indice2`); the
    driver then advances p past them.  Cascade order (eu_gf.cpp:87-138):

        enk -> detize -> izedet -> izeadb -> adbadj -> izeize ->
        baitadi -> joklgn -> jokjok -> trn -> (invpau) -> jnt

    Only the groupers that actually merge a following content word change stress;
    the noun/det/adj/adb groupers (enk/detize/izedet/izeize/izeadb/adbadj/jnt)
    all share the same "host + dependent" shape and are folded into one
    `_nominal_merge`.  The verb groupers are ported individually because their
    POS preconditions differ and drive the verb/aux de-accenting.

    POS bit map (eu_lingp.hpp:417-435):
      ize/det/adj/adb/ior/none ; ENKLITIKO=enkli ; PROKLITIKO=prokli ;
      ADI_JOK=adi_jok ; ADI_LGN=adi_lgn ; ADI_TRN=adi_trn ;
      ATZ_ADI1=atz_adi1 ; ATZ_ADI2=atz_adi2 ; ATZ_ADI3=atz_adi3 ; LOT_JNT=lot_jnt
    """
    fgrp = [1] * n
    i = 0
    while i < n:
        t = tags[i]
        nxt = tags[i + 1] if i + 1 < n else None      # inf.next  (p+1)
        nxtn = tags[i + 2] if i + 2 < n else None      # inf.nextn (p+2)
        has_next = nxt is not None        # !phrase_last && !utt_last
        has_nextn = nxtn is not None       # !phrase_prev_last && !utt_prev_last
        adv = 1

        # ---- enk (gfize.cpp:86-144) -----------------------------------------
        # The C enk host test is exactly `queryPOS(POS_EU_NONE) ||
        # queryPOS(POS_EU_IZE)` (gfize.cpp:100) -- a noun.  NOT det/adj/ior:
        # an ADJ + enclitic (`bortitz bat`) is left UNmerged so `bat` heads its
        # own group and surfaces stressed, exactly as the binary does.  Two
        # shapes:
        #   noun + ENKLITIKO            -> merge the enclitic        (indice2=2)
        #   noun + ADJ + ENKLITIKO/DET  -> merge the adj + enclitic  (indice2=3)
        host_noun = (not _has_pos(t) or t["ize"])
        if has_next and host_noun and nxt["enkli"]:
            fgrp[i + 1] = 0
            adv = 2
            i += adv
            continue
        # noun + adj + bat: the C merges the trailing enclitic/det too only when
        # the middle word is ADJ (or a NONE-tagged dict-ADJ); the adj itself is
        # merged when it is ADJ (gfize.cpp:115-141).
        if has_next and host_noun and nxt["adj"] and has_nextn and (
                nxtn["enkli"] or nxtn["det"]):
            fgrp[i + 1] = 0
            fgrp[i + 2] = 0
            adv = 3
            i += adv
            continue

        # ---- izedet: noun/ATZ_IZE + DET (gfize.cpp::izedet) -----------------
        # Source host test: queryPOS(ATZ_IZE) || NONE || IZE; next == DET.  The
        # `bat`/`batzuk` determiner carries DET, so this merges (de-accents) it;
        # the C does NOT exclude ENKLITIKO.  Fires for "nagusietako bat",
        # "erromaniko batzuk" -- an ATZ_IZE modifier absorbs the determiner.
        if has_next and (not _has_pos(t) or t["ize"] or t["atz_ize"]) \
                and nxt["det"]:
            fgrp[i + 1] = 0
            adv = 2
            i += adv
            continue

        # ---- izeize: ATZ_IZE genitive modifier + noun (gfize.cpp:214-249) ----
        # A word carrying ATZ_IZE (an inflected genitive / local-genitive
        # modifier: -aren / -ko / -en, recognised by atzize's ATZ_IZE suffix
        # match) is the FGRP head and absorbs a following NONE/IZE noun; if that
        # noun is itself ATZ_IZE it also absorbs the noun after it (NONE/DET/
        # ENKLITIKO/IZE), indice2=3.  This is what splits "eginkizunaren zati
        # bat" / "garaiko hilarri bat" / "sozialaren genero bat": the genitive
        # eats the noun, the driver's p-advance then lands on `bat`, and because
        # `bat` is DET+ENKLITIKO (not NONE/IZE) the *next* enk pass at `bat` does
        # NOT fire -- so `bat` heads its own group and surfaces stressed (1st
        # syllable, monosyllable).  Without a preceding genitive (mota bat,
        # ikasgai bat) the noun is the enk host and `bat` is de-accented.
        if t["atz_ize"] and has_next:
            merged = False
            if not _has_pos(nxt) or nxt["ize"]:
                fgrp[i + 1] = 0
                adv = 2
                merged = True
            if has_nextn and nxt["atz_ize"] and (
                    not _has_pos(nxtn) or nxtn["det"] or nxtn["enkli"]
                    or nxtn["ize"]):
                fgrp[i + 1] = 0
                fgrp[i + 2] = 0
                adv = 3
                merged = True
            if merged:
                i += adv
                continue

        # ---- baitadi: PROKLITIKO + verb (gfadi.cpp:30-63) --------------------
        # proclitic ("ez"/"ba"/"bait") that fronts ADI_LGN/ADI_TRN/ADI_JOK/
        # ATZ_ADI1-3 merges that verb; if a conjugated verb (ADI_JOK/ATZ_ADI1)
        # follows it too, that is merged as well (indice2=3).
        if t["prokli"] and has_next and (
                nxt["adi_lgn"] or nxt["adi_trn"] or nxt["adi_jok"]
                or nxt["atz_adi1"] or nxt["atz_adi2"] or nxt["atz_adi3"]):
            fgrp[i + 1] = 0
            adv = 2
            if has_nextn and (nxtn["adi_jok"] or nxtn["atz_adi1"]):
                fgrp[i + 2] = 0
                adv = 3
            i += adv
            continue

        # ---- joklgn: ADI_JOK + (ADI_LGN|ATZ_ADI3) (gfadi.cpp:67-107) ---------
        # conjugated verb + auxiliary -> merge the auxiliary into the verb group
        # (this is the participle/conjugated-verb + "du/da/zen" case).
        if (t["adi_jok"] or t["atz_adi1"]) and has_next and (
                nxt["adi_lgn"] or nxt["atz_adi3"]):
            fgrp[i + 1] = 0
            adv = 2
            i += adv
            continue

        # ---- jokjok: (ADI_JOK|ATZ_ADI1) + (ADI_JOK|ATZ_ADI1) (gfadi.cpp:125)
        # verb chain: merge the second conjugated verb / nominalisation, and a
        # trailing ADI_LGN/ATZ_ADI3 auxiliary too (indice2=3).  Faithful to the
        # C condition, which keys on ADI_JOK *or* ATZ_ADI1 for both the head and
        # the next word (a -t(z)en nominalisation carries both bits via adit's
        # setPOS(ATZ_ADI1)+addPOS(ADI_JOK), so "emititzen hasi"/"idazten hasi"
        # chain and de-accent the following verb, as the binary does).
        if (t["adi_jok"] or t["atz_adi1"]) and has_next and (
                nxt["adi_jok"] or nxt["atz_adi1"]):
            fgrp[i + 1] = 0
            adv = 2
            if has_nextn and (nxtn["adi_lgn"] or nxtn["atz_adi3"]):
                fgrp[i + 2] = 0
                adv = 3
            i += adv
            continue

        # ---- trn: lone ADI_TRN/ATZ_ADI1 participle (gfadi.cpp:113-121) ------
        # sets only its own FGrp (indice2=1); merges nothing.  No-op here.
        i += adv
    return fgrp


def _has_pos(t):
    return any(t[k] for k in _POS_KEYS)


def _agrp_types(words, tags, fgrp, version, phrase_last_index):
    """Assign each word's AGRP accent type (eu_stre.cpp fgrp2agrp).

    Two passes: first the per-word base type (default OROK; enclitic-in-group
    -> NONE; STR_MRK -> MRK; bisyllabic conjugated-verb -ko/-go/-ten/-tzen ->
    MRK; LOT_JNT coordinator -> GABE), then the proclitic / conjugated-verb
    look-ahead that de-accents the following verb/auxiliary (-> NONE).
    """
    n = len(words)
    agrp = [A_OROK] * n
    # parallel flag: this word's MRK came from the bisyllabic conjugated-verb
    # -ko/-go/-ten/-tzen rule (NOT a dictionary STR_MRK).  The two are identical
    # in the public source, but the V3 h_shift wrapper treats them differently
    # for h-initial words (verb-rule MRK keeps the audible 1st syllable; dict
    # STR_MRK lets the silent-h empty syllable absorb the accent) -- see below.
    mrk_verb = [False] * n

    # Faithful fgrp2agrp: the C calls fgrp2agrp(u, fg) once per FGRP group and
    # walks the words of that group with `for(p=wordFirst(fg); p; p=wordNext(p))`.
    # The es_proclitico / es_verbo_jok branches *reassign* p via
    # `p=u.wordNext(p,URANGE_FGRP)` and set THAT word's AGrp, after which the
    # for-loop's own wordNext advances past it -- so the looked-at word never
    # gets its own per-word processing (its dict STR_MRK / verb-rule MRK is
    # overwritten by the OROK/NONE the look-ahead assigns).  We reproduce that
    # by walking each FGRP group with an explicit index `i` that the look-ahead
    # branch may advance.  Group boundaries: fgrp[k]!=0 starts a new group
    # (GF_EU_NONE==0 means "merged into the previous group").
    group_start = [k for k in range(n) if k == 0 or fgrp[k] != 0]
    bounds = group_start + [n]
    for gi in range(len(group_start)):
        g0, g1 = bounds[gi], bounds[gi + 1]
        i = g0
        while i < g1:
            t = tags[i]
            w = words[i]
            # default OROK already set
            if t["enkli"] and fgrp[i] == 0:
                agrp[i] = A_NONE
            if t["str_mrk"]:
                agrp[i] = A_MRK
            # fgrp2agrp: es_verbo_jok(=ADI_JOK only) && es_bisilabo &&
            # es_ko_go_ten_tzen -> MRK (eu_stre.cpp:79).  Source gates on
            # ADI_JOK only; the earlier `or atz_adi1` was empirical and is
            # dropped to match es_verbo_jok.
            if t["adi_jok"] and _is_bisyllable(w) \
                    and _ends_ko_go_ten_tzen(w):
                agrp[i] = A_MRK
                mrk_verb[i] = True
            if t["lot_jnt"]:
                agrp[i] = A_GABE
            # look-ahead branches that reassign p (only within this FGRP group)
            advanced = False
            if t["prokli"]:
                if i + 1 < g1:
                    nx = tags[i + 1]
                    if nx["adi_trn"] or nx["adi_lgn"]:
                        agrp[i + 1] = A_NONE
                    else:
                        agrp[i + 1] = A_OROK
                    mrk_verb[i + 1] = False
                    i += 1            # p reassigned, then loop advances again
                    advanced = True
            elif t["adi_jok"]:
                if i + 1 < g1:
                    nx = tags[i + 1]
                    if _is_monosyllable(words[i + 1]) and nx["adi_lgn"]:
                        agrp[i + 1] = A_NONE
                    else:
                        agrp[i + 1] = A_OROK
                    mrk_verb[i + 1] = False
                    i += 1
                    advanced = True
            i += 1
            if advanced:
                continue
    return agrp, mrk_verb


def _is_monosyllable(word):
    return sum(1 for ch in word.lower() if ch in "aeiou") <= 1


def _is_bisyllable(word):
    return sum(1 for ch in word.lower() if ch in "aeiou") == 2


def _ends_ko_go_ten_tzen(word):
    """eu_stuti.cpp es_ko_go_ten_tzen: -ko/-go, or -ten, or -tzen."""
    n = len(word)
    if n >= 2 and word[-1] == 'o' and word[-2] in ('k', 'g'):
        return True
    if n >= 3 and word[-1] == 'n' and word[-2] == 'e':
        if word[-3] == 't':
            return True
        if n >= 4 and word[-3] == 'z' and word[-4] == 't':
            return True
    return False


# ==========================================================================
# Pause group -> per-word single-char strings
# ==========================================================================
_ACUTE_VOWELS = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u'}


def _accent_vowel_ord(raw_word):
    """For a word respelling carrying an acute-accented vowel (the `exp`
    pronunciation field of a NOR=acr dictionary entry, e.g. 'béibi', 'xabiér',
    'donatélo'), return the 0-based ordinal -- among the word's vowel letters --
    of the accented vowel; else None.

    Faithful to eu_phtr.cpp: an accented vowel char (CS_atilde..CS_utilde) maps
    to the base phoneme AND calls SETSTREUS (setStress(USTRESS_TEXT)) on that
    cell (eu_phtr.cpp:274-278).  agrp_stress has no AGRP_EU_TXT case, so the
    word's only accent is this phone-level text stress on the accented vowel.
    """
    if raw_word is None:
        return None
    wl = raw_word.lower()
    vord = 0
    for ch in wl:
        if ch in _ACUTE_VOWELS:
            return vord
        if ch in "aeiou":
            vord += 1
    return None


def _group_to_singlechar(words, version, phrase_last_index=None,
                         orig_words=None, pre_tags=None, raw_words=None):
    cfg = _CONFIG[version]
    flags = _dict_for(version)[1]
    # The engine always syllabifies with diphthong glides (au/eu/ai are one
    # syllable for stress counting).  cfg["glides"] only governs whether the
    # offglide is rendered as j/w (accentual path) or as a full vowel i/u (the
    # flat path).  cfg["accentual"] gates the dict SALBTF flags too.
    phones, pword, _ = g2p_group(words, flags, glides=True,
                                 use_dict_flags=cfg["accentual"],
                                 kdrop_xword=cfg.get("kdrop_xword", False),
                                 orig_words=orig_words, version=version)
    nwords = len(words)
    word_phones = [[] for _ in range(nwords)]
    for k in range(len(phones)):
        word_phones[pword[k]].append(k)
    stress = [False] * len(phones)

    if cfg["accentual"]:
        # eu_w2ph.cpp USE_TOKENIZER path: POS-tag (eu_categ) -> FGRP group
        # (eu_gf) -> AGRP type (eu_stre fgrp2agrp) -> accentual stress
        # (eu_stre agrp_stress).
        if pre_tags is not None:
            # Tags already computed + poscases-resolved over the WHOLE sentence
            # (eu_categ.cpp::utt_categ runs the categoriser and the poscases pass
            # across wordFirst()..wordLast() of the utterance, not per phrase).
            tags = pre_tags
        else:
            tags = [_tag_word(w, flags, version) for w in words]
            _poscases(tags, words)
        fgrp = _fgrp_grouping(tags, nwords)
        agrp, mrk_verb = _agrp_types(words, tags, fgrp, version,
                                     phrase_last_index)
        _agrp_stress(words, phones, word_phones, stress, fgrp, agrp, version,
                     phrase_last_index, mrk_verb, tags=tags)
    else:
        # eu_stre.cpp word_stress flat path (non-tokenizer): every word stressed
        # on its 2nd syllable, 1st if monosyllabic.  The source-compiled libhtts
        # V2 oracle stresses EVERY word (incl. eta/ta/edo) on its 2nd syllable --
        # i.e. es_sin_acento does NOT fire on this build's flat path (`eta
        # gizarte`->etA, `hau ta`->tA), so the flat path is a pure 2nd-syllable
        # rule with no es_sin_acento / STR_MRK / clitic de-accenting.
        for wi in range(nwords):
            idxs = word_phones[wi]
            if not idxs:
                continue
            local = [phones[k] for k in idxs]
            syls = syllabify(local, [False] * len(local))
            if not syls:
                continue
            tgt = syls[1] if len(syls) >= 2 else syls[0]
            v = _syllable_vowel(local, [False] * len(local), tgt)
            if v is not None:
                stress[idxs[v]] = True

    # eu_phtr.cpp text-accent (USTRESS_TEXT): a word respelled from a NOR=acr
    # dictionary `exp` field carries its stress as an acute accent on a vowel
    # (béibi, xabiér, donatélo).  eu_phtr maps the accented vowel to its base
    # phoneme and SETSTREUS marks that phone USTRESS_TEXT; agrp_stress has no
    # AGRP_EU_TXT branch, so the word's only accent is that one text-stressed
    # vowel.  Override the AGRP-assigned stress for any such word: clear its
    # phones and stress the vowel phone at the accented ordinal (counting full
    # vowels AND diphthong glides, the order eu_phtr emits them).
    if raw_words is not None and cfg["accentual"]:
        for wi in range(nwords):
            ord_ = _accent_vowel_ord(raw_words[wi]) if wi < len(raw_words) \
                else None
            if ord_ is None:
                continue
            idxs = word_phones[wi]
            vcount = 0
            target_k = None
            for k in idxs:
                if _is_vowel(phones[k]):
                    if vcount == ord_:
                        target_k = k
                        break
                    vcount += 1
            for k in idxs:
                stress[k] = False
            if target_k is not None:
                stress[target_k] = True

    # The flat path renders diphthong glide phones as their full vowels.
    glide_to_vowel = {} if cfg["glides"] else \
        {PHEU['iaprox']: PHEU['i'], PHEU['uaprox']: PHEU['u']}

    result = []
    for wi in range(nwords):
        toks = []
        for k in word_phones[wi]:
            ph = glide_to_vowel.get(phones[k], phones[k])
            sampa = PH_SAMPA.get(ph, ph)
            ipa = SAMPA_TO_IPA.get(sampa, sampa)
            if stress[k] and ipa in ('a', 'e', 'i', 'o', 'u'):
                ipa = "'" + ipa
            toks.append(MULTI.get(ipa, ipa))
        result.append("".join(toks))
    return result


def _agrp_stress(words, phones, word_phones, stress, fgrp, agrp, version,
                 phrase_last_index, mrk_verb=None, tags=None):
    """Stress each accentual group (eu_stre.cpp agrp_stress).

    An accentual group = a head word (agrp != NONE) plus following words whose
    fgrp==0 (merged) AND agrp==NONE.  MRK -> 1st syllable of the group; OROK ->
    2nd syllable of the group (1st if the group is monosyllabic); GABE/NONE ->
    no stress.  For V3, a silent leading `h` on the head shifts the audible
    stress one syllable earlier.
    """
    n = len(words)
    i = 0
    while i < n:
        head = i
        head_type = agrp[head]
        # collect group members: head + following merged/none words
        members = [head]
        j = i + 1
        while j < n and fgrp[j] == 0 and agrp[j] == A_NONE:
            members.append(j)
            j += 1
        i = j

        if head_type in (A_NONE, A_GABE):
            # eu_stre.cpp agrp_stress: GABE/NONE groups are unstressed, with one
            # phrase-final re-accent on the accentual path.  A LOT_AZK+LOT_JNT
            # coordinator (eta/edo/ala/baina/baino -- the es_sin_acento list
            # MINUS `ta`, which is LOT_JNT-only, not LOT_AZK, and the binary
            # leaves unstressed) that ends a phrase inside a properly terminated
            # sentence is re-accented on its 2nd syllable.  Probed: `... eta,
            # gizarte ... da.` -> etA, but `... eta, gizarte` (no closing
            # period) -> eta, and `hau ta` -> ta.  Gated on lot_azk so `ta` is
            # excluded; the closing-period requirement is handled by the caller
            # passing phrase_last_index only for terminated phrases.
            if head_type == A_GABE and head == phrase_last_index \
                    and tags is not None and tags[head]["lot_azk"] \
                    and tags[head]["lot_jnt"]:
                _stress_nth_syllable(phones, word_phones, members, stress, -1,
                                     version, words[head])
            continue

        # build the group's syllable list (phones across all members in order)
        group_phone_idx = []
        for m in members:
            group_phone_idx.extend(word_phones[m])
        if not group_phone_idx:
            continue
        local = [phones[k] for k in group_phone_idx]
        syls = syllabify(local, [False] * len(local))
        if not syls:
            continue

        h_shift = (_CONFIG[version]["h_shift"] and words[head][:1] == 'h')

        if head_type == A_MRK:
            # MRK -> 1st syllable.  Under V3 h_shift on an h-initial head, a
            # *dictionary STR_MRK* mark is absorbed by the silent-h empty
            # syllable (hasi->asi, hori->oɾi: no audible accent), but the mark
            # assigned by the bisyllabic conjugated-verb -ten/-tzen rule keeps
            # its audible 1st syllable (hartzen->ArPen, hasten->Asten).
            is_verb_mrk = bool(mrk_verb and mrk_verb[head])
            if h_shift and not is_verb_mrk:
                target = None
            else:
                target = 0
        else:  # OROK
            if h_shift:
                target = 0
            else:
                target = 1 if len(syls) >= 2 else 0
        if target is None or target >= len(syls):
            continue
        v = _syllable_vowel(local, [False] * len(local), syls[target])
        if v is not None:
            stress[group_phone_idx[v]] = True


def _stress_nth_syllable(phones, word_phones, members, stress, nth, version,
                         head_word):
    group_phone_idx = []
    for m in members:
        group_phone_idx.extend(word_phones[m])
    if not group_phone_idx:
        return
    local = [phones[k] for k in group_phone_idx]
    syls = syllabify(local, [False] * len(local))
    if not syls:
        return
    target = nth if nth >= 0 else len(syls) + nth
    if 0 <= target < len(syls):
        v = _syllable_vowel(local, [False] * len(local), syls[target])
        if v is not None:
            stress[group_phone_idx[v]] = True


# ==========================================================================
# Number / date expansion  (eu_numexp.cpp / eu_numhilvl.cpp / eu_decli.cpp).
# Source-faithful Basque vigesimal cardinals.  upTo99 glues "ta" onto the
# tens word (hogeita), upTo999 inserts "eta", expnum walks the ternas
# (mila/miloi/biloi) with the eta-copula rule; eu_decli.dekline attaches a
# case suffix to a glued digit form (1894an, 10ean).
# ==========================================================================
_UNITS = ["zero", "bat", "bi", "hiru", "lau", "bost", "sei", "zazpi", "zortzi",
          "bederatzi"]
_TEN_TO_19 = ["hamar", "hamaika", "hamabi", "hamahiru", "hamalau", "hamabost",
              "hamasei", "hamazazpi", "hamazortzi", "hemeretzi"]
_TENS2468 = ["hogei", "berrogei", "hirurogei", "laurogei"]          # 20 40 60 80
_HUNDREDS = ["ehun", "berrehun", "hirurehun", "laurehun", "bostehun", "seiehun",
             "zazpiehun", "zortziehun", "bederatziehun"]
_THOUSAND, _MILLION, _BILLION, _TA, _ETA = "mila", "miloi", "biloi", "ta", "eta"
_NUM_VOWELS = set("aeiou")
# Recognised Basque case-declension suffixes (eu_decli.cpp::isGroupDecd).
#
# isGroupDecd does NOT carry a hand-written suffix list: it queries the
# dictionary entry of the trailing cell --
#     myhdic = dic->search(ct(q).str);
#     isDec  = dic->query(myhdic, HDIC_QUERY_EU_DEC);   // bit 2 of the HDicRef
#     len    = dic->query(myhdic, HDIC_QUERY_MATCHLEN); // 0 => exact match
#     if (isDec && !len) retval = TRUE;
# (eu_decli.cpp:142-173).  So the declension set is exactly the dictionary keys
# whose HDicRef carries the EU_DEC bit (HDIC_QUERY_EU_DEC = ENCODE(2,1),
# eu_hdic.hpp:159).  We read that bit straight out of the .dic instead of
# hand-typing a list.  Both shipped eu dicts (eu_dicc_v1 / eu_dicc_20250326)
# expose the identical 282-entry EU_DEC set (absolutive/ergative/dative,
# genitive/benefactive, comitative, inessive, allative, ablative,
# local-genitive, motivative/partitive, plus the dialectal -gana*/-orre*/-one*
# pronominal declensions).
def _read_decl_suffixes(path):
    """All dict keys carrying the EU_DEC bit (eu_decli.cpp::isGroupDecd)."""
    data = open(path, 'rb').read()
    out = set()
    for _, base, n, slen, exlen, blen, has_exp in (
            (i, *b) for i, b in enumerate(_hdic_blocks(data))):
        for k in range(n):
            rec = base + blen * k
            wlen = struct.unpack_from('<H', data, rec)[0]
            try:
                w = data[rec + 2:rec + 2 + wlen].decode('latin-1')
            except UnicodeDecodeError:
                continue
            ref = struct.unpack_from('<I', data, rec + 2 + slen)[0]
            if (ref >> 2) & 1:               # HDIC_QUERY_EU_DEC, bit 2
                out.add(w.lower())
    return out


_DECL_SUFFIX_CACHE = {}


def _decl_suffixes(version="v1"):
    cfg = _CONFIG[version]
    path = os.path.join(_HERE, cfg["dict"])
    if path not in _DECL_SUFFIX_CACHE:
        _DECL_SUFFIX_CACHE[path] = _read_decl_suffixes(path)
    return _DECL_SUFFIX_CACHE[path]


# Module-level alias for the (identical across versions) EU_DEC set, used by the
# version-agnostic v3 hyphen-declension regex below.  Read from the v1 dict.
_DECL_SUFFIX = _decl_suffixes("v1")


def _get1e3n(numtern):                       # eu_numexp.cpp get1E3n
    return {1: _THOUSAND, 2: _MILLION, 3: _THOUSAND,
            4: _BILLION, 5: _THOUSAND}.get(numtern)


def _upto99(num, out):                        # eu_numexp.cpp upTo99
    if num == 0:
        out.append("zero")
        return
    while num:
        if num <= 9:
            out.append(_UNITS[num])
            num = 0
        elif num <= 19:
            out.append(_TEN_TO_19[num - 10])
            num = 0
        else:
            out.append(_TENS2468[num // 20 - 1])
            num %= 20
            if num:
                out[-1] += _TA              # extendStr(taStr): glued onto tens


def _upto999(num, out):                       # eu_numexp.cpp upTo999
    if num < 100:
        _upto99(num, out)
        return
    cent = num // 100
    out.append(_HUNDREDS[cent - 1])
    num -= cent * 100
    if num:
        out.append(_ETA)
        _upto99(num, out)


def expnum(digits):                           # eu_numexp.cpp expnum
    out = []
    inp = digits
    numceros = 0
    while len(inp) > 1 and inp[0] == '0':
        numceros += 1
        inp = inp[1:]
    out += ["zero"] * numceros
    if len(inp) > 18:
        return out
    L = len(inp)
    resto = L % 3
    numtern = (L - resto) // 3
    numzone = [False] * 6
    etapend = False
    if resto:
        etapend = True
        terna = int(inp[:resto])
        if terna != 1:
            if terna == 0:
                _upto99(terna, out)
            else:
                _upto999(terna, out)
                g = _get1e3n(numtern)
                if g:
                    out.append(g)
        else:
            if numtern == 0:
                _upto99(terna, out)
            elif numtern in (1, 3, 5):
                g = _get1e3n(numtern)
                if g:
                    out.append(g)
            elif numtern in (2, 4):
                g = _get1e3n(numtern)
                if g:
                    out.append(g)
                _upto99(terna, out)
        inp = inp[resto:]
        numzone[numtern] = True
    for j in range(numtern):
        terna2 = int(inp[:3])
        if terna2 != 0:
            if ((terna2 % 100 == 0) or (terna2 // 100 == 0)) and etapend \
               and j != numtern - 2 and j != numtern - 4:
                out.append(_ETA)
            if terna2 != 1:
                _upto999(terna2, out)
                g = _get1e3n(numtern - (j + 1))
                if g:
                    out.append(g)
            else:
                k = numtern - (j + 1)
                if k == 0:
                    if resto != 0:
                        _upto99(terna2, out)
                    else:
                        g = _get1e3n(k)
                        if g:
                            out.append(g)
                elif k in (1, 3, 5):
                    g = _get1e3n(k)
                    if g:
                        out.append(g)
                elif k == 2:
                    if numzone[3]:
                        _upto99(terna2, out)
                        g = _get1e3n(k)
                        if g:
                            out.append(g)
                    else:
                        g = _get1e3n(k)
                        if g:
                            out.append(g)
                        _upto99(terna2, out)
                elif k == 4:
                    if numzone[5]:
                        _upto99(terna2, out)
                        g = _get1e3n(k)
                        if g:
                            out.append(g)
                    else:
                        g = _get1e3n(k)
                        if g:
                            out.append(g)
                        _upto99(terna2, out)
            numzone[numtern - (j + 1)] = True
            etapend = True
            inp = inp[3:]
        else:
            k = numtern - (j + 1)
            if k == 2:
                if numzone[3]:
                    out.append(_MILLION)
            elif k == 4:
                if numzone[5]:
                    out.append(_BILLION)
            elif k == 0:
                if terna2 == 0 and resto == 0 and not numzone[j]:
                    _upto99(terna2, out)
            inp = inp[3:]
    return out


def number_to_basque_words(n, ordinal=False):
    words = expnum(str(int(n)))
    if ordinal and words:
        w = words[-1]
        if w.endswith("st"):
            w = w[:-1]
        words[-1] = w + "garren"
    return words


def _decline(word, dek):                       # eu_decli.cpp dekline
    last, first = word[-1].lower(), dek[0].lower()
    if last == 'r' and first != 'r':
        word += 'r'
    if last == 'a':
        if first == 'a':
            dek = dek[1:]
        elif first == 'e':
            word = word[:-1]
    elif last == 'e':
        pass
    elif last not in _NUM_VOWELS and first not in _NUM_VOWELS:
        word += 'e'
    return word + dek


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


def _is_numberish(tok):
    return tok.isdigit() or _roman_to_int(tok) is not None


def _merge_thousands(tokens):
    """Merge digit . digit . digit runs into one number token (eu_numhilvl
    expCard: a '.' between 3-digit groups is a thousands separator)."""
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
            i = j
        else:
            out.append(t)
            i += 1
    return out


# ==========================================================================
# Acronym / abbreviation spelling  (eu_abbacr.cpp + eu_cap.cpp::pronounce)
# ==========================================================================
# eu_cap.cpp::pronounce handles an all-uppercase token: it builds a vowel/
# consonant pattern and, if the word cannot be syllabified as Basque (`if
# (!vowel) p = expandCell(p)` plus the syllable failure), it spells the word
# letter by letter (expandCell), each letter looked up as its dictionary letter-
# name.  Otherwise the word is read as a normal word.  eu_abbacr.cpp first looks
# the token up in the dictionary as an acronym (HDIC_ANSWER_EU_NOR_ACR): if
# found it emits the dictionary `exp` expansion (NATO -> ipar atlantikoko ...).
#
# Letter-name table: read verbatim from the AhoTTS speller source, NOT probed.
# `eu_speller.cpp::spellCell` spells a cell char-by-char via `eu_getchexp(c)`,
# which indexes `eu_symbolexp[256]` (`symbolexp.c`).  These are the exact ASCII
# A-Z / a-z entries of that table (byte-identical between the V1 pyAhoTTS tree
# and the V2/V3 ahotts_common tree).  Source: symbolexp.c:124-256
# (`pCHAR eu_symbolexp[256]`), rows [065]A..[090]Z and [097]a..[122]z.
# Note y -> "i grekoa" (source row [089]Y / [121]y) -- a probe round had it as
# "i"; the source is authoritative.
_LETTER_NAME = {
    'a': "a", 'b': "be", 'c': "ze", 'd': "de", 'e': "e", 'f': "efe",
    'g': "ge", 'h': "hatxe", 'i': "i", 'j': "jota", 'k': "ka", 'l': "ele",
    'm': "eme", 'n': "ene", 'o': "o", 'p': "pe", 'q': "ku", 'r': "erre",
    's': "ese", 't': "te", 'u': "u", 'v': "uve", 'w': "uve bikoitza",
    'x': "ixa", 'y': "i grekoa", 'z': "zeta",
}

# --------------------------------------------------------------------------
# Pronounceability (eu_pronun.cpp::isPronun) -- faithful source port.
# --------------------------------------------------------------------------
# eu_normal.cpp routes an all-caps word (isCap==1) through `if (!isPronun(p))
# p = expandCell(p)`: a NON-pronounceable all-caps word is spelled letter by
# letter, a pronounceable one is read.  isPronun maps the (h-filtered) word to a
# string of phonetic-class codes, splits it into vowel/consonant groups, and
# checks every consonant group against the position-specific valid-cluster
# tables below.  Tables + class codes ported verbatim from eu_pronun.cpp
# (lines 176-262) and the eu_getGroup / filterStr transforms.
_EU_VOWELS = set("aeiouáéíóúàèìòùü")
# class-string tables (eu_pronun.cpp:176-193) -> class code (enum :199-217)
_EU_GETGROUP = {
    "n": 'N', "m": 'M', "b": 'O', "g": 'O', "w": 'W', "t": 'P', "k": 'P',
    "d": 'P', "p": 'P', "tt": 'Q', "ñ": 'Ñ', "l": 'L', "r": 'R', "ll": 'D',
    "rr": 'E', "z": 'Z', "x": 'Z', "s": 'G', "tz": 'H', "ts": 'H', "tx": 'H',
    "j": 'I', "f": 'F', "y": 'Y',
}
# oclu4 (w) is also accepted as a vowel-group head by eu_getGroup's dblGrp arm.
_EU_DIGRAPHS = ("tt", "ll", "rr", "tz", "ts", "tx")
_EU_VALID = {
    (1, 0): "D F G H I L R M N O P Q Ñ Z Y",      # validOneSta
    (1, 1): "D E F G H I L R M N O P Q Ñ Z Y",    # validOneMid
    (1, 2): "D F G H L R M N O P Q I Z",          # validOneEnd
    (2, 0): "OL OR PL PR FL FR",                   # validTwoSta
    (2, 1): ("NM NO NP NQ NL NR ND NF NG NH NI NZ MM MN MO MP MQ ML MR MD MF "
             "MG MH MI MZ ON OM OP OQ OÑ OL OR OF OG OH OI OZ PN PM PO PL PR PF "
             "PG PH PI PP PZ QN QM QO QF ÑO ÑZ ÑH ÑF LN RN LM RM LO RO LP RP LQ "
             "RQ LÑ RÑ LL RR LR RL LD RD LE RE LZ RZ LG RG LH RH LI RI LF RF ZN "
             "ZM ZO ZP ZQ ZÑ ZL ZR ZG ZH ZO ZF ZI GN GM GO GP GQ GÑ GL GR GD GE "
             "GZ GH GI GF HM HO HP IN IM IO IP IQ IÑ IL IR ID IE IZ IG IG IF FN "
             "FM FO FP FQ FÑ FL FR FZ FH FI"),     # validTwoMid
    (2, 2): ("NS NG NH NF NP MS MG MH MF MP OL OR LP RP OG OH OZ PL PR LG RG LH "
             "RH LF RF LO RO ZP GP FP FM FL FR FG"),  # validTwoEnd
    (3, 0): "",                                    # validThreeSta
    (3, 1): ("NFL NFR NFP NGF NGH NGI NGL NGR NGM NGN NGO NGP NOL NOR NPL NPR "
             "NPP NZM NZO NZP MFL MFR MFP MGF MGH MGI MGL MGR MGM MGN MGO MGP "
             "MOL MOR MPL MPR MPP OGN OGM OGP OGL OGR OGZ OGF POL POR PPL PPR "
             "LFL RFR LFR RFL LFO RFO LFP RFP LGP RGP LHM RHM LOL ROR LOR ROL "
             "LPL RPR RZL LZP RZP LPR ZOL ZOR ZFL ZFR ZPR GFL GFR GOL GOR GPL "
             "GPR GPM GPO FOL FOR FPR FFL FFR"),   # validThreeMid
    (3, 2): "",                                    # validThreeEnd
    (4, 0): "",                                    # validFourSta
    (4, 1): "NGOL NGOR NGPL NGPR OGPL OGPR",       # validFourMid
    (4, 2): "",                                    # validFourEnd
}


def _eu_filter_str(w):
    """eu_pronun.cpp::filterStr: drop intervocalic-ish h, ce/ci->z, ch->tx,
    qu->k, ph->f, mm->m (operates left to right on the lowercased word)."""
    out = []
    i = 0
    n = len(w)
    while i < n:
        c = w[i]
        nx = w[i + 1] if i + 1 < n else ''
        if c == 'h' and nx in _EU_VOWELS:
            i += 1                       # drop the h
            continue
        if c == 'c':
            if nx in ('e', 'i'):
                out.append('z')
            elif nx == 'h':
                out.append('t')
                out.append('x')
                i += 2
                continue
            else:
                out.append('k')
            i += 1
            continue
        if c == 'q' and nx == 'u':
            out.append('k')
            i += 2
            continue
        if c == 'p' and nx == 'h':
            out.append('f')
            i += 2
            continue
        if c == 'm' and nx == 'm':
            out.append('m')
            i += 2
            continue
        out.append(c)
        i += 1
    return ''.join(out)


def _eu_str2grpStr(w):
    """eu_pronun.cpp::eu_str2grpStr: filtered word -> phonetic-class-code
    string (V for a vowel, else the consonant class code; X for unknown)."""
    w = _eu_filter_str(w.lower())
    out = []
    i = 0
    n = len(w)
    while i < n:
        two = w[i:i + 2]
        if two in _EU_DIGRAPHS:
            out.append(_EU_GETGROUP[two])
            i += 2
            continue
        c = w[i]
        if c in _EU_VOWELS:
            out.append('V')
        elif c in _EU_GETGROUP:
            out.append(_EU_GETGROUP[c])
        else:
            out.append('X')
        i += 1
    return ''.join(out)


def _is_syllabifiable(word):
    """eu_pronun.cpp::isPronun -- True iff the word is pronounceable as Basque
    (so eu_normal reads it); False -> all-caps speller (expandCell)."""
    grp = _eu_str2grpStr(word)
    if not grp:
        return False
    # split into maximal vowel ('V') / consonant runs (eu_str2GrpLst)
    groups = []
    cur = grp[0]
    is_v = grp[0] == 'V'
    for ch in grp[1:]:
        v = ch == 'V'
        if v != is_v:
            groups.append(cur)
            cur = ch
            is_v = v
        else:
            cur += ch
    groups.append(cur)
    n = len(groups)
    # one consonant-only group -> not pronounceable (isPronun:594)
    if n == 1 and groups[0][0] != 'V':
        return False
    for i, g in enumerate(groups):
        if g[0] == 'V':
            continue
        L = len(g)
        if L >= 5:
            return False
        pos = 0 if i == 0 else (2 if i == n - 1 else 1)
        table = _EU_VALID.get((L, pos), "")
        if g not in table.split():
            return False
    return True


def _acronym_words(tok, lexicon):
    """An all-uppercase token (len>=2) -> spoken word list.

    1. dictionary acronym with an expansion (NATO/EAE/HABE) -> the exp words;
    2. else readable as Basque (AEK, SOS, ELA) -> the word itself (lowercased);
    3. else (GPS, LTD, IBM, PSE) -> spelled letter by letter (eu_cap expandCell).
    """
    exp = lexicon.get(tok)
    if exp and exp.strip():
        return exp.split()
    if tok in lexicon or tok.lower() in lexicon:
        return [tok.lower()]                          # known word/name: read
    if _is_syllabifiable(tok):
        return [tok.lower()]
    return [_LETTER_NAME[c] for c in tok.lower() if c in _LETTER_NAME]


def _expand_tokens(tokens, version):
    out = []
    lexicon = _dict_for(version)[0]
    for t in _merge_thousands(tokens):
        out.extend(_expand_one(t, lexicon, version=version))
    return out


def _expand_one(tok, lexicon, ordinal_dot=False, version="v1"):
    if tok in _PUNCT or not tok.strip():
        return [tok]
    # percent: %N or N% -> ehuneko + cardinal (eu_percent.cpp)
    m = re.fullmatch(r'%(\d+)', tok) or re.fullmatch(r'(\d+)%', tok)
    if m:
        return ["ehuneko"] + expnum(m.group(1))
    if tok.isdigit():
        return expnum(tok)
    # glued case suffix on a digit form: 1894an, 10ean, 60ko (eu_decli.cpp).
    # V1/V3 read the number as a cardinal and decline the last word
    # (1894an -> mila zortzireun ... hamalauan).  The V2 (ahotts/tts flat-path)
    # binary instead SPELLS each digit and reads the suffix as a separate word
    # (1894an -> bat zortzi bederatzi lau an; 3ko -> hiru ko) -- a documented
    # V2 wrapper behaviour, version-gated here.
    m = re.fullmatch(r'(\d+)([a-zA-Z]+)', tok)
    if m:
        digits, suf = m.group(1), m.group(2)
        # eu_decli.cpp isGroupDecd: a glued alpha suffix is treated as a
        # declension (number read as a cardinal, then declined) ONLY if the
        # suffix is a recognised Basque case-declension form (dict EU_DEC).
        # Otherwise (an ordinal -garren, a derivational -tar/-dun/-txo, or a
        # mis-spelled case like the colloquial -dik for -tik) the number is NOT
        # declined: each digit is SPELLED and the suffix read as its own word.
        # V2 (flat ahotts/tts path) always spells digit-by-digit regardless.
        if version == "v2" or suf.lower() not in _DECL_SUFFIX:
            return [_UNITS[int(d)] for d in digits] + [suf]
        words = expnum(digits)
        if words:
            words[-1] = _decline(words[-1], suf)
        return words
    # word/letter glued to digits: R4 -> "erre lau", Info7 -> "info zazpi".
    # eu_numexp splits a number off an adjacent alphabetic run; the alpha part
    # then normalises on its own (a single capital is spelled, a word is read).
    m = re.fullmatch(r'([A-Za-z]+)(\d+)', tok)
    if m and tok not in lexicon:
        alpha, num = m.group(1), m.group(2)
        if alpha.isupper():
            alpha_words = _acronym_words(alpha, lexicon)
        else:
            alpha_words = [alpha]
        return alpha_words + expnum(num)
    # NOR=acr dictionary entry -> its `exp` respelling (eu_abbacr.cpp
    # isAbbAcrUni + expAbbAcrUni: an exact dict match with NOR==ACR is replaced
    # at the normaliser stage by str2wrdLst(exp)).  dic->search hits the
    # case-insensitive blocks 2/3, so a capitalised name (New, Xabier) matches
    # the lowercase key just as the binary does.  The exp field carries two
    # encodings, distinguished on disk by their terminator: a TAB-terminated exp
    # ("bilborok\t", "euskadiko autonomi elkartea\t") is a true acronym/initialism
    # expansion read on EVERY path; a CR-terminated exp ("niu\r", "béibi\r",
    # "xabiér\r") is a phonetic respelling of a proper name carrying its stress
    # as an acute accent -- the accentual V1/V3 path applies it (and the
    # USTRESS_TEXT accent), but the V2 flat-path build (ahotts/tts transcribe)
    # reads the raw word (New->nEu, baby->bAbʝ, boom->βoOm, Xabier->ʃaβIer).
    exp = lexicon.get(tok)
    if exp is None and tok.lower() in lexicon \
            and (tok[:1].isupper() or tok.islower()):
        exp = lexicon[tok.lower()]
    if exp is not None:
        # A word that is ALSO TF_MRK (boom: NOR=acr exp 'bum' AND TF_MRK
        # transcription 'b.u.m') is left for the TF path -- eu_phtr.cpp emits
        # the dict transcription verbatim (tf_mrk_ch2ph), bypassing g2p and its
        # b/d/g coarticulation, so boom stays plosive [bum] even after a vowel
        # (baby boom -> ...bUm, da boom -> dA bUm).  Expanding it here would
        # re-g2p 'bum' and wrongly approximate the b to β after the vowel.
        flags = _dict_for(version)[1]
        fl = flags.get(tok.lower())
        is_tf = bool(fl and fl.get("tf_mrk") and fl.get("tf_exp"))
        is_respelling = exp.endswith("\r")
        if not is_tf and not (is_respelling and version == "v2"):
            return exp.split()
    # all-uppercase acronym/abbreviation (eu_abbacr + eu_cap::pronounce),
    # optionally with a glued lowercase case-suffix (EAEko, LTDan, GPSa).  The
    # suffix declines onto the last expanded word, exactly as expAbbAcrUni
    # inserts the words then keeps the trailing suffix group.
    m = re.fullmatch(r'([A-Z]{2,})([a-z]+)?', tok)
    if m:
        base = m.group(1)
        # a bare valid roman numeral (no glued suffix) is read as an ordinal --
        # eu_romanhilvl runs before the acronym speller (XX -> hogei).  With a
        # glued suffix the roman path does not fire (XXan -> spelled).
        if m.group(2) is None:
            rn = _roman_to_int(base)
            if rn is not None:
                return number_to_basque_words(rn, ordinal=True)
        words = _acronym_words(base, lexicon)
        if words:
            if m.group(2):
                words = list(words)
                words[-1] = _decline(words[-1], m.group(2))
            return words
    # a standalone single uppercase letter is spelled by name (eu_cap: a lone
    # capital is not a word, so expandCell spells it -- X -> ixa, C -> ze, V ->
    # uve).  A single roman letter is NOT read as a numeral here (X -> ixa, not
    # hamar) -- probe-validated.  Restricted to a *bare* single capital: a
    # capitalised normal word (Historia, Da) is a real word and is read.
    if len(tok) == 1 and tok.isupper() and tok.lower() in _LETTER_NAME \
            and tok not in lexicon:
        # eu_cap::pronounce treats a lone `y` as a vowel and reads the cell as
        # the word "i" (vowel count > 0 -> not expandCell'd), so it is NOT
        # spelled "i grekoa" (which is the multi-letter speller's name).
        if tok.lower() == 'y':
            return ["i"]
        return [_LETTER_NAME[tok.lower()]]
    # multi-letter roman numeral -> ordinal (single letters are spelled, not
    # treated as romans -- eu_romanhilvl.cpp)
    if len(tok) > 1:
        rn = _roman_to_int(tok)
        if rn is not None:
            return number_to_basque_words(rn, ordinal=True)
    return [tok]


# ==========================================================================
# V3 text normaliser  (modulo1y2 -TxtMode=Word  +  eu_phonemizer.getPhonemes)
# ==========================================================================
# The V3 oracle pipeline is two stages, both reproduced here:
#
#   1. modulo1y2 -TxtMode=Word        -> eu_phonemizer.Phonemizer.normalize()
#      The C++ text-normaliser.  It rewrites symbols to spoken Basque words,
#      verbalises *mid-glued* structural punctuation, expands numbers, and
#      otherwise leaves boundary/spaced punctuation literal.
#   2. eu_phonemizer.Phonemizer.getPhonemes(norm, use_single_char=True)
#      re-tokenises the normalised text with  \w+|[^\w\s]  and emits every
#      char in Python's string.punctuation as its own output token (words go
#      through the phonemiser).  `.line()` then joins with single spaces.
#
# The exact rule set was characterised against the binary (probed in every
# glued/boundary/spaced context).  Two punctuation classes:
#
#   "structural"  . , ; : ! ? ( ) - "  «»
#       verbalised ONLY when glued between two word characters (mid);
#       otherwise kept literal (then split off as a token by getPhonemes).
#       `-` mid -> removed (word split); «» mid -> removed (joined);
#       `"` behaves exactly like `,`;  «» elsewhere -> ' (ASCII apostrophe).
#   "always-verbalised"  [ ] { } _ / % & @ # * + = < >
#       expanded to spoken words in every context.
#
# The spoken expansions are plain Basque words, so they fall through the normal
# engine and get phonemised; we only need to emit the right word sequence.

# AhoTTS eu_symbolexp[256] (symbolexp.c) -- the authoritative per-character
# spoken expansion used by eu_speller / eu_numexp.  The symbol-verbalisation
# words below are taken from this table (NOT invented): the only deviation is the
# combined modulo1y2+wrapper rendering of a mid-glued double-quote, which the V3
# pipeline reads as "koma" rather than the raw symbolexp "komatxo bikoitzak"
# (probe-validated; `a"b` -> a koma be, `a " b` behaves like `,`).
_SYM_PUNCT = {
    '!': "harridura ikurra", '#': "almohadilla", '$': "dolar",
    '%': "ehuneko", '&': "eta", '(': "ireki parentesia",
    ')': "itxi parentesia", '*': "izartxo", '+': "gehiketaren ikurra",
    ',': "koma", '-': "gidoia", '.': "puntu", '/': "barra",
    ':': "bi puntu", ';': "puntu eta koma", '<': "txikiago", '=': "berdin",
    '>': "handiago", '?': "galdera ikurra", '@': "arroba",
    '[': "ireki markoa", '\\': "atzerantzako barra", ']': "itxi markoa",
    '^': "azentu zirkunflexu", '_': "beheko gidoia", '{': "ireki giltza",
    '|': "barra bertikala", '}': "itxi giltza", '~': "tilde",
}
# mid-glued structural punctuation -> spoken Basque word(s).  Values are the
# eu_symbolexp entries above (only `"` deviates -> "koma", documented).
_SYM_MID = {
    '.': _SYM_PUNCT['.'], ',': _SYM_PUNCT[','], ';': _SYM_PUNCT[';'],
    ':': _SYM_PUNCT[':'], '!': _SYM_PUNCT['!'], '?': _SYM_PUNCT['?'],
    '(': _SYM_PUNCT['('], ')': _SYM_PUNCT[')'],
    '"': "koma",
}
# always-verbalised punctuation -> spoken Basque word(s) (eu_symbolexp).
_SYM_ALWAYS = {
    '[': _SYM_PUNCT['['], ']': _SYM_PUNCT[']'],
    '{': _SYM_PUNCT['{'], '}': _SYM_PUNCT['}'],
    '_': _SYM_PUNCT['_'], '/': _SYM_PUNCT['/'], '%': _SYM_PUNCT['%'],
    '&': _SYM_PUNCT['&'], '@': _SYM_PUNCT['@'], '#': _SYM_PUNCT['#'],
    '*': _SYM_PUNCT['*'], '+': _SYM_PUNCT['+'], '=': _SYM_PUNCT['='],
    '<': _SYM_PUNCT['<'], '>': _SYM_PUNCT['>'],
}
_STRUCTURAL = set(_SYM_MID) | set("-«»")
_WORDCH_RE = re.compile(r"\w", re.UNICODE)


def _is_wordch(ch):
    return bool(ch) and bool(_WORDCH_RE.match(ch))


def _normalize_v3(text):
    """Reproduce modulo1y2 -TxtMode=Word symbol/punctuation normalisation.

    Number / percent / thousands expansion is handled later by _expand_tokens
    (same eu_numexp source); here we only resolve the symbol-verbalisation and
    quote/dash rules so the downstream tokeniser sees what the binary's
    normaliser would have emitted.
    """
    # eu_decli: a `word-suffix` where the suffix is a recognised case-declension
    # form is a *declension hyphen* -- modulo1y2 glues it (Arnold-ek->arnoldek,
    # AEK-k->aekek, word-en->uorden), unlike a compound hyphen (euskal-erria,
    # Bilbo-Concordia) which stays a word boundary.  Probe-validated as V3-only;
    # the V1/V2 (transcribe) path leaves it split.  Resolve it before the
    # char-by-char pass by deleting the hyphen so the two parts glue.
    text = re.sub(
        r'(\w)-(' + '|'.join(sorted(_DECL_SUFFIX, key=len, reverse=True)) +
        r')\b', r'\1\2', text)
    out = []
    n = len(text)
    for i, ch in enumerate(text):
        prev = text[i - 1] if i > 0 else ''
        nxt = text[i + 1] if i + 1 < n else ''
        mid = _is_wordch(prev) and _is_wordch(nxt)
        # a '.' that separates a digit from a 3-digit group is a thousands
        # separator -- leave it for _merge_thousands, do NOT verbalise it.
        if ch == '.' and prev.isdigit() and \
                re.match(r'\d{3}(?!\d)', text[i + 1:i + 5] + '    '):
            out.append('.')
            continue
        if ch in _SYM_ALWAYS:
            out.append(' ' + _SYM_ALWAYS[ch] + ' ')
        elif ch == '-':
            # mid-glued hyphen -> word split (removed); else literal
            out.append(' ' if mid else ch)
        elif ch in ('«', '»'):
            # mid-glued guillemet -> joined (removed); else ASCII apostrophe
            out.append('' if mid else "'")
        elif ch in _SYM_MID:
            out.append(' ' + _SYM_MID[ch] + ' ' if mid else ch)
        else:
            out.append(ch)
    return ''.join(out)


# ==========================================================================
# Top level
# ==========================================================================
_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)
_PUNCT = set(".,!?;:")
# Python string.punctuation -- the exact set getPhonemes emits as its own
# tokens.  Used for the V3 (modulo1y2 + eu_phonemizer) tokenisation.
import string as _string  # noqa: E402
_STRING_PUNCT = set(_string.punctuation)
_KEEP_PUNCT = set(".,!?;:")     # punctuation surfaced in V3 output
# V3: literal punct tokens that break the pause group (probe-validated).  Every
# string.punctuation char breaks coarticulation/stress EXCEPT the apostrophe.
_V3_BREAK_PUNCT = (_STRING_PUNCT - {"'"})


_ACCENT_REPL = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ü': 'u',
                'à': 'a', 'è': 'e', 'ì': 'i', 'ò': 'o', 'ù': 'u', 'ç': 'z',
                # circumflex -> base vowel (symbolexp.c folds Á/É/Í/Ó/Ú to the
                # bare letter; eu_t2l accent handling).  Without this a foreign
                # "nô" drops the vowel; the binary keeps it (n -> nO).
                'â': 'a', 'ê': 'e', 'î': 'i', 'ô': 'o', 'û': 'u'}


def _normalize_word(word):
    return ''.join(_ACCENT_REPL.get(ch, ch) for ch in word.lower())


def _normalize_word_keepcase(word):
    """Accent-stripped but case-preserving form, for the case-sensitive
    searchBin block selection used by the SALBTF phonetic exceptions."""
    repl = dict(_ACCENT_REPL)
    repl.update({k.upper(): v.upper() for k, v in _ACCENT_REPL.items()})
    return ''.join(repl.get(ch, ch) for ch in word)


def phonemize(text, version="v1"):
    """text -> final single-char IPA training string for the given AhoTTS
    version ("v1", "v2", "v3").  Words space-separated.  For v3, punctuation is
    emitted as separate tokens (matching the modulo1y2 + eu_phonemizer
    pipeline); v1/v2 drop punctuation (the libhtts/transcribe pipeline returns
    words only)."""
    if version not in _CONFIG:
        raise ValueError("version must be v1, v2 or v3")
    cfg = _CONFIG[version]
    keep_punct = cfg["keep_punct"]

    text = re.sub(r'\.{2,}', '.', text)
    if keep_punct:
        # V3: run the modulo1y2 text-normaliser (symbol verbalisation, quote /
        # dash rules) before tokenising, exactly as eu_phonemizer.normalize ->
        # getPhonemes does.  getPhonemes re-tokenises with \w+|[^\w\s] and emits
        # every string.punctuation char as its own token.
        text = _normalize_v3(text)
    tokens = _TOKEN_RE.findall(text)
    tokens = _expand_tokens(tokens, version)

    # which punctuation chars survive as literal output tokens
    punct_out = _STRING_PUNCT if keep_punct else _PUNCT
    seq = []
    for tok in tokens:
        if tok in _PUNCT:
            seq.append(('p', tok))            # pause boundary + maybe emitted
        elif keep_punct and tok in _V3_BREAK_PUNCT:
            # V3 (modulo1y2): EVERY literal punctuation token breaks the pause
            # group -- probe-validated.  `a ( da` / `a , da` / `a : da` /
            # `a - da` / `a " da` all surface plosive `dA` (broken
            # coarticulation) and re-stress the following monosyllable, exactly
            # as a comma/period does.  The lone exception is the ASCII
            # apostrophe (from «» / C's), which does NOT break (`a ' da` keeps
            # approximant ðA) -- it stays a non-breaking literal token below.
            seq.append(('p', tok))
        elif tok in ('-', '–', '—') and not keep_punct:
            # eu_phtr.cpp keeps a hyphen-glued compound (bete-betean, jakin-min,
            # idazle-belaunaldi) in ONE pause group: the hyphen is removed and
            # the two parts stay phonetically adjacent, so cross-part
            # coarticulation (b->beta, n->m) fires.  Drop the hyphen token so
            # the surrounding words sit contiguously in the same g2p group.
            continue
        elif tok in ('«', '»', '"', '“', '”') and not keep_punct:
            # V1/V2 (libhtts/transcribe path): quotation marks are NOT pause
            # breaks -- the binary keeps coarticulation across them (dira
            # «diskurtso -> ...ðiɾA ðiskUrVo: the d of "diskurtso" approximates
            # after the vowel of "dira").  Drop the quote so the words stay
            # adjacent in the same g2p group, like the hyphen above.
            continue
        elif tok in punct_out and len(tok) == 1 and not tok.strip().isalnum():
            seq.append(('t', tok))            # literal token, NOT a pause break
        elif tok.strip():
            seq.append(('w', tok))

    # --- sentence-wide POS tagging + poscases (eu_categ.cpp::utt_categ) -------
    # The categoriser and the poscases disambiguation pass run once over the
    # WHOLE utterance's word list (wordFirst()..wordLast()), with neighbour
    # look-ups (wordPrev/wordNext) and the wordIsLast(URANGE_SENTENCE) tests
    # crossing pause/comma boundaries.  So tag every spoken word of the sentence
    # here, resolve poscases across the whole list, and hand each phrase its tag
    # slice -- rather than re-running poscases per phrase (which would see a
    # phrase edge as a sentence edge and mis-fire the izejok/adjjok/jntazk
    # `last` branches at every comma).
    sent_words = [_normalize_word(tok) for (k, tok) in seq if k == 'w']
    # boundary_after[w] = a pause/punct cell ('p') separates word w from word
    # w+1 (or w is the last word).  This is what the C poscases neighbour
    # look-ups respect: a pause cell sits between the two word cells, so
    # wordNext across it / wordIsLast(SENTENCE) behave as a boundary.  Used by
    # the dena-special, izejok/adjjok and jntazk `last`/`next` tests so that a
    # word adjacent to punctuation is treated as phrase/sentence-final.
    boundary_after = []          # any pause cell follows (phrase or sentence)
    sent_end_after = []          # a SENTENCE terminator (. ! ?) follows
    _SENT_TERM = {'.', '!', '?'}
    wi_pos = [idx for idx, (k, _t) in enumerate(seq) if k == 'w']
    for n_, pos in enumerate(wi_pos):
        if n_ + 1 >= len(wi_pos):
            boundary_after.append(True)             # last word of utterance
            sent_end_after.append(True)
        else:
            nxt_pos = wi_pos[n_ + 1]
            between = [seq[j] for j in range(pos + 1, nxt_pos) if seq[j][0] == 'p']
            boundary_after.append(bool(between))
            sent_end_after.append(any(c in _SENT_TERM for (_k, c) in between))
    sent_tags = None
    if cfg["accentual"]:
        flags_all = _dict_for(version)[1]
        sent_tags = [_tag_word(w, flags_all, version) for w in sent_words]
        _poscases(sent_tags, sent_words, boundary_after, sent_end_after)

    out_tokens = []
    i = 0
    word_cursor = 0          # index into sent_words / sent_tags
    while i < len(seq):
        kind = seq[i][0]
        if kind == 'p':
            if keep_punct:
                out_tokens.append(seq[i][1])
            i += 1
            continue
        if kind == 't':
            out_tokens.append(seq[i][1])
            i += 1
            continue
        # a phrase = a run of words (and non-breaking literal punct tokens)
        # bounded by pause punctuation; stress groups span it.
        group = []
        group_idx = []
        while i < len(seq) and seq[i][0] in ('w', 't'):
            group_idx.append(i)
            if seq[i][0] == 'w':
                group.append(seq[i][1])
            i += 1
        norm = [_normalize_word(w) for w in group]
        # case-preserving (accent-stripped) forms for the case-sensitive
        # SALBTF block selection in searchBin (pos1.cpp::posdic).
        orig = [_normalize_word_keepcase(w) for w in group]
        phrase_tags = None
        if sent_tags is not None:
            phrase_tags = sent_tags[word_cursor:word_cursor + len(norm)]
        word_cursor += len(norm)
        sc_lists = _group_to_singlechar(norm, version,
                                        phrase_last_index=len(norm) - 1,
                                        orig_words=orig, pre_tags=phrase_tags,
                                        raw_words=group)
        # re-interleave phonemised words with the literal punct tokens that sit
        # inside the phrase (e.g. an inline "(" or "'")
        wi = 0
        for gi in group_idx:
            if seq[gi][0] == 't':
                out_tokens.append(seq[gi][1])
                continue
            sc = sc_lists[wi]
            # ez + z-initial verb: "ez" loses its z (eu_phtr z-case); accentual
            # path only (the flat V2 path does not apply the proclitic sandhi).
            if cfg["accentual"] and norm[wi] == "ez" and wi + 1 < len(norm) \
                    and norm[wi + 1].startswith("z"):
                out_tokens.append("e")
            elif sc:
                out_tokens.append(sc)
            wi += 1
    return ' '.join(out_tokens)


if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else "Euskara Euskal Herriko hizkuntza da."
    for v in ("v1", "v2", "v3"):
        print(f"{v}: {phonemize(t, version=v)}")
