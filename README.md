# Bitchchain

A Bitcoin-forked blockchain with hybrid PoW/PoS consensus, Confidential Transactions, and an LLM-powered research synthesis engine.

[![CI](https://github.com/bitchchain/bitchchain/actions/workflows/ci.yml/badge.svg)](https://github.com/bitchchain/bitchchain/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)

## Overview

Bitchchain forks Bitcoin's UTXO model and P2P networking architecture, then applies three quantified improvements:

| # | Target | Baseline (Bitcoin) | Bitchchain Goal | Method |
|---|--------|--------------------|-----------------|--------|
| 1 | Throughput | ~7 TPS | ≥ 70 TPS | 4 MB blocks + parallelized validation |
| 2 | Energy | ~1,449 kWh/tx | ≤ 724 kWh/tx | Hybrid PoW (mining) + PoS (finality) |
| 3 | Privacy | Fully transparent | Optional CT | Pedersen commitment + Bulletproof range proofs |

An LLM agent layer continuously ingests the latest blockchain research to guide protocol evolution.

## Architecture

`
CLI / REST API
      │
      ▼
┌──────────────────────────────────────────────────┐
│  Orchestrator (agent/orchestrator.py)            │
│  ┌──────────────┐  ┌──────────────┐              │
│  │ ResearchSynth │  │ NodeMonitor  │              │
│  └──────────────┘  └──────────────┘              │
│  ┌─────────────────────────────────────────────┐ │
│  │ Domain Modules                              │ │
│  │ blockchain_core  consensus_engine            │ │
│  │ privacy_layer    network_node               │ │
│  └─────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
      │              │              │
  LLM API       ArXiv API      Bitcoin P2P
`

## Quick Start

### Prerequisites

- Python 3.11+
- pip

### Installation

`ash
# Clone the repository
git clone https://github.com/bitchchain/bitchchain.git
cd bitchchain

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -e ".[dev]"
`

### Running a Node

`ash
# Start a regtest (local development) node
python -m agent.main start-node --regtest

# Mine blocks
python -m agent.main mine --regtest --count 10

# Check status
python -m agent.main status

# Send a transaction
python -m agent.main send-tx --to <ADDRESS> --amount 100000000 --from-txid <TXID> --from-vout 0

# Send a Confidential Transaction
python -m agent.main send-ct --to <SCRIPT_HEX> --amount 100000000 --fee 1000 \
    --from-txid <TXID> --from-vout 0

# Register as a validator
python -m agent.main stake --address <ADDRESS> --amount 3200000000 --stake-txid <TXID>

# Run research sync (requires ANTHROPIC_API_KEY or Ollama)
python -m agent.main research-sync

# Ask the LLM a protocol question
python -m agent.main ask "Should we increase block size to 8MB?"
`

### Docker

`ash
# Start a full node + research agent
docker compose -f docker/docker-compose.yml up -d

# Start with 2-node testnet
docker compose -f docker/docker-compose.yml --profile testnet up -d

# Start with local Ollama for offline LLM
docker compose -f docker/docker-compose.yml --profile offline up -d
`

### Configuration

Copy the example environment file and fill in your values:

`ash
cp config/.env.example config/.env
# Edit config/.env with your API keys and node settings
`

See config/agent_config.yaml for all configuration options.

## Modules

| Module | File | Responsibility |
|--------|------|----------------|
| Blockchain Core | gent/modules/blockchain_core.py | Block, Transaction, UTXO set, chain storage, HTLC scripts |
| Consensus Engine | gent/modules/consensus_engine.py | Hybrid PoW/PoS mining + PoS finality |
| Privacy Layer | gent/modules/privacy_layer.py | Pedersen commitment CT + range proofs |
| Network Node | gent/modules/network_node.py | Async P2P TCP node with Bitcoin protocol |
| Orchestrator | gent/orchestrator.py | Command routing, state management, research pipeline |
| Memory Manager | gent/memory/memory_manager.py | SQLite-backed KV store, mempool, event log |
| Wallet | gent/modules/wallet.py | Key generation, address derivation, transaction signing |
| LLM Client | 	ools/llm_client.py | Unified Claude/GPT/Ollama client with fallback |
| Knowledge Updater | 	ools/knowledge_updater.py | ArXiv + Semantic Scholar + Papers with Code crawler |
| HF Model Manager | 	ools/hf_model_manager.py | BGE embedding + BART summarization |
| Benchmark | gent/benchmark.py | TPS, energy model, and CT privacy benchmarks |
| RPC Server | gent/rpc_server.py | JSON-RPC 2.0 API (12 methods) |

## Testing

`ash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=agent --cov=tools --cov-report=html

# Run a specific test class
pytest tests/test_agent.py::TestPrivacyLayer -v

# Run benchmarks
python -m agent.main benchmark --all --publish
`

## Confidential Transactions

Bitchchain implements Confidential Transactions using Pedersen commitments:

- **Commitment**: C = r*G + v*H where  is a random blinding factor and  is the value
- **Balance proof**: Sum of input commitments = Sum of output commitments + fee commitment
- **Range proofs**: Each committed value is proven to be in [0, 2^64) using bit-decomposition
- **Recipient decode**: Amount can be recovered by the recipient using the shared blinding factor

`python
from agent.modules.privacy_layer import ConfidentialTransactionEngine

engine = ConfidentialTransactionEngine()

# Create a CT output
output, blinding = engine.build_ct_output(1_000_000, "76a914...88ac")

# Build a full CT transaction
ct_tx, output_blindings = engine.build_ct_transaction(
    sender_address="sender",
    input_refs=[("txid", 0, input_blinding)],
    outputs_spec=[(999_000, "76a914...88ac")],
    fee_satoshis=1_000,
)

# Verify balance proof
valid, msg = engine.verify_balance(ct_tx, [input_commitment_hex])
assert valid
`

## Hybrid PoW/PoS Consensus

- **PoW (SHA-256d)**: Miners produce blocks; difficulty retargets every 2016 blocks
- **PoS Finality**: Validators stake ≥ 32 BCC; checkpoints every 100 blocks
- **Finality threshold**: ≥ 2/3 of active stake weight must vote to finalize
- **Slashing**: Validators caught equivocating (double-voting) are slashed
- **Energy reduction**: 1 PoW confirmation + PoS finality replaces Bitcoin's 6 confirmations

## LLM-Powered Research Agent

The research pipeline automatically:

1. Crawls ArXiv (cs.CR, cs.DC), Semantic Scholar, and Papers with Code weekly
2. Scores papers by recency × keyword relevance
3. Synthesizes findings into actionable protocol recommendations via Claude/GPT
4. Appends results to SECOND-KNOWLEDGE-BRAIN.md

`ash
# Trigger manually
python -m agent.main research-sync

# Or let it run weekly via APScheduler in the research Docker service
`

## Documentation

- CLAUDE.md — Agent identity, architecture, and module catalog
- PROJECT-detail.md — Full technical specification
- PROJECT-DEVELOPMENT-PHASE-TRACKING.md — 18-week build roadmap with progress
- SECOND-KNOWLEDGE-BRAIN.md — Self-improving research corpus

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines. We welcome issues, feature requests, and pull requests.

## Security

See [SECURITY.md](SECURITY.md) for reporting vulnerabilities. **Do not file security issues in public GitHub issues.**

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Disclaimer

Bitchchain is experimental software. The Confidential Transactions implementation uses Pedersen commitments with bit-decomposition range proofs. While cryptographically valid, this is a Python prototype — a production deployment should use libsecp256k1 bindings for constant-time elliptic curve operations. **Do not use this software for real financial transactions without a formal security audit.**
