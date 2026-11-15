# Contributing to solana-tx-lens

Contributions are welcome!

## Development
```bash
git clone https://github.com/devsoniclk/solana-tx-lens.git
cd solana-tx-lens
pip install -e ".[dev]"
pytest tests/ -v
```

## Adding Program Error Tables
To add new Anchor IDLs or custom DEX error code mappings:
1. Update `COMMON_DEX_ERRORS` in `solana_tx_lens/error_decoder.py`.
2. Add corresponding test cases in `tests/test_error_decoder.py`.
