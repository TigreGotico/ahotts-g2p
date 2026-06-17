# Licensing

`ahotts-g2p` is licensed under the **Apache License 2.0** (see
[`../LICENSE`](../LICENSE)).

## Clean-room reimplementation

The upstream AhoTTS engine is distributed by Aholab under the GNU GPL. This
package is an **independent, clean-room pure-Python reimplementation** of the
AhoTTS grapheme-to-phoneme behaviour:

- **No AhoTTS source code is copied, linked, vendored, or included.** There is
  no C/C++ in this repo and no GPL-licensed code.
- The algorithms (g2p rules, syllabification, stress assignment, SAMPA/IPA
  mapping) were reimplemented from scratch in Python from the documented
  behaviour and the public source's design.
- This is the same approach as
  [pycotovia](https://github.com/TigreGotico/pycotovia), the pure-Python
  reimplementation of Cotovia.

Because no GPL code is incorporated, the Python implementation is distributed
under Apache-2.0, consistent with org policy.

## Credit

The AhoTTS algorithms and the bundled Basque dictionary (`eu_dicc.dic`) are the
work of **Aholab Signal Processing Laboratory, University of the Basque Country
(UPV/EHU)**. This credit is recorded in [`../NOTICE`](../NOTICE), as required by
the Apache-2.0 license, and does not imply endorsement by Aholab or UPV/EHU.

- AhoTTS: <https://aholab.ehu.eus/>
- Source: <https://github.com/aholab/AhoTTS>

## The dictionary data file

`eu_dicc.dic` is the AhoTTS Basque lexicon, shipped as package data and read at
runtime from its on-disk HDIC binary format. It is data consumed by the
reimplemented algorithms, credited to Aholab in `NOTICE`.
