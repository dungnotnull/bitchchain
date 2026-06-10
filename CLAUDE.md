# CLAUDE.md — Bitchchain Blockchain Agent

## Agent Identity
**Name:** Bitchchain Blockchain Agent
**Tagline:** A Bitcoin-inspired blockchain with hybrid PoW/PoS consensus, Confidential Transactions, and an LLM-powered research synthesis engine.
**Build Phase:** Phase 1 — Core Blockchain Implementation

---

## Problem Statement
Bitcoin's canonical design suffers from three well-documented constraints: low throughput (~7 TPS), excessive energy consumption (Proof-of-Work only), and transparent transaction amounts that compromise financial privacy. Bitchchain forks Bitcoin's UTXO model and P2P networking architecture, then applies three quantified improvements — (1) 10× TPS via 4 MB blocks and parallelized validation, (2) 50% energy reduction via hybrid PoW/PoS where PoS validators finalize blocks, and (3) optional Confidential Transactions using Pedersen commitments to conceal amounts without breaking balance proofs. An LLM agent layer continuously ingests the latest blockchain research to guide protocol evolution.

---

## Quantified Improvement Targets (Locked Before Code)
| # | Target | Baseline (Bitcoin) | Bitchchain Goal | Method |
|---|--------|--------------------|-----------------|--------|
| 1 | Throughput | ~7 TPS | ≥ 70 TPS | 4 MB blocks + parallel UTXO validation |
| 2 | Energy | ~1,449 kWh/tx | ≤ 724 kWh/tx | Hybrid PoW (mining) + PoS (finality) |
| 3 | Privacy | Fully transparent | Optional CT | Pedersen commitment + Bulletproof range proofs |

---

## Agent Architecture

```
CLI / REST Trigger
        ↓
┌──────────────────────────────────────────────────────┐
│  Orchestrator (agent/orchestrator.py)                │
│  ┌──────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │ ResearchSynth│→ │ NodeMonitor │→ │ PlanExecutor│ │
│  └──────────────┘  └─────────────┘  └─────────────┘ │
│         ↕                ↕                           │
│  ┌────────────────────────────────────────────────┐  │
│  │ Domain Modules                                 │  │
│  │ blockchain_core.py   consensus_engine.py       │  │
│  │ privacy_layer.py     network_node.py           │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
        ↓              ↓              ↓
   LLM API         ArXiv API     Bitcoin P2P
 (llm_client)   (knowledge_upd)  (asyncio TCP)
```

1. **Trigger**: CLI command (start-node / mine / send-tx / research-sync)
2. **Orchestrator**: routes commands to the appropriate domain module or research pipeline
3. **Node Monitor**: tracks chain state, mempool, connected peers, and consensus metrics
4. **Research Synthesizer**: uses LLM to digest new blockchain papers into actionable protocol notes
5. **Plan Executor**: applies approved protocol improvements as configuration changes

---

## Module List (`agent/modules/`)
| File | Responsibility |
|------|---------------|
| `blockchain_core.py` | Block header, Transaction, UTXO set, chain storage (LevelDB-inspired) |
| `consensus_engine.py` | Hybrid PoW/PoS: SHA-256d mining + validator staking and finality votes |
| `privacy_layer.py` | Pedersen commitment CT transactions and Bulletproof-style range proof stubs |
| `network_node.py` | Async P2P node: peer discovery (DNS seeds), block/tx gossip, inv/getdata protocol |

---

## Tools (`agent/tools/`)
| File | Responsibility |
|------|---------------|
| `hf_model_manager.py` | Not primary; loads BAAI/bge-large for semantic search over research papers |

---

## HuggingFace Models
| Model ID | Task | Why Chosen |
|----------|------|-----------|
| `BAAI/bge-large-en-v1.5` | Paper embedding & semantic search | Top-ranked on MTEB; enables "find papers similar to this protocol decision" queries |
| `facebook/bart-large-cnn` | Research paper summarization | High-quality abstractive summarization for long ArXiv papers |

---

## LLM API Integration
- **Primary**: Claude `claude-opus-4-8` — multi-paper synthesis, protocol trade-off analysis, code review of consensus changes
- **Fallback**: OpenAI `gpt-4o` — structured JSON output for parameter tuning recommendations
- **Offline**: Ollama `llama3` — local research synthesis when no API key available
- **Use cases**: synthesize blockchain papers → implementation plan; explain cryptographic trade-offs; review consensus parameter changes

---

## Knowledge Crawl Sources
| Source | Categories / Queries | Frequency |
|--------|----------------------|-----------|
| ArXiv | cs.CR (cryptography), cs.DC (distributed computing) | Weekly |
| Financial Cryptography Conference | proceedings.mlr.press/fc* | Monthly |
| Bitcoin developer mailing list | lists.linuxfoundation.org/bitcoin-dev | Weekly |
| Ethereum research forum | ethresear.ch | Weekly |
| Papers with Code | blockchain, consensus, zero-knowledge proofs | Weekly |

---

## Supporting Tools (`tools/`)
- `knowledge_updater.py` — crawls ArXiv cs.CR + cs.DC + Financial Cryptography, scores by recency × relevance, appends top-10 weekly findings to `SECOND-KNOWLEDGE-BRAIN.md`
- `llm_client.py` — unified Claude/GPT/Ollama client with streaming, retry, and provider fallback
- `hf_model_manager.py` — lazy-loads BGE and BART models for paper embedding and summarization

---

## Active Development Tasks
- [x] Define 3 quantified improvement targets
- [x] Design block/transaction data structures
- [x] Implement hybrid PoW/PoS consensus engine
- [x] Implement Pedersen commitment CT layer
- [x] Implement async P2P network node
- [x] Wire orchestrator and agent modules
- [x] Configure knowledge_updater.py for blockchain research
- [x] Containerize with docker-compose
- [ ] Run baseline benchmark vs reference Bitcoin node
- [ ] Achieve ≥ 70 TPS on simulated testnet
- [ ] Verify energy model reduction of ≥ 50%
