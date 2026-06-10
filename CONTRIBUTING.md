# Contributing to Bitchchain

Thank you for your interest in contributing to Bitchchain! This document provides guidelines and instructions for contributing.

## Code of Conduct

This project and everyone participating in it is governed by the [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [GitHub Issues](../../issues).
2. If not, open a new issue with:
   - **Bug title**: Clear, concise description
   - **Steps to reproduce**: Numbered list
   - **Expected behavior**: What should happen
   - **Actual behavior**: What actually happens
   - **Environment**: OS, Python version, Bitchchain version
   - **Logs**: Relevant log output (redact any sensitive data)

### Suggesting Features

1. Open a [GitHub Discussion](../../discussions) first to gauge interest.
2. If well-received, open a feature request issue with:
   - **Problem**: What problem does this solve?
   - **Proposed solution**: How should it work?
   - **Alternatives considered**: Other approaches you thought about
   - **Impact**: Which of the 3 improvement targets (TPS, energy, privacy) does this affect?

### Pull Requests

1. **Fork** the repository and create your branch from main.
2. **Write tests** for any new functionality. We require test coverage for all PRs.
3. **Follow the code style** — run uff check . and mypy agent tools before submitting.
4. **Document your changes** — update docstrings, README, and relevant .md files.
5. **Keep PRs focused** — one logical change per PR. Don't mix refactoring with new features.
6. **Write clear commit messages** — use conventional commits format:
   - eat: add wallet key management
   - ix: correct Pedersen commitment balance proof
   - docs: update README quickstart
   - 	est: add CT integration tests
   - efactor: extract UTXO validation into separate method

### Development Setup

`ash
git clone https://github.com/bitchchain/bitchchain.git
cd bitchchain
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
pre-commit install
`

### Running Tests

`ash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=agent --cov=tools

# Type checking
mypy agent tools

# Linting
ruff check .
`

### Commit Signing

We require all commits to be signed (GPG or SSH). See [GitHub's guide](https://docs.github.com/en/authentication/managing-commit-signature-verification).

## Architecture Overview

- gent/modules/ — Core blockchain modules (blockchain_core, consensus_engine, privacy_layer, network_node, wallet)
- gent/ — Orchestrator, CLI entry point, RPC server, memory manager
- 	ools/ — LLM client, knowledge updater, HuggingFace model manager
- 	ests/ — Unit and integration tests
- config/ — Configuration files
- docker/ — Docker and Docker Compose files

## Crypto Implementation Guidelines

When working with cryptographic code:

1. **Never implement your own crypto primitives** — use well-established libraries (ecdsa, hashlib, cryptography)
2. **Use constant-time comparison** for signature verification (hmac.compare_digest)
3. **Never log or print private keys, blinding factors, or nonces**
4. **Test with known test vectors** from Bitcoin and secp256k1 specifications
5. **Mark experimental crypto** with clear docstring warnings

## Questions?

Open a [GitHub Discussion](../../discussions) or join our community chat.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
