# Security Policy

## Reporting a Vulnerability

**Do not report security vulnerabilities through public GitHub issues.**

Instead, please report them securely using one of the following methods:

1. **Email**: Send a description of the vulnerability to security@bitchchain.dev
2. **GitHub Security Advisory**: Use [GitHub's private vulnerability reporting](../../security/advisories/new)

Please include:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if available)
- Your contact information for follow-up

## Response Timeline

| Action | Target Time |
|--------|-------------|
| Acknowledge receipt | 24 hours |
| Initial assessment | 72 hours |
| Status update | 7 days |
| Fix developed | 14-30 days (depending on severity) |
| Fix released | Next release after fix is validated |

## Severity Classification

| Level | Description | Example |
|-------|-------------|---------|
| Critical | Remote code execution, fund theft, chain consensus attack | Private key leakage, consensus bypass |
| High | Data exposure, denial of service, privacy violation | CT amount leakage, mempool manipulation |
| Medium | Limited impact bugs | Non-crashing RPC errors, slow block validation |
| Low | Informational, hard to exploit | Log verbosity, minor misconfigurations |

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x | Yes (current development) |

## Known Security Considerations

### Experimental Software

Bitchchain is **experimental prototype software**. It has not undergone a formal security audit.

### Confidential Transactions

The CT implementation uses Pedersen commitments with bit-decomposition range proofs. While cryptographically valid, the Python implementation does not provide constant-time guarantees for elliptic curve operations. A production deployment should use libsecp256k1 bindings.

### P2P Network

The P2P protocol does not yet implement:
- TLS encryption for node connections
- Node authentication (V2 transport protocol)
- BIP 151/152 encrypted transport

### Wallet

Private keys are stored in SQLite. For production use:
- Encrypt the wallet database with a passphrase
- Use hardware security modules (HSMs) for validator keys
- Implement key derivation paths (BIP 32/44)

## Security Best Practices for Operators

1. Set pc_user and pc_password in your config — never run with empty credentials
2. Bind RPC to 127.0.0.1 unless you explicitly need remote access
3. Use firewall rules to restrict P2P port (8333) access
4. Never share your .env file or private keys
5. Run the node as a non-root user in Docker
6. Keep your system and Python dependencies updated
