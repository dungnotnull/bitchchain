# PROJECT-detail.md — Bitchchain Blockchain

## Executive Summary
Bitchchain is a production-grade, Python-implemented blockchain derived from Bitcoin's UTXO model and P2P architecture. It implements three measurable improvements over Bitcoin: (1) 10× throughput via 4 MB blocks with parallel UTXO validation, (2) 50% energy reduction via a hybrid PoW/PoS consensus where SHA-256d mining produces blocks while a PoS validator committee finalizes them, and (3) optional Confidential Transactions (CT) using Pedersen commitments so transaction amounts are hidden from observers while remaining cryptographically verifiable. An LLM-powered agent layer continuously synthesizes the latest academic and developer research to guide future protocol evolution.

---

## Problem Statement
Bitcoin (2009) solved the double-spend problem for a decentralized peer-to-peer payment system but codified constraints that are increasingly incompatible with production use:
- **Throughput**: 7 TPS blocks every 10 minutes cannot serve a global payment network.
- **Energy**: Nakamoto PoW wastes ~1,449 kWh per transaction (Cambridge CBEI, 2023).
- **Privacy**: All transaction amounts are publicly visible; address clustering trivially de-anonymizes participants.

Bitchchain addresses all three with approaches validated in peer-reviewed literature: larger blocks (Bitcoin Cash precedent), hybrid PoW/PoS (Ethereum 2.0 precedent), and Pedersen commitment CT (Mimblewimble, Confidential Assets paper by Poelstra et al.).

---

## Target Users & Use Cases
| User | Trigger | Agent Does |
|------|---------|-----------|
| Protocol researcher | Run node in research mode | Syncs chain, monitors metrics, surfaces new relevant papers via SECOND-KNOWLEDGE-BRAIN |
| Developer | Send CT transaction via CLI | Constructs Pedersen-committed output, broadcasts to peers, confirms in block |
| Validator | Register stake via CLI | Creates staking transaction, joins validator set, participates in finality votes |
| Miner | Start PoW miner | Builds candidate block, runs SHA-256d proof-of-work loop, submits to network |
| Auditor | Run benchmark suite | Measures actual TPS, energy model, privacy property completeness |

---

## Agent Architecture (ASCII)

```
CLI / REST API
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│  Orchestrator (agent/orchestrator.py)                   │
│  Routes: start-node | mine | send-tx | stake | research │
│  ┌──────────────────┐   ┌──────────────────────────┐    │
│  │  ResearchSynth   │   │  NodeMonitor             │    │
│  │  (LLM + papers)  │   │  (chain state, mempool)  │    │
│  └──────────────────┘   └──────────────────────────┘    │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Domain Modules                                    │  │
│  │  blockchain_core.py  | consensus_engine.py         │  │
│  │  privacy_layer.py    | network_node.py             │  │
│  └────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
      │               │               │
  LLM API         ArXiv API      Bitcoin P2P
(Claude/GPT)   (knowledge_upd)  (asyncio TCP)
      │
  Memory (SQLite + JSON)
```

---

## Full Module Catalog

### `agent/modules/blockchain_core.py`
- **Responsibility**: Core data structures and chain management
- **Inputs**: Raw transaction data, block templates
- **Outputs**: Validated Block objects, UTXO set updates, chain tip hash
- **Tools called**: hashlib (SHA-256d), ecdsa, leveldb-py
- **Quality gate**: Every block header passes PoW target check before acceptance; UTXO double-spend detection on every transaction

### `agent/modules/consensus_engine.py`
- **Responsibility**: Hybrid PoW/PoS consensus — mining loop + validator finality
- **Inputs**: Block candidates from mempool, validator stake registry, network peers
- **Outputs**: Mined blocks, finality votes, chain selection (longest finalized chain)
- **Tools called**: blockchain_core, network_node, hashlib
- **Quality gate**: Block not considered finalized until ≥ 2/3 of active stake weight votes; PoW difficulty retargets every 2016 blocks

### `agent/modules/privacy_layer.py`
- **Responsibility**: Confidential Transactions — Pedersen commitment construction and verification
- **Inputs**: Plaintext amounts (sender only), blinding factors
- **Outputs**: Committed output values, excess signature, range proof stub
- **Tools called**: sympy / ecdsa (elliptic curve operations)
- **Quality gate**: Sum-of-inputs commitment equals sum-of-outputs commitment plus fee commitment (balance proof)

### `agent/modules/network_node.py`
- **Responsibility**: Async P2P TCP networking — peer discovery, message protocol, block/tx propagation
- **Inputs**: DNS seed list, known peers from config
- **Outputs**: Block and transaction broadcasts to all connected peers
- **Tools called**: asyncio, json, socket
- **Quality gate**: All inbound messages validated before processing; duplicate detection via inv cache

---

## HuggingFace Model Selection
| Model | Task | Benchmark | Reason over alternatives |
|-------|------|-----------|--------------------------|
| `BAAI/bge-large-en-v1.5` | Paper semantic search | MTEB #1 overall (2024) | Best embedding quality for dense retrieval over research corpus |
| `facebook/bart-large-cnn` | Paper abstractive summarization | ROUGE-L 44.2 on CNN/DM | High-quality summaries for long ArXiv PDFs; runs on single GPU |

---

## LLM API Integration Spec
| Provider | Model | Use Case | Token Budget (est.) |
|----------|-------|----------|---------------------|
| Claude | claude-opus-4-8 | Multi-paper synthesis, protocol trade-off analysis | 8,000 tokens/query |
| OpenAI | gpt-4o | Structured JSON parameter recommendations | 4,000 tokens/query |
| Ollama | llama3 | Offline research digest | 4,000 tokens/query |

