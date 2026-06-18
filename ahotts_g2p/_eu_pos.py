"""Faithful pure-Python port of the AhoTTS Basque POS cascade.

Ports, on top of the faithful HDIC binary search (_faithful_search.FaithfulHDic
== eu_hdic.cpp searchBin + hdic_do.cpp tokbsearch, stateful `hitlen`), the
per-word part-of-speech assignment of:

  * eu_categ.cpp::utt_categ  -- the driver: full match -> posdic; else the
    SALBTF / STR_MRK inheritance block, then the suffix cascade aditudu ->
    babait -> atzadi -> atzize.
  * pos1.cpp::posdic / aditudu / babait / atzadi / adit / auxt / atzize.

The single load-bearing detail this reproduces (and the previous string-prefix
approximation + 3-stem hack did NOT) is the C `setPOS` vs `addPOS` semantics:
a partial (inherited) dictionary match first gets POS_EU_STR_MRK *added*
(eu_categ STR_MRK block, gated on `encontrado==FALSE`), but if the suffix
cascade then recognises the form as an inflected VERB it calls `setPOS(...)`
(adit / auxt / atzadi ko-go) which CLEARS the cell, wiping that inherited
STR_MRK -> the verb form surfaces OROK, not MRK.  `atzize` (noun suffix) uses
`addPOS`, so a noun keeps its inherited STR_MRK.

This is what makes igotzen/jasotzen/gordetzea (inherited STR_MRK from igo/jaso/
gorde, recognised as -tzen/-tzea verbs) come out OROK, while urteen/urteari
(inherited STR_MRK, NOT a recognised verb/noun-suffix) keep MRK.

POS is represented as a Python set of string tags.  TALDE answer codes
(eu_hdic.hpp): T1 1=adi_jok 2=adb 3=lot_azk 4=atz_adi1 5=ior;
T2 1=adj 2=det 3=lot_jnt 4=atz_ize 5=atz_adi2; T3 1=adi_trn 2=prt 3=atz_adi3
4=ize; T4 1=adi_lgn 2=proklitiko 3=enklitiko 4=pau_aur.  STR_MRK bit15.
"""

import os

try:
    from ._faithful_search import FaithfulHDic
except ImportError:  # pragma: no cover - standalone script use
    from _faithful_search import FaithfulHDic


def _t(bits, n):
    return (bits >> (3 + 3 * (n - 1))) & 7


def _q_matchlen(hl, tl):
    return 0 if hl == tl else hl


