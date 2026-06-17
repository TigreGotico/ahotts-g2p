# ahotts-g2p documentation

Pure-Python, zero-dependency AhoTTS grapheme-to-phoneme for Basque and Spanish.

## Contents

- [Installation](installation.md) -- requirements and install options.
- [Usage](usage.md) -- the public API, CLI, and common recipes.
- [Versions](versions.md) -- the AhoTTS V1/V2/V3 engine lineage and what each
  produces; what this release implements.
- [Architecture](architecture.md) -- the text -> phoneme pipeline and the HDIC
  dictionary decode.
- [Accuracy](accuracy.md) -- the StyleTTS2-eu oracle and per-version parity
  status.
- [Licensing](licensing.md) -- Apache-2.0, the clean-room reimplementation, and
  the AhoTTS / Aholab credit.

Port-engineering notes (clean-room source audit and per-language deltas):

- [NOTES.md](NOTES.md) -- Basque V1/V2/V3 port notes and residual breakdown.
- [NOTES_ES.md](NOTES_ES.md) -- Spanish port notes.
- [SOURCE_PORT_AUDIT.md](SOURCE_PORT_AUDIT.md) -- C++ source -> Python audit.

## Quick start

```python
from ahotts_g2p import phonemize
phonemize("Bai.")              # 'bAj .'
```

See the runnable scripts under [`../examples/`](../examples).