**Prompt templates:**
```
SYNTHESIS PROMPT:
You are a blockchain protocol researcher. Given the following research papers:
{paper_summaries}
Analyze the applicability to Bitchchain's three improvement targets:
1. TPS improvement (current goal: ≥70 TPS)
2. Energy reduction (current goal: ≤50% of Bitcoin PoW)
3. Privacy (CT completeness)
Return a JSON object with: {applicable_findings, recommended_parameter_changes, risk_analysis}
```

---

## E2E Execution Flow

### Flow: Start Full Node
1. `main.py start-node` → orchestrator receives command
2. Orchestrator loads chain from disk (SQLite), initializes UTXO set
3. `network_node.py` connects to DNS seeds, performs peer handshake
4. Sync loop: download headers → validate PoW → download blocks → validate transactions → update UTXO set
5. Node enters listening state: accepts new peers, blocks, transactions
6. Memory manager persists chain tip, peer list, mempool state

### Flow: Mine Block
1. `main.py mine` → orchestrator checks node is synced
2. `consensus_engine.py` builds block template from mempool (highest fee-rate txns)
3. PoW loop: increment nonce until `SHA-256d(header) < target`
4. On solution: broadcast to all peers via `network_node.py`
5. Wait for ≥2/3 validator finality votes before considering block confirmed
6. Memory manager records mined block hash and reward

### Flow: Send CT Transaction
1. `main.py send-ct --to ADDR --amount 1.5 BCC` → orchestrator
2. `privacy_layer.py` generates Pedersen commitment for amount 1.5, chooses blinding factor
3. Constructs transaction with committed output; signs with sender private key
4. Broadcasts via `network_node.py`; recipient derives actual amount with blinding factor

### Flow: Research Sync
1. Cron / manual `main.py research-sync` → `knowledge_updater.py`
2. Fetches top 50 papers from ArXiv cs.CR + cs.DC (last 7 days)
3. BGE embeddings computed; BM25 + cosine similarity scores against protocol keywords
4. Top 10 papers passed to `llm_client.py` (Claude) for synthesis
5. Output appended to `SECOND-KNOWLEDGE-BRAIN.md` with ISO date stamp

---

## SECOND-KNOWLEDGE-BRAIN.md Integration
- **Sources**: ArXiv cs.CR, cs.DC; Financial Cryptography; bitcoin-dev mailing list; ethresear.ch
- **Crawl config**: 50 papers/week, score by recency (90-day window) × keyword relevance
- **Keywords**: consensus, proof-of-stake, confidential transactions, zero-knowledge, blockchain throughput, UTXO model
- **Dedup**: SHA-256 hash of DOI/URL; skip if already present
- **Update frequency**: Weekly (Sunday 02:00 UTC)

---

## `knowledge_updater.py` Spec
- **Inputs**: ArXiv API endpoint, keyword list, last-run timestamp
- **Outputs**: Appended entries in SECOND-KNOWLEDGE-BRAIN.md
- **Schedule**: Weekly via APScheduler
- **Failure handling**: Log error, retry next day; fall back to cached paper list if API unavailable

---

## `llm_client.py` Spec
- **Provider chain**: Claude → OpenAI → Ollama
- **Retry logic**: 3 retries with exponential backoff (1s, 2s, 4s)
- **Streaming**: Supported for Claude and OpenAI via SSE
- **Fallback trigger**: HTTP 429 (rate limit) or connection timeout

---

## `hf_model_manager.py` Spec
- **Model registry**: BGE-large (embedding), BART-large-cnn (summarization)
- **Lazy loading**: Download on first use, cache in `./models/`
- **Cache path**: `D:\Dungchan\agent\3\models\`
- **GPU passthrough**: CUDA if available, CPU fallback

---

## Docker Compose Spec
- **Services**: `bitchchain-node` (main blockchain node), `bitchchain-agent` (research/monitoring agent)
- **Volumes**: `chain-data` (blockchain storage), `models` (HuggingFace cache)
- **Ports**: 8333 (P2P), 8332 (RPC API)
- **GPU**: nvidia runtime for HuggingFace inference if available

---

## Quality Gates
1. **Block validation**: Every block passes PoW target check + transaction signature verification before acceptance
2. **CT balance proof**: Sum of input commitments = sum of output commitments + fee commitment
3. **Finality threshold**: Block finalized only when ≥2/3 of active validator stake has voted
4. **TPS gate**: Simulated testnet must demonstrate ≥70 TPS before mainnet configuration
5. **Research gate**: SECOND-KNOWLEDGE-BRAIN updated weekly; agent must surface at least 1 actionable protocol insight per crawl

---

## Test Scenarios (see tests/test-scenarios.md)
1. Mine 10 blocks on regtest network, verify chain grows correctly
2. Send CT transaction, verify receiver can decode amount, verifier cannot
3. Register validator stake, verify finality votes are counted
4. Simulate 50 concurrent transactions, measure actual TPS
5. Run knowledge_updater, verify SECOND-KNOWLEDGE-BRAIN receives ≥5 new entries

---

## Key Design Decisions
1. **Python over C++**: Prioritize AI agent composability and research velocity; C++ port is Phase 8+
2. **Pedersen CT over zk-SNARKs**: Pedersen has well-understood security properties and requires no trusted setup; range proofs added in Phase 3+
3. **4 MB blocks over SegWit-style**: Simpler implementation for prototype; SegWit witness discount added later
4. **asyncio P2P**: Event-driven I/O matches Bitcoin's original select()-based design without OS thread overhead
5. **SQLite + JSON state**: Sufficient for prototype; replace with LevelDB in production fork
