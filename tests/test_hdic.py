"""HDIC dictionary load tests (eu_dicc.dic shipped as package data)."""
from ahotts_g2p import ahotts_eu_hdic as A
from ahotts_g2p import decode_hdic


def test_dict_loaded():
    # the bundled dictionary parsed into the live flag table
    assert isinstance(A.DICT_FLAGS, dict)
    assert len(A.DICT_FLAGS) > 10000  # main lexicon is ~17k unique words


def test_dict_path_is_package_data():
    assert A._DICT_PATH.endswith("eu_dicc.dic")
    import os
    assert os.path.exists(A._DICT_PATH)


def test_flag_fields_present():
    # pick any entry, confirm decoded flag schema
    sample = next(iter(A.DICT_FLAGS.values()))
    for key in ("str_mrk", "n_n", "i_j", "j_x", "l_l", "z_t", "tf_mrk"):
        assert key in sample
        assert isinstance(sample[key], bool)


def test_str_mrk_flag_drives_first_syllable_stress():
    # at least some words carry the first-syllable STR_MRK flag
    marked = [w for w, v in A.DICT_FLAGS.items() if v["str_mrk"]]
    assert marked


def test_no_palatal_n_flag_population():
    # the N_J_N flag generalises beyond a tiny curated set
    n_n = [w for w, v in A.DICT_FLAGS.items() if v["n_n"]]
    assert len(n_n) > 100


def test_decode_hdic_standalone_loader():
    blocks, entries = decode_hdic.load_hdic(A._DICT_PATH)
    assert len(blocks) == 4
    assert len(entries) > 10000
    lut = decode_hdic.build_lookup(A._DICT_PATH)
    assert lut
