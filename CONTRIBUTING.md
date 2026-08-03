# Contributing

Contributions are welcome for device compatibility, normalized schemas, exports, documentation, tests, and safer local credential handling.

Before submitting:

1. Use synthetic fixtures only.
2. Do not include passTokens, user IDs, databases, raw personal responses, or screenshots with personal health values.
3. Keep the connector generic; fat-loss or product-specific analytics belong in downstream applications.
4. Preserve unofficial/non-affiliation notices and upstream MIT attribution.
5. Run:

```bash
python -m pytest -q -p no:cacheprovider
python -m ruff check src tests
```

Compatibility reports should state device model, account region, date range, available data types, and a redacted error message.

## Licensing of contributions

This project is licensed under AGPL-3.0-only. By submitting a pull request, you agree that:

1. your contribution is licensed to the project under AGPL-3.0-only; and
2. you grant the maintainer (shkyyy18) the perpetual right to also license your contribution under other terms, including commercial licenses — this keeps the community edition free and AGPL while preserving the maintainer's ability to offer commercial licensing.

If you do not agree, please open an issue to discuss before submitting.