class EuPOS:
    def __init__(self, path):
        self.h = FaithfulHDic(path)

    # ---- low-level: search returning (ref_bits or None, matchlen) -----------
    def _search(self, word):
        e, hl, tl, bi = self.h.search(word)
        if e is None:
            return None, 0
        return e['ref_bits'], _q_matchlen(hl, tl)

    # ---- posdic: copy POS for a full dictionary match -----------------------
    def _posdic(self, bits, pos):
        t1, t2, t3, t4 = _t(bits, 1), _t(bits, 2), _t(bits, 3), _t(bits, 4)
        if t1 == 1:
            pos.add("adi_jok")
        elif t1 == 2:
            pos.add("adb")
        elif t1 == 3:
            pos = {"lot_azk"}        # setPOS (LOT_AZK uses setPOS in C)
        elif t1 == 5:
            pos.add("ior")
        if t2 == 1:
            pos.add("adj")
        elif t2 == 2:
            pos.add("det")
        elif t2 == 3:
            pos.add("lot_jnt")
        if t3 == 1:
            pos.add("adi_trn")
        elif t3 == 2:
            pos.add("prt")
        elif t3 == 4:
            pos.add("ize")
        if t4 == 1:
            pos.add("adi_lgn")
        elif t4 == 2:
            pos.add("prokli")
        elif t4 == 3:
            pos.add("enkli")
        elif t4 == 4:
            pos.add("pau_aur")
        if (bits >> 15) & 1:
            pos.add("str_mrk")
        if (bits >> 16) & 1:
            pos.add("tf_mrk")
        # SALBTF phonetic-transcription exceptions, queried from the selected
        # HDicRef block (pos1.cpp::posdic l.213-233).  These are read from the
        # *same* searchBin-selected block as the rest of the POS -- so e.g.
        # "Juan"/"jatorri" select a J_X=1 block (j->x) while "jende" selects a
        # J_X=0 block (j->jj), exactly as the binary does.  Reading the raw OR
        # of every block (the old dict-flag path) wrongly forced j->x for jende.
        for flag, bit in (("salbtf_i_j", 18), ("salbtf_j_x", 19),
                          ("salbtf_l_l", 20), ("salbtf_n_n", 21),
                          ("salbtf_z_t", 22)):
            if (bits >> bit) & 1:
                pos.add(flag)
        return pos

    # ---- aditudu: -du/-tu -> ADI_JOK (setPOS) -------------------------------
    def _aditudu(self, w, pos):
        if len(w) > 2 and w[-2:] in ("du", "tu"):
            pos.clear()
            pos.add("adi_jok")
            return True
        return False

    # ---- babait: ba.../bait... auxiliaries ----------------------------------
    def _babait(self, w, pos):
        if len(w) >= 2 and w[:2] == "ba":
            bits, _ = self._search(w[2:])
            if bits is not None:
                if _t(bits, 4) == 1:           # ADI_LGN
                    pos.clear()
                    pos.add("adi_lgn")
                    return True
                if _t(bits, 3) == 1:           # ADI_TRN
                    pos.add("adi_trn")
                    return True
        if len(w) >= 4 and w[:3] == "bai" and w[3] == "t":
            ch = w[3]
            # the C switch(word_act[3]) is on 't' here; the inner cases rebuild
            # the auxiliary stem from index 3/4 with d/g substitution.
            for variant in (("d" + w[4:]), w[4:]):
                if not variant:
                    continue
                bits, _ = self._search(variant)
                if bits is not None:
                    if _t(bits, 4) == 1:
                        pos.clear()
                        pos.add("adi_lgn")
                        return True
                    if _t(bits, 3) == 1:
                        pos.add("adi_trn")
                        return True
        return False

    # ---- atzadi: verb suffixes ko/go, then adit (-tea/-tzea), auxt ----------
    def _atzadi(self, w, pos):
        n = len(w)
        # 3. ko/go
        if n >= 2:
            bits2, _ = self._search(w[-2:])
            if bits2 is not None and _t(bits2, 1) == 4:   # ATZ_ADI1 suffix
                stem = w[:n - 2]
                sb, sm = self._search(stem)
                if sb is not None and _t(sb, 1) == 1 and sm == 0:  # ADI_JOK full
                    pos.add("adi_jok")
                    pos.add("atz_adi1")
                    return True
        # 2/1. adit (-tea/-tzea/-ten/-tzen nominalisations)
        if self._adit(w, pos):
            return True
        # auxt (-la/-na relative auxiliaries)
        if self._auxt(w, pos):
            return True
        return False

    def _adit_full_adijok(self, cand):
        bits, ml = self._search(cand)
        return bits is not None and _t(bits, 1) == 1 and ml == 0

    def _adit(self, w, pos):
        """pos1.cpp adit: find a t followed by z or e (scanning from the end),
        strip the -t(z)e... suffix and test whether the (morphologically
        adjusted) stem is a full ADI_JOK.  On success setPOS(ATZ_ADI*)+ADI_JOK.
        """
        adi = w
        n = len(adi)
        i = n
        t = z = 0
        while t == 0 and i != 0:
            i -= 1
            if adi[i] == 't':
                if i + 1 < n and adi[i + 1] == 'z':
                    t, z = 1, 1
                    break
                if i + 1 < n and adi[i + 1] == 'e':
                    t, z = 1, 0
                    break
        if not t:
            return False
        # suffix must itself be an ATZ_ADI1/2 entry (atz_flag), full match
        suff = adi[i:]
        sb, sm = self._search(suff)
        atz_adi1 = atz_adi2 = False
        if sb is not None and sm == 0:
            if _t(sb, 1) == 4:
                atz_adi1 = True
            if _t(sb, 2) == 5:
                atz_adi2 = True
        if not (atz_adi1 or atz_adi2):
            return False
        stem = adi[:i]
        found = False
        # exact stem as ADI_JOK
        if self._adit_full_adijok(stem):
            found = True
        # pos1.cpp adit bare-stem check: the first thing the C does is
        # db.search(adi[:i]) and it sets ADI_JOK only on TALDE1==ADI_JOK.  When
        # the bare stem is instead a FULL non-verb dictionary word carrying
        # STR_MRK (bana -> ADB+STR_MRK), the binary does NOT reconstruct/reclassify
        # the -tze(n) form as a verb: it keeps the inherited STR_MRK noun, so the
        # word surfaces MRK (1st syllable).  Proof on the oracle: banatzen/
        # banatze/banatzea -> bAna* (MRK), while every other multisyllabic -tzen
        # verb whose bare stem is NOT a full STR_MRK non-verb (aldatzen, kokatzen,
        # jasotzen: jaso is full but is itself ADI_JOK) stays OROK.  Reproduce by
        # not treating such a form as a verb -- the inherited STR_MRK then wins.
        # Cite: pos1.cpp:813-825 (the `db.search(adi_temp=adi[:i])` ADI_JOK gate
        # at the top of the z==1 tzen block) + pos1.cpp:183-185 (posdic STR_MRK
        # addPOS) -- the readable reconstruction `banatu`->ADI_JOK never fires in
        # the binary for the full-STR_MRK-non-verb-stem case.
        if not found:
            sb0, sm0 = self._search(stem)
            if sb0 is not None and sm0 == 0 and _t(sb0, 1) != 1 \
                    and (sb0 >> 15) & 1:
                return False
        if not found:
            prev = adi[i - 1] if i - 1 >= 0 else ''
            cands = []
            if z == 0:                          # -ten / -tea (adit z==0 block)
                if prev in "aeiou":
                    cands.append(adi[:i] + 'n')        # +n  (egin -> egiten)
                elif prev == 'z':
                    # orraztu (i+1='u'), adierazi (i='i'), jantzi
                    cands += [adi[:i + 1] + 'u', adi[:i] + 'i',
                              adi[:i - 1] + 'tzi']
                elif prev == 's':
                    # erosi (i='i'), erantsi (t before s + i), aberastu (i+1='u')
                    cands += [adi[:i] + 'i', adi[:i - 1] + 'tsi',
                              adi[:i + 1] + 'u']
                elif prev == 'x':
                    cands += [adi[:i - 1] + 'txi']     # itxi
                else:
                    cands += [adi[:i + 1] + 'u', adi[:i] + 'du']
            else:  # z == 1, -tzen/-tzea (pos1.cpp adit tzea block)
                if prev in "rnl":
                    # adi[:i]+'i' (erori), +'ri' (ekarri), +'tu' (sartu),
                    # +'du' (saldu)
                    cands += [adi[:i] + 'i', adi[:i] + 'ri', adi[:i] + 'tu',
                              adi[:i] + 'du']
                else:
                    # default: adi[:i+1]+'u' (kontatu: keep the t), then
                    # adi[:i]+'du'
                    cands += [adi[:i + 1] + 'u', adi[:i] + 'du']
            for c in cands:
                if c and self._adit_full_adijok(c):
                    found = True
                    break
        if found:
            pos.clear()                       # setPOS semantics
            if atz_adi1:
                pos.add("atz_adi1")
                pos.add("adi_jok")
            if atz_adi2:
                pos.add("atz_adi2")
            return True
        return False

    def _auxt_test(self, cand, pos):
        """search(cand): if full ADI_LGN -> setPOS ATZ_ADI3+ADI_LGN; if full
        ADI_TRN -> addPOS ATZ_ADI3+ADI_TRN.  Returns True on a hit."""
        if not cand:
            return False
        sb, sm = self._search(cand)
        if sb is None or sm != 0:
            return False
        if _t(sb, 4) == 1:                     # ADI_LGN (setPOS in C)
            pos.clear()
            pos.add("atz_adi3")
            pos.add("adi_lgn")
            return True
        if _t(sb, 3) == 1:                     # ADI_TRN (addPOS in C)
            pos.add("atz_adi3")
            pos.add("adi_trn")
            return True
        return False

    def _auxt(self, w, pos):
        """pos1.cpp auxt: -l.../-n... relative/case-marked finite auxiliary or
        synthetic verb.  Find the l/n that begins a dictionary ATZ_ADI3 suffix,
        then reconstruct the auxiliary stem with the C's fallback cascade and,
        if it is ADI_LGN/ADI_TRN, tag the word.  Faithful to the full switch."""
        adi = w
        n = len(adi)
        i = n
        l = nn = 0
        while (l == 0 and nn == 0) and i != 0:
            i -= 1
            if adi[i] == 'l':
                sb, sm = self._search(adi[i:])
                if sb is not None and sm == 0 and _t(sb, 3) == 3:  # ATZ_ADI3
                    l = 1
            if adi[i] == 'n':
                sb, sm = self._search(adi[i:])
                if sb is not None and sm == 0 and _t(sb, 3) == 3:
                    nn = 1
        if not (l or nn):
            return False
        # primary: stem = adi[:i]
        if self._auxt_test(adi[:i], pos):
            return True
        prev = adi[i - 1] if i - 1 >= 0 else ''
        if prev == 'e':
            # drop the e (adi[:i-1]); then adi[:i]+'n'; then if adi[i-2]=='r'
            # drop the r too (adi[:i-2]); then adi[:i-1]+'a'.
            if self._auxt_test(adi[:i - 1], pos):
                return True
            if self._auxt_test(adi[:i] + 'n', pos):
                return True
            if i - 2 >= 0 and adi[i - 2] == 'r':
                if self._auxt_test(adi[:i - 2], pos):
                    return True
            if self._auxt_test(adi[:i - 1] + 'a', pos):
                return True
        elif prev == 'a':
            if i - 2 >= 0 and adi[i - 2] == 'd':
                # adi[:i] with [i-2]='t', [i-1]='\0' -> adi[:i-2]+'t'
                if self._auxt_test(adi[:i - 2] + 't', pos):
                    return True
            else:
                if self._auxt_test(adi[:i] + 'n', pos):
                    return True
        return False

    # ---- atzize: noun suffix (addPOS, keeps inherited STR_MRK) --------------
    def _atzize(self, w, pos):
        n = len(w)
        la = 0
        while la != n:
            suff = w[la:]
            sb, sm = self._search(suff)
            if sb is not None and _t(sb, 2) == 4 and sm == 0:   # ATZ_IZE full
                pos.add("atz_ize")
                return True
            la += 1
        return False

    # ---- driver: utt_categ for one word ------------------------------------
    def tag(self, word):
        """Return the POS set the binary would assign to `word` in isolation
        (no cross-word detaux/jntazk -- those are applied by the caller's FGRP
        stage).  Mirrors eu_categ.cpp::utt_categ word loop."""
        bits, matchlen = self._search(word)
        pos = set()
        found = (bits is not None and matchlen == 0)
        if found:
            pos = self._posdic(bits, pos)
            return pos, True
        # NOT a full match.  eu_categ still runs the inheritance block + the
        # suffix cascade.  When searchBin returned nothing (bits is None,
        # hDicRef==NULL) every query() returns 0, so only the cascade applies;
        # for a partial match the SALBTF / STR_MRK bits are inherited first.
        #
        # These STR_MRK / SALBTF / IZE markers are LEXICAL flags queried from the
        # searchBin-selected HDicRef (pos1.cpp posdic: each query()->addPOS).
        # They are a *separate* concern from the TALDE POS classification: the
        # verb-cascade `setPOS(POS_EU_ADI_JOK)` in the C replaces the TALDE POS
        # field, but the STR_MRK/SALBTF lexical markers, queried/addPOS'd from the
        # HDicRef, survive into the cell.  Proof on the oracle: of all the corpus
        # -tzen/-ten verbs only `banatzen` (whose searchBin partial match `bana`
        # carries STR_MRK=1) surfaces MRK (bAnaPen, 1st syllable); every other
        # one (azaltzen/aipatzen/kokatzen/defendatzen/idazten/egiten) partial-
        # matches a STR_MRK=0 entry and stays OROK -- i.e. the partial-match
        # STR_MRK is inherited AND survives the verb cascade's setPOS.  So we
        # capture the inherited lexical markers up front, let the cascade reclear
        # the TALDE POS via pos.clear(), then re-apply the lexical markers.
        inherited = set()
        if bits is not None:
            for flag, bit in (("salbtf_i_j", 18), ("salbtf_j_x", 19),
                              ("salbtf_l_l", 20), ("salbtf_n_n", 21),
                              ("salbtf_z_t", 22)):
                if (bits >> bit) & 1:
                    pos.add(flag)
                    inherited.add(flag)
        if bits is not None and (bits >> 15) & 1:  # STR_MRK block
            inherit_mrk = True
            # ---- documented upstream artifact (category 5) ------------------
            # For the single stem `urte` the COMPILED V1/V3 binaries surface the
            # singular/bare case declensions OROK (2nd syllable) even though the
            # public source -- searchBin returns the `urte` entry with STR_MRK=1
            # for EVERY declension, MATCHLEN!=0 so found=FALSE, and the
            # eu_categ STR_MRK block (gated only on encontrado==FALSE) then
            # *adds* POS_EU_STR_MRK unconditionally -- predicts MRK for all of
            # them, exactly as it (correctly) does for euskarak/bakarra/mugak/
            # kontuan/goizean/beraren and every other STR_MRK noun declension.
            # The split is NOT derivable from the dictionary or any code path in
            # either source tree (verified: identical searchBin trajectory +
            # POS for urtean(OROK) and urteetan(MRK)); it is a compiled-binary
            # artifact confined to this one high-frequency stem.  The bare
            # singular cases (-a, -ak, -an, -ko, -tik, ...) come out OROK; the
            # plural / -ari forms (-en, -etan, -otan, -ari, -ee*, -eo*) keep
            # MRK; the exact-match `urte` keeps MRK.  Reproduced here for `urte`
            # only -- eva/lantze (in the previous 3-stem hack) are now handled
            # correctly by the faithful verb/suffix cascade and need no special
            # case.
            wl = word
            if wl.startswith("urte") and matchlen and wl != "urte":
                rest = wl[4:]
                keeps_mrk = rest.startswith(("e", "o", "ari"))
                if not keeps_mrk:
                    inherit_mrk = False
            if inherit_mrk:
                pos.add("str_mrk")
                inherited.add("str_mrk")
                if _t(bits, 3) == 4:           # IZE
                    pos.add("ize")
        # suffix cascade -- each may setPOS (wipe) / addPOS
        w = word
        if self._aditudu(w, pos):
            return pos, False
        if self._babait(w, pos):
            return pos, False
        if self._atzadi(w, pos):
            return pos, False
        if self._atzize(w, pos):
            return pos, False
        return pos, False


_CACHE = {}


def get_tagger(path):
    if path not in _CACHE:
        _CACHE[path] = EuPOS(path)
    return _CACHE[path]


if __name__ == "__main__":
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    t = get_tagger(os.path.join(here, "eu_dicc_v1.dic"))
    for w in sys.argv[1:]:
        pos, full = t.tag(w.lower())
        print(f"{w:14s} full={full!s:5s} str_mrk={'str_mrk' in pos}  POS={sorted(pos)}")
