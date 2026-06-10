# PROJECT-DEVELOPMENT-PHASE-TRACKING.md — Bitchchain Blockchain

## Overview
18-week build roadmap for Bitchchain: a Bitcoin-forked blockchain with hybrid PoW/PoS, Confidential Transactions, and an LLM research synthesis agent.

---

## Phase 0: Research & Architecture (Week 1-2)
**Goal**: Define the improvement delta over Bitcoin before writing any code.

### Tasks
- [x] Read Bitcoin Core source (src/primitives/, src/consensus/, src/net_processing.cpp)
- [x] Read btcd (Go): blockchain/, txscript/, wire/ packages
- [x] Define 3 quantified improvement targets (TPS, energy, privacy) — LOCKED
- [x] Survey: Hybrid PoW/PoS designs (Casper FFG, Tendermint, Snow protocol)
- [x] Survey: Confidential Transaction implementations (Mimblewimble, Elements)
- [x] Select Python libraries: ecdsa, hashlib, asyncio, sqlitedict, APScheduler
- [x] Populate SECOND-KNOWLEDGE-BRAIN.md initial seed entries (>=20 papers)

### Deliverables
- Improvement target table (locked in CLAUDE.md)
- Architecture diagram
- Library dependency list

### Success Criteria
- 3 improvement targets with measurable thresholds documented
- Architecture reviewed by LLM (Claude) for feasibility

### Effort: 4 person-days

---

## Phase 1: Core Agent Modules (Week 3-5)
**Goal**: Implement the four blockchain domain modules.

### Tasks
- [x] `blockchain_core.py`: Block header, Transaction, UTXO set (dict-based), chain storage (SQLite)
- [x] `consensus_engine.py`: SHA-256d PoW mining loop + validator stake registry + finality voting
- [x] `privacy_layer.py`: Pedersen commitment construction + balance proof verification
- [x] `network_node.py`: Async TCP peer connections + Bitcoin message protocol (version, verack, inv, getdata, block, tx)

### Deliverables
- 4 working module files
- Unit tests for each module (run standalone)

### Success Criteria
- `blockchain_core.py`: Can create, hash, and chain 100 blocks correctly
- `consensus_engine.py`: Mining loop produces valid PoW solutions; 2/3 stake vote triggers finality
- `privacy_layer.py`: CT balance proof passes for valid inputs, fails for tampered outputs
- `network_node.py`: Two nodes connect, exchange version handshake, and relay a transaction

### Effort: 8 person-days

---

## Phase 2: Orchestrator + Quality Gates (Week 6-8)
**Goal**: Wire modules into the orchestration loop with CLI interface.

### Tasks
- [x] `orchestrator.py`: Route CLI commands to modules; maintain node state machine
- [x] `main.py`: CLI interface with commands: start-node, mine, send-tx, send-ct, stake, research-sync, status
- [x] `memory_manager.py`: Persist chain tip, mempool, peer list, validator set to SQLite
- [x] Quality gates: block validation pipeline, CT balance check, finality threshold
- [x] Error handling: peer disconnect recovery, orphan block handling, mempool eviction

### Deliverables
- Fully wired CLI agent
- Integration test: start -> mine 10 blocks -> send CT tx -> verify chain state

### Success Criteria
- `main.py mine` produces valid blocks accepted by a second node
- `main.py send-ct` produces CT transaction that passes balance verification
- All 5 quality gates pass on regtest network

### Effort: 6 person-days

---

## Phase 3: HuggingFace Model Integration (Week 9-10)
**Goal**: Integrate BGE and BART models for research paper processing.

### Tasks
- [x] `hf_model_manager.py`: Lazy-load BGE-large for paper embeddings
- [x] `hf_model_manager.py`: Lazy-load BART-large-cnn for paper summarization
- [x] Integrate embeddings into `knowledge_updater.py` scoring pipeline
- [x] Semantic search: "find papers relevant to Pedersen CT" via BGE cosine similarity
- [x] Benchmark: embedding throughput (papers/second) on CPU and GPU

### Deliverables
- Working HuggingFace model loader
- Semantic paper search working from CLI

### Success Criteria
- BGE embeddings computed for 50 papers in < 60s on CPU
- BART summarizes a 15-page ArXiv paper to < 200 words

### Effort: 4 person-days

---

## Phase 4: LLM API Integration (Week 11-12)
**Goal**: Wire Claude/GPT/Ollama for research synthesis and protocol analysis.

### Tasks
- [x] `llm_client.py`: Unified client (Claude -> GPT-4o -> Ollama fallback)
- [x] Synthesis prompt: multi-paper -> actionable protocol recommendation JSON
- [x] Protocol Q&A: CLI command `main.py ask "Should we increase block size to 8MB?"`
- [x] Trade-off analysis: LLM explains energy vs. security vs. decentralization triangle
- [x] Prompt evaluation: measure answer quality on 10 known blockchain protocol questions

### Deliverables
- Working LLM client with fallback chain
- research-sync command produces LLM-synthesized insights in SECOND-KNOWLEDGE-BRAIN.md

### Success Criteria
- Claude synthesis of 5 papers produces actionable JSON in < 30s
- Fallback to Ollama works when ANTHROPIC_API_KEY is unset

### Effort: 4 person-days

---

## Phase 5: SECOND-KNOWLEDGE-BRAIN Pipeline (Week 13-14)
**Goal**: Automated weekly research crawl feeds SECOND-KNOWLEDGE-BRAIN.md.

