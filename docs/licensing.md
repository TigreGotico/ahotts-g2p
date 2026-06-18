# Licensing

`ahotts-g2p` is licensed under the **GNU General Public License v3.0 or later**
(see [`../LICENSE`](../LICENSE)).

## Why GPL-3.0

The upstream AhoTTS engine is distributed by **Aholab (UPV/EHU)** under the
GPL-3.0. This package is a derivative work: it reimplements the AhoTTS
linguistic rules (normalisation, grapheme-to-phoneme, syllabification, lexical
stress, dictionary decode) and ships the AhoTTS dictionaries. A derivative of
GPL-3.0 work is distributed under the same terms, so this project is GPL-3.0 to
honour the original work.

No upstream C/C++ source text is copied verbatim, and no compiled GPL code is
linked at runtime; the licence follows from the derived algorithms and the
bundled dictionary data.

## Credit

The AhoTTS algorithms and the bundled Basque/Spanish dictionaries
(`eu_dicc_v1.dic`, `eu_dicc_v3.dic`, `es_dicc.dic`) are the work of the
**Aholab Signal Processing Laboratory, University of the Basque Country
(UPV/EHU)**. This credit does not imply endorsement by Aholab or UPV/EHU.

- AhoTTS: <https://aholab.ehu.eus/>
- Source: <https://github.com/aholab/AhoTTS>
- Version-to-source mapping: [versions.md](versions.md).

## The dictionary data files

`eu_dicc_v1.dic`, `eu_dicc_v3.dic`, and `es_dicc.dic` are the AhoTTS lexicons,
shipped as package data and read at runtime from their on-disk HDIC binary
format. They are produced by Aholab and distributed here under the same GPL-3.0
terms as the upstream engine.
