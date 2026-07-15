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