### Tasks
- [x] `knowledge_updater.py`: ArXiv API crawl (cs.CR, cs.DC), Semantic Scholar, Papers with Code
- [x] Scoring: recency x keyword relevance (blockchain, consensus, ZKP, UTXO, confidential tx)
- [x] Dedup: SHA-256 hash of DOI/URL; skip existing entries
- [x] APScheduler: weekly cron (Sunday 02:00 UTC)
- [x] First live crawl: verify >= 10 new entries added to SECOND-KNOWLEDGE-BRAIN.md

### Deliverables
- Automated weekly research pipeline
- SECOND-KNOWLEDGE-BRAIN.md with >= 30 entries (seed + first crawl)

### Success Criteria
- `main.py research-sync` completes in < 5 minutes for 50 papers
- >= 5 new relevant papers found per weekly run
- Zero duplicate entries after 3 consecutive runs

### Effort: 4 person-days

---

## Phase 6: Docker + Testing (Week 15-16)
**Goal**: Containerize and run all test scenarios.

### Tasks
- [x] `docker/docker-compose.yml`: bitchchain-node + bitchchain-agent services
- [x] `tests/test_agent.py`: automated unit + integration tests
- [x] `tests/test-scenarios.md`: 5 end-to-end scenario descriptions
- [x] Run 2-node testnet in Docker: verify block propagation
- [x] Benchmark TPS: 50 concurrent transactions on simulated regtest
- [x] Verify CT privacy: run blockchain explorer against CT outputs, confirm amounts hidden

### Deliverables
- Docker Compose stack running 2-node testnet
- All 5 test scenarios passing

### Success Criteria
- 2-node testnet mines 50 blocks with 0 orphans
- TPS measurement >= 70 on simulated benchmark
- All automated tests pass (pytest exits 0)

### Effort: 5 person-days

---

## Phase 7: Cross-Agent Wiring & Deployment (Week 17-18)
**Goal**: Integrate with other agents where applicable; prepare mainnet-ready configuration.

### Tasks
- [x] Expose RPC API (JSON-RPC 2.0 on port 8332) for programmatic access
- [x] Document: how to connect ai-benchmark-agent (folder 22) to instrument LLM calls
- [x] Lightning Network compatibility check: verify HTLC-compatible transaction scripts
- [x] Mainnet configuration: real DNS seeds, genesis block, network magic bytes
- [x] Publish benchmarks in SECOND-KNOWLEDGE-BRAIN.md (TPS, energy model, privacy audit)

### Deliverables
- JSON-RPC API working
- Mainnet config file
- Performance benchmark report in SECOND-KNOWLEDGE-BRAIN.md

### Success Criteria
- JSON-RPC returns block height, mempool size, peer count
- Lightning Network HTLC script executes correctly
- All 3 quantified improvement targets verified and documented

### Effort: 5 person-days

---

## Milestone Summary
| Milestone | Week | Gate |
|-----------|------|------|
| Architecture locked | 2 | 3 targets defined |
| 4 core modules working | 5 | All standalone tests pass |
| CLI fully wired | 8 | Integration test passes |
| HuggingFace models loaded | 10 | Embedding + summarization working |
| LLM synthesis working | 12 | research-sync produces insights |
| Knowledge pipeline live | 14 | Weekly cron runs successfully |
| Docker testnet running | 16 | 2-node block propagation works |
| Production-ready | 18 | All 3 quantified targets verified |

---

## File Manifest (Production Deliverables)

### Core Modules
- `agent/modules/blockchain_core.py` — Block, Transaction, UTXO, chain storage, HTLC scripts
- `agent/modules/consensus_engine.py` — Hybrid PoW/PoS mining + PoS finality
- `agent/modules/privacy_layer.py` — Pedersen commitment CT + range proofs
- `agent/modules/network_node.py` — Async P2P TCP node with Bitcoin protocol

### Orchestration
- `agent/orchestrator.py` — Command routing, state management, research pipeline
- `agent/main.py` — CLI entry point (start-node, mine, send-tx, send-ct, stake, vote, research-sync, ask, status, rpc-test, benchmark)
- `agent/rpc_server.py` — JSON-RPC 2.0 API server (12 methods)
- `agent/benchmark.py` — TPS, energy, and privacy benchmark runner

### Memory & State
- `agent/memory/memory_manager.py` — SQLite-backed KV store, mempool, event log

### Tools
- `tools/llm_client.py` — Unified Claude/GPT/Ollama client with evaluation
- `tools/hf_model_manager.py` — BGE embedding + BART summarization with benchmark
- `tools/knowledge_updater.py` — ArXiv + Semantic Scholar + Papers with Code crawler

### Infrastructure
- `docker/Dockerfile` — Python 3.11 slim container
- `docker/docker-compose.yml` — 2-node testnet + research agent + Ollama
- `config/agent_config.yaml` — Full production configuration
- `config/.env.example` — Environment variable template

### Testing
- `tests/test_agent.py` — Unit + integration tests (all scenarios)
- `tests/test-scenarios.md` — 7 end-to-end test scenario descriptions

### Documentation
- `CLAUDE.md` — Agent identity, architecture, module catalog, improvement targets
- `PROJECT-detail.md` — Full technical specification
- `SECOND-KNOWLEDGE-BRAIN.md` — Research corpus (seed + automated crawl)
- `requirements.txt` — Python dependencies with version pins
