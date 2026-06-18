"""Standalone HDIC binary-dictionary reader for AhoTTS eu_dicc.dic.

Decodes the full HDIC trie/bin format (4 sorted-array blocks) and exposes,
for every word in the dictionary, its decoded HDicRef bitfield: part-of-speech
groups (TALDE1..4), first-syllable stress flag (STR_MRK), the phonetic
transcription-exception flags (SALBTF_I_J / J_X / L_l / N_J_N / Z_T), the
TF_MRK / PAU_ATZE markers, the NOR (abb/unit/acr) / DEC class, and any
expansion (pronunciation / substitution) string.

On-disk format (authority: pyAhoTTS src/hdic_io.cpp fbinCreate,
hdic_do.cpp tokbsearch, eu_hdic.cpp searchBin, eu_hdic.hpp flag bit layout):

  signature  : b"Aholab aHoTTS HDIC Database\\x1A" + NUL          (28 B)
  type       : CHAR[2]  ("eu")
  version    : UINT32   (little-endian, == 0)
  block 0 hdr: UINT32 base, UINT32 n, UINT16 slen, UINT16 exlen   (cs, exp)
  block 1 hdr: UINT32 base, UINT32 n, UINT16 slen                 (cs, no-exp)
  block 2 hdr: UINT32 base, UINT32 n, UINT16 slen, UINT16 exlen   (ci, exp)
  block 3 hdr: UINT32 base, UINT32 n, UINT16 slen                 (ci, no-exp)
  -> b_base[0] == end-of-header (consistency check in C).

  Each entry in block i is b_blen[i] bytes, laid out as:
      UINT16 len              # length of the word string (excl. NUL)
      CHAR   str[slen]        # word, NUL-terminated, NUL-padded to slen
      UINT32 ref              # the HDicRef bitfield (little-endian)
      (exp blocks only:)
      UINT16 explen           # length of expansion string
      CHAR   exp[exlen]       # expansion, NUL-terminated, NUL-padded to exlen
  so b_blen = 2 + slen + 4              (no-exp)
            = 2 + slen + 4 + 2 + exlen  (exp)
  Entries are sorted by string (binary-searchable). Blocks 0/1 are
  case-sensitive (raw token); blocks 2/3 are case-insensitive (lowercased).

HDicRef bit layout (eu_hdic.hpp HDICQUERY_ENCODE(bit0, nbits)):
  TALDE1 : bits 3..5   (3 bits)   POS group 1
  TALDE2 : bits 6..8   (3 bits)   POS group 2
  TALDE3 : bits 9..11  (3 bits)   POS group 3
  TALDE4 : bits 12..14 (3 bits)   POS group 4
  STR_MRK: bit 15                 first-syllable lexical stress
  TF_MRK : bit 16                 transcription is fully marked (use exp pron)
  PAU_ATZE:bit 17
  SALBTF_I_0_J : bit 18           "i" -> [j]
  SALBTF_J_0_X : bit 19           "j" -> [x]
  SALBTF_L_l_L : bit 20           "l" -> [l] (not [L])
  SALBTF_N_J_N : bit 21           "n" -> [n] (no palatalisation)
  SALBTF_Z_0_T : bit 22           "z" -> [T]
  NOR    : bits 0..1   (2 bits)   1=abb 2=unit 3=acr
  DEC    : bit 2

Pure stdlib (struct), no C build, no subprocess.
"""
import os
import struct

SIGNATURE = b"Aholab aHoTTS HDIC Database\x1A"

# (bit0, nbits) for each query field, from eu_hdic.hpp
Q_NOR = (0, 2)
Q_DEC = (2, 1)
Q_TALDE1 = (3, 3)
Q_TALDE2 = (6, 3)
Q_TALDE3 = (9, 3)
Q_TALDE4 = (12, 3)
Q_STR_MRK = (15, 1)
Q_TF_MRK = (16, 1)
Q_PAU_ATZE = (17, 1)
Q_SALBTF_I_J = (18, 1)
Q_SALBTF_J_X = (19, 1)
Q_SALBTF_L_l = (20, 1)
Q_SALBTF_N_J_N = (21, 1)
Q_SALBTF_Z_T = (22, 1)
# bits 23..30 free; bit 31 = CASE, bits 23..30 also (re)used as MATCHLEN at
# runtime by the C search code, but on disk they are 0 (entries are full words).

TALDE1 = {1: "adi_jok", 2: "adb", 3: "lot_azk", 4: "atz_adi1", 5: "ior"}
TALDE2 = {1: "adj", 2: "det", 3: "lot_jnt", 4: "atz_ize", 5: "atz_adi2"}
TALDE3 = {1: "adi_trn", 2: "prt", 3: "atz_adi3", 4: "ize"}
TALDE4 = {1: "adi_lgn", 2: "proklitiko", 3: "enklitiko", 4: "pau_aur"}
NOR = {1: "abb", 2: "unit", 3: "acr"}


def _getbits(bits, q):
    bit0, nbits = q
    return (bits >> bit0) & ((1 << nbits) - 1)


def decode_ref(bits):
    """Decode a 32-bit HDicRef into a dict of named flags/fields."""
    return {
        "bits": bits,
        "nor": NOR.get(_getbits(bits, Q_NOR)),
        "dec": bool(_getbits(bits, Q_DEC)),
        "talde1": TALDE1.get(_getbits(bits, Q_TALDE1)),
        "talde2": TALDE2.get(_getbits(bits, Q_TALDE2)),
        "talde3": TALDE3.get(_getbits(bits, Q_TALDE3)),
        "talde4": TALDE4.get(_getbits(bits, Q_TALDE4)),
        "str_mrk": bool(_getbits(bits, Q_STR_MRK)),
        "tf_mrk": bool(_getbits(bits, Q_TF_MRK)),
        "pau_atze": bool(_getbits(bits, Q_PAU_ATZE)),
        "i_j": bool(_getbits(bits, Q_SALBTF_I_J)),
        "j_x": bool(_getbits(bits, Q_SALBTF_J_X)),
        "l_l": bool(_getbits(bits, Q_SALBTF_L_l)),
        "n_n": bool(_getbits(bits, Q_SALBTF_N_J_N)),
        "z_t": bool(_getbits(bits, Q_SALBTF_Z_T)),
    }


