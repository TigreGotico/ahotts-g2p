"""HDIC binary-dictionary reader tests.

The ``.dic`` files are AhoTTS HDIC databases shipped as package data; the
reader decodes their four sorted blocks and the per-word HDicRef bitfield with
the stdlib ``struct`` module only.
"""
import os

import pytest

from ahotts_g2p import dict_hdic

_PKG = os.path.dirname(dict_hdic.__file__)
_DICTS = [
    os.path.join(_PKG, "eu_dicc_v1.dic"),
    os.path.join(_PKG, "eu_dicc_v3.dic"),
]


def test_dict_files_present():
    for path in _DICTS:
        assert os.path.exists(path), path


@pytest.mark.parametrize("path", _DICTS)
def test_load_hdic_four_blocks(path):
    blocks, entries = dict_hdic.load_hdic(path)
    assert len(blocks) == 4
    assert len(entries) > 10000  # main lexicon is ~17k words


@pytest.mark.parametrize("path", _DICTS)
def test_build_lookup_flag_schema(path):
    lut = dict_hdic.build_lookup(path)
    assert len(lut) > 10000
    sample = next(iter(lut.values()))
    for key in ("str_mrk", "n_n", "i_j", "j_x", "l_l", "z_t", "tf_mrk"):
        assert key in sample
        assert isinstance(sample[key], bool)


@pytest.mark.parametrize("path", _DICTS)
def test_str_mrk_population(path):
    """The first-syllable lexical-stress flag is set on a real subset."""
    lut = dict_hdic.build_lookup(path)
    marked = [w for w, v in lut.items() if v["str_mrk"]]
    assert marked


@pytest.mark.parametrize("path", _DICTS)
def test_no_palatal_n_population(path):
    """The no-n-palatalisation flag generalises well beyond a curated set."""
    lut = dict_hdic.build_lookup(path)
    n_n = [w for w, v in lut.items() if v["n_n"]]
    assert len(n_n) > 100


def test_decode_ref_round_trips_known_bits():
    flags = dict_hdic.decode_ref(0)
    assert flags["str_mrk"] is False
    assert flags["bits"] == 0
