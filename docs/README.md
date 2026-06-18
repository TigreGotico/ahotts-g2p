# ahotts-g2p documentation

Pure-Python, zero-dependency AhoTTS grapheme-to-phoneme for Basque and Spanish.

## Contents

- [Installation](installation.md) -- requirements and install options.
- [Usage](usage.md) -- the public API, CLI, and common recipes.
- [Versions](versions.md) -- the AhoTTS V1/V2/V3 engine lineage and what each
  produces; what this release implements.
- [Architecture](architecture.md) -- the text -> phoneme pipeline and the HDIC
  dictionary decode.
- [Methodology](methodology.md) -- how the port was produced and how parity
  with the AhoTTS binaries is verified.
- [Accuracy](accuracy.md) -- the StyleTTS2-eu oracle and per-version parity
  status.
- [Licensing](licensing.md) -- GPL-3.0 (matching upstream), why this is a
  source-derived (not clean-room) port, and the AhoTTS / Aholab credit.

## Quick start

```python
from ahotts_g2p import phonemize
phonemize("Bai.")              # 'bAj .'
```

See the runnable scripts under [`../examples/`](../examples).