def _read_header(data):
    off = len(SIGNATURE) + 1               # signature + NUL
    if data[:len(SIGNATURE)] != SIGNATURE:
        raise ValueError("not an HDIC database")
    off += 2                                   # type ("eu")
    off += 4                                   # format version
    blocks = []
    # blocks 0 and 2 have exlen; 1 and 3 do not
    layout = [True, False, True, False]
    for has_exp in layout:
        base, n = struct.unpack_from('<II', data, off)
        off += 8
        slen = struct.unpack_from('<H', data, off)[0]
        off += 2
        if has_exp:
            exlen = struct.unpack_from('<H', data, off)[0]
            off += 2
        else:
            exlen = 0
        if has_exp:
            blen = 2 + slen + 4 + 2 + exlen
        else:
            blen = 2 + slen + 4
        blocks.append(dict(base=base, n=n, slen=slen, exlen=exlen,
                           blen=blen, has_exp=has_exp))
    if off != blocks[0]["base"]:
        raise ValueError("inconsistent HDIC header (base[0] mismatch)")
    return blocks


def _iter_block(data, blk):
    base, n, slen, blen = blk["base"], blk["n"], blk["slen"], blk["blen"]
    has_exp, _exlen = blk["has_exp"], blk["exlen"]
    for k in range(n):
        rec = base + blen * k
        wlen = struct.unpack_from('<H', data, rec)[0]
        word = data[rec + 2:rec + 2 + wlen]
        ref = struct.unpack_from('<I', data, rec + 2 + slen)[0]
        exp = None
        if has_exp:
            ep = rec + 2 + slen + 4
            elen = struct.unpack_from('<H', data, ep)[0]
            exp = data[ep + 2:ep + 2 + elen]
        yield word, ref, exp


def load_hdic(path):
    """Parse eu_dicc.dic. Return (blocks_meta, entries).

    entries: list of dicts {word, word_raw, ref(decoded), exp, block, case}.
    Words are latin-1 decoded. case=True for the case-sensitive blocks (0,1).
    """
    with open(path, 'rb') as fh:
        data = fh.read()
    blocks = _read_header(data)
    case_of = [True, True, False, False]
    entries = []
    for bi, blk in enumerate(blocks):
        for word, ref, exp in _iter_block(data, blk):
            try:
                w = word.decode('latin-1')
            except UnicodeDecodeError:
                continue
            e = decode_ref(ref)
            entries.append({
                "word": w,
                "ref_bits": ref,
                "flags": e,
                "exp": exp.decode('latin-1') if exp else None,
                "block": bi,
                "case": case_of[bi],
            })
    return blocks, entries


def build_lookup(path):
    """Return {lowercased_word: merged-info} aggregating across all 4 blocks.

    A word can appear in several blocks (e.g. case-sensitive acronym + the
    case-insensitive main lexicon). We key by lowercase and merge: flags are
    OR-ed, the pronunciation/expansion is taken from whichever block supplies
    one (preferring exp blocks). POS group strings keep the first non-None.
    """
    _, entries = load_hdic(path)
    out = {}
    for e in entries:
        key = e["word"].lower()
        f = e["flags"]
        cur = out.get(key)
        if cur is None:
            cur = {
                "word": key,
                "str_mrk": False, "tf_mrk": False, "pau_atze": False,
                "i_j": False, "j_x": False, "l_l": False, "n_n": False,
                "z_t": False, "dec": False,
                "nor": None, "talde1": None, "talde2": None,
                "talde3": None, "talde4": None,
                "exp": None, "blocks": [],
            }
            out[key] = cur
        for bf in ("str_mrk", "tf_mrk", "pau_atze", "i_j", "j_x", "l_l",
                   "n_n", "z_t", "dec"):
            cur[bf] = cur[bf] or f[bf]
        for sf in ("nor", "talde1", "talde2", "talde3", "talde4"):
            if cur[sf] is None and f[sf] is not None:
                cur[sf] = f[sf]
        if e["exp"] and not cur["exp"]:
            cur["exp"] = e["exp"]
        cur["blocks"].append(e["block"])
    return out


def _main():
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "eu_dicc.dic")
    blocks, entries = load_hdic(path)
    print("Blocks:")
    for i, b in enumerate(blocks):
        print(f"  [{i}] base={b['base']:>7} n={b['n']:>6} slen={b['slen']:>3}"
              f" exlen={b['exlen']:>3} blen={b['blen']:>3}"
              f" case={'cs' if i < 2 else 'ci'}")
    print(f"Total entries: {len(entries)}")
    lut = build_lookup(path)
    print(f"Unique (lowercased) words: {len(lut)}")
    # quick flag census
    from collections import Counter
    c = Counter()
    for w, v in lut.items():
        for f in ("str_mrk", "tf_mrk", "i_j", "j_x", "l_l", "n_n", "z_t",
                  "dec", "pau_atze"):
            if v[f]:
                c[f] += 1
    print("Flag census:", dict(c))
    # show queried words
    for w in sys.argv[2:]:
        v = lut.get(w.lower())
        print(w, "->", v if v else "NOT FOUND")


if __name__ == "__main__":
    _main()
