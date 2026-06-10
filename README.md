# Bitchchain

A Bitcoin-forked blockchain with hybrid PoW/PoS consensus, Confidential Transactions, and an LLM-powered research synthesis engine.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)

## Overview

Bitchchain forks Bitcoin’s UTXO model and P2P networking architecture, then applies three major improvements:

| # | Target      | Baseline (Bitcoin)     | Bitchchain Goal      | Method                              |
|---|-------------|------------------------|----------------------|-------------------------------------|
| 1 | Throughput  | ~7 TPS                 | ≥ 70 TPS             | 4 MB blocks + parallelized validation |
| 2 | Energy      | ~1,449 kWh/tx          | ≤ 724 kWh/tx         | Hybrid PoW (mining) + PoS (finality) |
| 3 | Privacy     | Fully transparent      | Optional CT          | Pedersen commitments + Bulletproofs |

An LLM agent layer continuously ingests the latest blockchain research to guide protocol evolution.

## Architecture

```ascii
          CLI / REST API
                │
                ▼
┌──────────────────────────────────────────────────┐
│              Orchestrator                        │
│  ┌────────────────┐   ┌────────────────┐         │
│  │ ResearchSynth  │   │ NodeMonitor    │         │
│  └────────────────┘   └────────────────┘         │
│  ┌─────────────────────────────────────────────┐ │
│  │               Domain Modules                │ │
│  │  blockchain_core   consensus_engine         │ │
│  │  privacy_layer     network_node             │ │
│  └─────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
                │
     LLM API ───┼─── ArXiv API ─── Bitcoin P2P
```

## Quick Start

### Prerequisites
- Python 3.11+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/bitchchain/bitchchain.git
cd bitchchain

# Create virtual environment
python -m venv venv
source venv/bin/activate          # Linux / macOS
# venv\Scripts\activate           # Windows

# Install dependencies
pip install -e ".[dev]"
```

### Running a Node

```bash
# Start a regtest (local development) node
python -m agent.main start-node --regtest

# Mine blocks
python -m agent.main mine --regtest --count 10

# Check status
python -m agent.main status

# Send a normal transaction
python -m agent.main send-tx --to <ADDRESS> --amount 100000000 --from-txid <TXID> --from-vout 0

# Send a Confidential Transaction
python -m agent.main send-ct --to <SCRIPT_HEX> --amount 100000000 --fee 1000 \
    --from-txid <TXID> --from-vout 0

# Register as a validator
python -m agent.main stake --address <ADDRESS> --amount 3200000000 --stake-txid <TXID>

# Run research sync
python -m agent.main research-sync

# Ask the LLM a protocol question
python -m agent.main ask "Should we increase block size to 8MB?"
```

### Docker

```bash
# Start full node + research agent
docker compose -f docker/docker-compose.yml up -d

# Start 2-node testnet
docker compose -f docker/docker-compose.yml --profile testnet up -d

# Start with local Ollama (offline LLM)
docker compose -f docker/docker-compose.yml --profile offline up -d
```

### Configuration

```bash
cp config/.env.example config/.env
```

Edit `config/.env` with your API keys and settings.  
See `config/agent_config.yaml` for all configuration options.

## Modules

| Module                  | File                                | Responsibility |
|-------------------------|-------------------------------------|----------------|
| Blockchain Core         | `agent/modules/blockchain_core.py` | Block, Transaction, UTXO set, chain storage |
| Consensus Engine        | `agent/modules/consensus_engine.py`| Hybrid PoW/PoS + finality |
| Privacy Layer           | `agent/modules/privacy_layer.py`   | Confidential Transactions |
| Network Node            | `agent/modules/network_node.py`    | Async P2P networking |
| Orchestrator            | `agent/orchestrator.py`            | Command routing & research pipeline |
| Wallet                  | `agent/modules/wallet.py`          | Key management & signing |
| LLM Client              | `tools/llm_client.py`              | Claude / GPT / Ollama support |
| Knowledge Updater       | `tools/knowledge_updater.py`       | ArXiv + Semantic Scholar crawler |

## Confidential Transactions

Bitchchain implements Confidential Transactions using Pedersen commitments:

```python
from agent.modules.privacy_layer import ConfidentialTransactionEngine

engine = ConfidentialTransactionEngine()

# Build CT output
output, blinding = engine.build_ct_output(1_000_000, "76a914...88ac")

# Build full CT transaction
ct_tx, output_blindings = engine.build_ct_transaction(
    sender_address="sender",
    input_refs=[("txid", 0, input_blinding)],
    outputs_spec=[(999_000, "76a914...88ac")],
    fee_satoshis=1_000,
)
```

## Hybrid PoW/PoS Consensus

- **PoW (SHA-256d)**: Block production with difficulty retarget every 2016 blocks
- **PoS Finality**: Validators stake ≥ 32 BCC, checkpoints every 100 blocks
- **Finality**: Requires ≥ 2/3 of active stake weight
- **Slashing**: For equivocation (double-signing)

## LLM-Powered Research Agent

Automatically crawls ArXiv, Semantic Scholar, and Papers with Code, then synthesizes actionable protocol recommendations.

```bash
python -m agent.main research-sync
```

## Documentation

- `CLAUDE.md` — Agent identity & architecture
- `PROJECT-detail.md` — Full technical specification
- `PROJECT-DEVELOPMENT-PHASE-TRACKING.md` — Development roadmap
- `SECOND-KNOWLEDGE-BRAIN.md` — Self-improving research corpus

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Security

See [SECURITY.md](SECURITY.md). **Do not report security issues publicly.**

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

## Disclaimer

Bitchchain is experimental software. The Confidential Transactions implementation is a Python prototype. **Do not use this software for real financial transactions without a formal security audit.**
