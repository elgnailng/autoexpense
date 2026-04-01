# Security

## Local-First Design

This project processes sensitive financial data (bank statements, transaction history). It is designed for **local-first use** -- all data is stored in a local DuckDB file and never leaves your machine unless you explicitly expose the server via ngrok or similar tunneling.

## Reporting Vulnerabilities

If you discover a security vulnerability, please report it by opening a [GitHub Issue](https://github.com/elgnailng/expense-elt/issues) with the label "security".

For sensitive disclosures, please email the maintainer directly rather than opening a public issue.

## Security Features

- Google OAuth 2.0 authentication with session JWTs (HttpOnly, SameSite cookies)
- Role-based access control (owner + accountant roles)
- Personal expense privacy filtering for accountant users
- Rate limiting (60 req/min global, 10 req/min on auth)
- Security headers (CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy)
- Path traversal protection on static file serving
- Pipeline lock to prevent concurrent write conflicts
- Error sanitization (no internal paths in API responses)

## Environment Variables

Never commit `.env` files. Use `.env.example` as a template. Required secrets:

- `GOOGLE_CLIENT_ID` -- Google OAuth Client ID
- `ALLOWED_EMAIL` -- Owner email address
- `SESSION_SECRET` -- HMAC key for JWTs (auto-generated if not set, but set one for persistent sessions)
