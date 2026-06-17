"""Faithful port of LangEU_HDicDB::searchBin + HDicDB::tokbsearch.

Operates on the 4 sorted blocks exactly as the C does: per-block binary search
comparing raw latin-1 bytes via strncmp over the overlap, with the *stateful*
hitlen class member shared across the 4 tokbsearch calls and NOT reset between
them in the full-token pass (it IS reset to 0 each partial-search iteration).
"""
try:
    from . import decode_hdic as D
except ImportError:  # pragma: no cover - standalone script use
    import decode_hdic as D


def _strncmp(a, b, n):
    # compare first n bytes as C strncmp on unsigned char
    a = a[:n]; b = b[:n]
    for x, y in zip(a, b):
        if x != y:
            return -1 if x < y else 1
    if len(a) != len(b):
        return -1 if len(a) < len(b) else 1
    return 0


class FaithfulHDic:
    def __init__(self, path):
        blocks, entries = D.load_hdic(path)
        from collections import defaultdict
        bb = defaultdict(list)
        for e in entries:
            bb[e['block']].append(e)
        # store raw byte strings per block in DISK ORDER (already disk order)
        self.blk = []
        for bi in range(4):
            es = bb[bi]
            # word bytes (case: blocks 0/1 raw, 2/3 lowercased stored)
            self.blk.append([(e['word'].encode('latin-1'), e) for e in es])
        self.hitlen = 0

    def tokbsearch(self, tok, bi):
        """Return idx into block bi of the longest entry that is a prefix-match
        (per the C overlap-strncmp), updating self.hitlen. tok is bytes."""
        arr = self.blk[bi]
        toklen = len(tok)
        l, u = 0, len(arr)
        hit = -1
        while l < u:
            idx = (l + u) // 2
            buf = arr[idx][0]
            blen = len(buf)
            comparison = _strncmp(tok, buf, min(blen, toklen))
            if comparison == 0:
                if blen > toklen:
                    comparison = -1
                else:
                    if blen > self.hitlen:
                        self.hitlen = blen
                        hit = idx
                    if blen < toklen:
                        comparison = 1
                    else:
                        break
            if comparison < 0:
                u = idx
            else:
                l = idx + 1
        return hit

    def search(self, token):
        """Faithful searchBin. token: str. Returns (entry, hitlen, toklen, block)
        or (None,...) if not found."""
        tok = token.encode('latin-1')
        tokl = token.lower().encode('latin-1')
        toklen = len(tok)
        self.hitlen = 0
        hit = [0, 0, 0, 0]
        hit[0] = self.tokbsearch(tok, 0)
        hit[1] = self.tokbsearch(tok, 1)
        hit[2] = self.tokbsearch(tokl, 2)
        hit[3] = self.tokbsearch(tokl, 3)
        i = 0
        notFound = False
        if hit[3] >= 0: i = 3
        elif hit[2] >= 0: i = 2
        elif hit[1] >= 0: i = 1
        elif hit[0] >= 0: i = 0
        else: notFound = True

        if notFound or (toklen != self.hitlen):
            parLen = toklen - 1
            contSrch = True
            toklen_old = toklen
            if parLen == 0:
                contSrch = False
            while contSrch:
                partial = tok[:parLen]
                partiall = token[:parLen].lower().encode('latin-1')
                toklen = parLen
                self.hitlen = 0
                hit[0] = self.tokbsearch(partial, 0)
                hit[1] = self.tokbsearch(partial, 1)
                hit[2] = self.tokbsearch(partiall, 2)
                hit[3] = self.tokbsearch(partiall, 3)
                if hit[3] >= 0: i = 3
                elif hit[2] >= 0: i = 2
                elif hit[1] >= 0: i = 1
                elif hit[0] >= 0: i = 0
                else: notFound = True
                if self.hitlen == parLen:
                    notFound = False
                    contSrch = False
                else:
                    notFound = True
                parLen -= 1
                if parLen == 0:
                    contSrch = False
            toklen = toklen_old
            if notFound:
                return None, self.hitlen, toklen, None
        entry = self.blk[i][hit[i]][1]
        return entry, self.hitlen, toklen, i


if __name__ == "__main__":
    import sys
    h = FaithfulHDic('eu_dicc_v1.dic')
    for w in sys.argv[1:]:
        e, hl, tl, bi = h.search(w)
        if e:
            print(f"{w:14s} -> matched {e['word']!r} block={bi} hitlen={hl} toklen={tl} str_mrk={e['flags']['str_mrk']} MATCHLEN={'full' if hl==tl else hl}")
        else:
            print(f"{w:14s} -> NOT FOUND (hitlen={hl})")


def query_matchlen(hl, tl):
    return 0 if hl == tl else hl


def atzize_found(h, word_act):
    """Faithful port of LangEU_Categ::atzize: strip leading chars, search the
    suffix, and if it matches TALDE2==ATZ_IZE with full match (tam==0) ->
    encontrado=TRUE. Returns True if a noun suffix was found."""
    L = len(word_act)
    len_atz = 0
    while len_atz != L:
        atzizki = word_act[len_atz:]
        # C: atzizki[++len_atz2]='\0' adds an extra char of garbage but the
        # searched C-string is still `atzizki` up to first NUL == the suffix.
        e, hl, tl, bi = h.search(atzizki)
        tam = query_matchlen(hl, tl) if e else 0
        if e:
            f = e['flags']
            # TALDE2 ATZ_IZE check
            bits = e['ref_bits']
            t2 = (bits >> 6) & 7
            if t2 == 4 and tam == 0:  # ATZ_IZE answer code = 4
                return True, atzizki
        len_atz += 1
    return False, None
