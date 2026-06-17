# Installation

`ahotts-g2p` is pure Python with **no runtime dependencies**. It needs only a
Python interpreter (3.10+); the bundled dictionary is read with the stdlib.

## From PyPI

```bash
pip install ahotts-g2p
```

## From source

```bash
git clone https://github.com/TigreGotico/ahotts-g2p
cd ahotts-g2p
pip install -e .[test]
```

The `[test]` extra adds `pytest` for running the test suite.

## Verify

```bash
python -c "from ahotts_g2p import phonemize; print(phonemize('Bai.'))"
# bAj .

pytest tests/ -q
```

## Package data

The Basque dictionary `eu_dicc.dic` ships inside the `ahotts_g2p` package
(declared as `package-data` in `pyproject.toml`), so it is available after a
normal install -- no extra download step.
