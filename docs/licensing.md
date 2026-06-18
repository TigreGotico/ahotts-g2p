# Licensing

`ahotts-g2p` is licensed under the **GNU General Public License v3.0 (or later)**
(see [`../LICENSE`](../LICENSE)).

## Why GPL-3.0 (and not a permissive licence)

The upstream AhoTTS engine is distributed by **Aholab (UPV/EHU)** under the
**GPL-3.0**. This package is a **source-derived** port of the AhoTTS linguistic
behaviour: an AI assistant read the public AhoTTS C/C++ source and reimplemented
the algorithms in Python under human guidance, with every result validated
against the real AhoTTS binaries.

Because the implementation was **derived from GPL-3.0 source**, the honest and
upstream-respecting choice is to license this port under the **same GPL-3.0**.
We do this to honour the original AhoTTS work, not because org policy prefers a
permissive licence.

## This is NOT a clean-room reimplementation

We explicitly do **not** claim a clean-room process. In a clean-room port the
implementers are walled off from the original source and work only from a
behavioural specification. Here, the implementing agent **read the upstream GPL
source**, so the clean-room defence does not apply and would be misleading to
claim.

No upstream C/C++ source text is copied verbatim into this repo, and there is no
compiled GPL code linked at runtime — but the *algorithms* are derived from the
GPL source, which is what matters for licensing.

## Open questions (transparency, not legal advice)

We are not lawyers. We want downstream users to be aware that some questions here
are genuinely unsettled:

- **Was this clean-room?** No — see above.
- **Can it be relicensed (MIT/Apache/etc.)?** Almost certainly not. A port
  derived from GPL-3.0 source is a derivative work; we keep GPL-3.0.
- **Can an AI originate or "assign" a licence?** Unclear. The authorship and
  copyright status of AI-generated code is legally unsettled, and a licence is a
  grant by a rights-holder whose identity is uncertain here. We apply GPL-3.0 as
  the conservative default rather than asserting any novel rights.

If you redistribute or build on this, treat it as **GPL-3.0** and seek your own
advice if the above questions matter to your use.

## Credit

The AhoTTS algorithms and the bundled Basque/Spanish dictionaries
(`eu_dicc_v1.dic`, `eu_dicc_v3.dic`, `es_dicc.dic`) are the work of **Aholab
Signal Processing Laboratory, University of the Basque Country (UPV/EHU)**. This
credit does not imply endorsement by Aholab or UPV/EHU.

- AhoTTS: <https://aholab.ehu.eus/>
- Source: <https://github.com/aholab/AhoTTS>
- The lineage and which binary each version maps to: [versions.md](versions.md).

## The dictionary data files

`eu_dicc_v1.dic`, `eu_dicc_v3.dic`, and `es_dicc.dic` are the AhoTTS lexicons,
shipped as package data and read at runtime from their on-disk HDIC binary
format. They are produced by Aholab and distributed here under the same GPL-3.0
terms as the upstream engine.
