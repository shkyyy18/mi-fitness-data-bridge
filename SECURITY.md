# Security policy

## Sensitive data

Mi Fitness passTokens, user identifiers, SQLite databases, exports, logs, and health records are sensitive. Never include them in issues, pull requests, screenshots, or test fixtures.

## Reporting

Report suspected credential exposure or a vulnerability privately to the repository maintainers before opening a public issue. Include a minimal synthetic reproduction and do not include real account data.

## Supported use

This project is designed for local, single-user access to data the user is authorized to access. A hosted credential proxy, shared-token service, or public internet deployment is outside the supported security model.

## Credential response

If a passToken may have leaked, sign out of the Xiaomi account sessions, refresh credentials, remove local exports/logs containing the token, and inspect Git history before publishing.
