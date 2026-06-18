# ahotts-g2p documentation

Pure-Python, zero-dependency AhoTTS grapheme-to-phoneme for Basque and Spanish.

## Contents

- [Installation](installation.md) -- requirements and install options.
- [Usage](usage.md) -- the public API, CLI, and common recipes.
- [Versions](versions.md) -- the AhoTTS V1/V2/V3 lineage, the upstream source
  and consuming model for each, and the behavioural signatures.
- [Architecture](architecture.md) -- the module layout, the text -> phoneme
  pipeline, and the HDIC dictionary decode.
- [Methodology](methodology.md) -- how correctness is defined and verified.
- [Reverse engineering](reverse-engineering.md) -- the binary <-> source <->
  model mapping and how each version was identified.
- [Accuracy](accuracy.md) -- the per-version parity figures.
- [Licensing](licensing.md) -- GPL-3.0 (matching upstream) and the AhoTTS /
  Aholab credit.

## Quick start

```python
from ahotts_g2p import phonemize
phonemize("Bai.")              # 'bAj .'
```

See the runnable scripts under [`../examples/`](../examples).
