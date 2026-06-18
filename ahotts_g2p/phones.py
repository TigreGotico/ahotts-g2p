r"""Phone tables for the AhoTTS Basque (eu) front-end.

Three layers map between representations:

* ``PHEU`` -- AhoTTS grapheme/phone codes (``phone.h`` via ``eu_lingp.hpp``)
  to the single internal phone char the g2p engine works with.
* ``PH_SAMPA`` -- internal phone char to SAMPA (``phone.c`` ``phinfo`` plus the
  ``hts.cpp`` ``HTS_U2W::phone2sampa`` overrides).
* ``SAMPA_TO_IPA`` -- SAMPA to IPA, ordered, longest-token-first so multi-char
  SAMPA tokens (``ts``, ``s\`\``, ``tS``) resolve before single chars.

``MULTI`` then folds the few remaining multi-char IPA sequences and the
apostrophe stress marker onto single training characters.
"""
from collections import OrderedDict

#: AhoTTS phone code -> internal single-char phone (``eu_lingp.hpp`` aliases).
PHEU = {
    'a': 'a', 'e': 'e', 'i': 'i', 'o': 'o', 'u': 'u',
    'iaprox': 'j', 'uaprox': 'w',
    'b': 'b', 'baprox': 'B', 'd': 'd', 'daprox': 'D',
    'g': 'g', 'gaprox': 'G', 'p': 'p', 't': 't', 'k': 'k',
    'm': 'm', 'n': 'n', 'ntilde': 'J', 'f': 'f', 's': 's',
    'z': 'X', 'jj': 'y', 'l': 'l', 'll': 'L', 'r': 'r', 'rr': 'R',
    'x': 'S', 'ts': 'V', 'tZ': 'P', 'tt': 'Q', 'dj': 'K', 'tx': 'C',
    'T': 'T', 'j': 'x',
    # Northern (Iparrahotsa / Iparralde) dialect phones (phone.h):
    #   PH_R  '['  uvular r,  PH_Jb '='  voiced palatal stop /ɟ/,
    #   PH_y  'F'  French rounded vowel /y/.  Distinct internal codes so the
    #   southern alveolar rr ('R') and palatal jj ('y'/'K') are unaffected.
    'uvular': '@', 'Jb': '=', 'y_fr': '#', 'h': 'h',
}

#: Internal phone char -> SAMPA (``phone.c`` + ``hts.cpp`` ``phone2sampa``).
PH_SAMPA = {
    '_': '_', '+': '+', '~': '~',
    'p': 'p', 'b': 'b', 't': 't', 'd': 'd', 'k': 'k', 'g': 'g',
    'm': 'm', 'n': 'n', 'J': 'J', 'C': 'tS', 'B': 'B', 'f': 'f',
    'T': 'T', 'D': 'D', 's': 's', 'y': 'jj', 'x': 'x', 'G': 'G',
    'l': 'l', 'L': 'L', 'r': 'r', 'R': 'rr', 'i': 'i', 'j': 'j',
    'e': 'e', 'a': 'a', 'o': 'o', 'u': 'u', 'w': 'w', 'S': 'S',
    'V': 'ts', 'K': 'gj', 'X': 's`', 'P': 'ts`', 'Q': 'c',
    'v': 'v', 'z': 'z', 'Z': 'Z', 'h': 'h',
    # Northern dialect internal codes -> SAMPA (phone_tosampa / phone.c).
    '@': 'R', '=': 'J\\', '#': 'y',
}

#: SAMPA -> IPA, ordered longest-first.  Includes the stress-marked vowels
#: (``'a`` etc.) so a fully marked transcription resolves without a fallback.
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
    # Northern (Iparrahotsa) dialect SAMPA: uvular r, voiced palatal stop.
    ("R", "ʁ"), ("J\\", "ɟ"),
    ("'i", "'i"), ("'e", "'e"), ("'a", "'a"), ("'o", "'o"), ("'u", "'u"),
])

#: IPA / stress sequences folded onto single training characters.
MULTI = {
    "tʃ": "C", "ts": "V", "tʂ": "P",
    "'i": "I", "'e": "E", "'a": "A", "'o": "O", "'u": "U",
    "pʰ": "H", "kʰ": "K", "tʰ": "T",
}

#: SAMPA -> internal phone char (inverse of ``PH_SAMPA`` plus aliases), used to
#: parse dotted-SAMPA dictionary transcriptions back into phone codes.
SAMPA_TO_INTERNAL = {v: k for k, v in PH_SAMPA.items()}
SAMPA_TO_INTERNAL.update({
    "rr": PHEU['rr'], "gj": PHEU['dj'], "B": PHEU['baprox'],
    "D": PHEU['daprox'], "G": PHEU['gaprox'], "L": PHEU['ll'],
    "J": PHEU['ntilde'], "S": PHEU['x'], "T": PHEU['T'], "x": PHEU['j'],
    "s`": PHEU['z'], "ts`": PHEU['tZ'], "jj": PHEU['jj'], "z": PHEU['z'],
    "á": PHEU['a'], "é": PHEU['e'], "ó": PHEU['o'], "í": PHEU['i'],
    "ú": PHEU['u'],
})
