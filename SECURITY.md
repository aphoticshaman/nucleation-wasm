# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it via email:

**Email:** aphotic.noise@gmail.com

**Please include:**
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

**Response Timeline:**
- Acknowledgment: Within 48 hours
- Initial assessment: Within 7 days
- Fix timeline: Based on severity

## Security Measures

This project implements:

- **Dependency Auditing**: `cargo audit` on every CI run
- **License Compliance**: `cargo deny` for license checking
- **Static Analysis**: Semgrep SAST scanning
- **Dependency Updates**: Dependabot enabled
- **Code Review**: All PRs require review

## Secure Development

When contributing:

1. Never commit secrets, API keys, or credentials
2. Use environment variables for configuration
3. Validate all external input
4. Keep dependencies up to date
5. Follow Rust safety guidelines (minimize `unsafe`)
