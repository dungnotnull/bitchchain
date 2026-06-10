# SECOND-KNOWLEDGE-BRAIN.md — Bitchchain Blockchain

*Self-improving knowledge base. Updated weekly by `tools/knowledge_updater.py`. The longer this agent runs, the more accurate its protocol decisions become.*

---

## Core Concepts & Frameworks

### Bitcoin UTXO Model
- Transactions consume Unspent Transaction Outputs (UTXOs) and create new UTXOs
- Each UTXO is locked by a script (P2PKH, P2SH, P2WPKH); spending requires a valid unlocking script
- UTXO set is the canonical state — no account balances; entire chain history not needed for validation
- Double-spend prevention: each UTXO can only be referenced once in the chain

### Nakamoto Consensus (PoW)
- Miners compete to find a nonce s.t. SHA-256d(header) < target
- Difficulty adjusts every 2016 blocks (~2 weeks) to maintain 10-minute average block time
- Longest chain (most accumulated work) wins — probabilistic finality
- Energy model: linear relationship between hash rate and energy consumption

### Hybrid PoW/PoS (Casper FFG Style)
- PoW proposes blocks; PoS validator committee votes on finality checkpoints
- Validators stake tokens as collateral; slashing condition for equivocation
- Finality: once ≥2/3 of stake weight votes for a checkpoint, it is irreversible
- Energy reduction: PoW block rate can be reduced (longer interval) without sacrificing finality speed

### Confidential Transactions (Pedersen Commitments)
- Pedersen commitment: C = r·G + v·H where r = blinding factor, v = value, G and H are curve generators
- Homomorphic property: C(v1) + C(v2) = C(v1+v2) → sum of input commitments = sum of output commitments
- Verifier checks balance without knowing individual amounts
- Range proofs (Bulletproofs) ensure committed values are non-negative without revealing them
- Reference: "Confidential Transactions" by Greg Maxwell (2015); "Bulletproofs" by Bünz et al. (2018)

### Elliptic Curve Cryptography (secp256k1)
- Bitcoin's curve: y² = x³ + 7 over prime field p = 2²⁵⁶ - 2³² - 977
- Key generation: private key k (256-bit random); public key K = k·G
- ECDSA signing: (r, s) where r = (k·G).x mod n, s = k⁻¹(z + r·privkey) mod n
- Schnorr signatures (BIP-340): simpler security proof, key aggregation (MuSig), batch verification

---

## Key Research Papers

| Title | Authors | Year | Venue | Link | Key Finding | Relevance |
|-------|---------|------|-------|------|-------------|-----------|
| Bitcoin: A Peer-to-Peer Electronic Cash System | Nakamoto | 2008 | White paper | bitcoin.org/bitcoin.pdf | UTXO model + PoW consensus; 10 min blocks, 7 TPS | Foundation |
| Casper the Friendly Finality Gadget | Buterin, Griffith | 2017 | ArXiv | arxiv.org/abs/1710.09437 | PoS finality overlay on PoW; slashing conditions; 2/3 supermajority | Consensus engine |
| Confidential Transactions | Maxwell | 2015 | bitcointalk | https://bitcointalk.org/index.php?topic=1085273 | Pedersen commitments hide amounts; balance proof via homomorphism | Privacy layer |
| Bulletproofs: Short Proofs for Confidential Transactions | Bünz, Bootle, Boneh et al. | 2018 | IEEE S&P | arxiv.org/abs/1705.01608 | Logarithmic-size range proofs; no trusted setup; 2× verify cost vs. CT | Privacy range proofs |
| MimbleWimble | Jedusor | 2016 | White paper | scalingbitcoin.org/papers/mimblewimble.txt | CT + cut-through UTXO compression; compact blockchain | Alternative CT model |
| On the Instability of Bitcoin Without the Block Reward | Carlsten, Kalodner, Weinberg, Narayanan | 2016 | CCS | dl.acm.org/doi/10.1145/2976749.2978408 | Fee sniping attacks when block reward vanishes; selfish mining incentives | Security analysis |
| Selfish Mining: A 25% Attack Against the Bitcoin Mining Protocol | Eyal, Sirer | 2014 | Financial Crypto | arxiv.org/abs/1311.0243 | Pools with >25% hash rate can profit by withholding blocks | Mining security |
| An Analysis of Attacks on Blockchain Consensus | Pass, Shi | 2017 | ArXiv | arxiv.org/abs/1612.06248 | Formal analysis of blockchain security in the sleepy model | Formal security |
| Prism: Deconstructing the Blockchain to Approach Physical Limits | Bagaria et al. | 2019 | CCS | arxiv.org/abs/1909.11261 | Parallel voting and transaction chains → 70,000 TPS theoretical | High-TPS design |
| The Bitcoin Backbone Protocol | Garay, Kiayias, Leonardos | 2015 | EUROCRYPT | eprint.iacr.org/2014/765 | Formal PoW backbone properties: common prefix, chain quality, chain growth | Formal PoW model |
| Ethereum 2.0 Annotated Specification | Buterin et al. | 2020 | GitHub | github.com/ethereum/annotated-spec | Beacon chain, attestations, BLS signatures, slashing | PoS implementation ref |
| PHANTOM: A Scalable BlockDAG Protocol | Sompolinsky, Zohar | 2018 | IACR | eprint.iacr.org/2018/104 | DAG-based blockchain; 100× TPS; confirms all blocks eventually | Throughput alternative |
| Monero Research Bulletin: RingCT | Noether et al. | 2016 | Research | getmonero.org/library/MRL-0005.pdf | Ring signatures + CT for sender + amount privacy; applied in production | Privacy reference |
| Algorand: Scaling Byzantine Agreements for Cryptocurrencies | Gilad et al. | 2017 | SOSP | dl.acm.org/doi/10.1145/3132747.3132757 | VRF-based sortition; BA* consensus; 1000 TPS; strong finality | PoS consensus design |
| Tendermint: Byzantine Fault Tolerance in the Age of Blockchains | Buchman | 2016 | Master's thesis | atrium.lib.uoguelph.ca/server/api/core/bitstreams/e0e2a7b0 | BFT SMR for blockchains; instant finality; 2/3 supermajority | Finality mechanism |

---

## State-of-the-Art Models

| Model / Tool | Task | Benchmark | Date | Source |
|-------------|------|-----------|------|--------|
| `BAAI/bge-large-en-v1.5` | Paper embedding + semantic search | MTEB #1 overall NDCG@10 | 2024-01 | HuggingFace |
| `facebook/bart-large-cnn` | Paper summarization | ROUGE-L 44.16 on CNN/DM | 2023-06 | HuggingFace |
| `libsecp256k1` (C) | ECDSA + Schnorr signing | ~100k sign/sec (CPU) | 2024 | bitcoin-core/secp256k1 |
| `py_ecc` | BLS12-381 pairing (for PoS aggregation) | Pure Python; use for prototyping | 2023 | ethereum/py_ecc |
| SHA-256d (hardware) | PoW hashing | ~10 TH/s (Antminer S21) | 2024 | Bitmain spec sheet |

---

## LLM Prompt Patterns

### Multi-Paper Protocol Synthesis
```
SYSTEM: You are a blockchain protocol researcher reviewing recent academic papers 
for applicability to a Bitcoin-forked blockchain (Bitchchain).

USER: Here are summaries of {N} recent papers:
{paper_summaries}

Analyze each for applicability to these three targets:
1. Throughput ≥ 70 TPS (current: 4 MB blocks + parallel validation)
2. Energy ≤ 50% of Bitcoin PoW (current: hybrid PoW/PoS with 2/3 stake finality)
3. Privacy: optional Confidential Transactions (Pedersen commitments, range proofs)

Return JSON:
{
  "applicable_findings": [...],
  "recommended_parameter_changes": [...],
  "risk_analysis": [...],
  "priority_action": "string"
}
```

### Protocol Trade-Off Analysis
```
USER: Analyze the trade-off: increasing Bitchchain block size from 4 MB to 8 MB.
Consider: TPS gain, propagation delay, orphan rate increase, centralization pressure 
on full nodes, bandwidth requirements. Recommend with quantified estimates.
```

### Security Vulnerability Review
```
USER: Review this consensus parameter change: [parameter]. 
Known attacks to check: selfish mining (>25% hash rate), 
nothing-at-stake (PoS), long-range attacks, eclipse attacks.
Return: vulnerability present (Y/N), severity (critical/high/medium/low), mitigation.
```

---

## Authoritative Data Sources

| Source | URL | Update Frequency | Contents |
|--------|-----|-----------------|----------|
| ArXiv cs.CR | arxiv.org/list/cs.CR/recent | Daily | Cryptography papers |
| ArXiv cs.DC | arxiv.org/list/cs.DC/recent | Daily | Distributed computing papers |
| Bitcoin-dev mailing list | lists.linuxfoundation.org/pipermail/bitcoin-dev/ | Irregular | Protocol proposals, BIPs |
| Bitcoin Improvement Proposals | github.com/bitcoin/bips | Irregular | Formal protocol specifications |
| Ethereum Research | ethresear.ch | Daily | PoS, sharding, ZKP research |
| Financial Cryptography | fc24.ifca.ai | Annual | Academic blockchain/crypto papers |
| IACR ePrint | eprint.iacr.org | Daily | Cryptography preprints |
| Papers with Code (blockchain) | paperswithcode.com/search?q=blockchain | Weekly | SOTA with code |
| Cambridge CBEI | ccaf.io/cbnsi/cbeci | Monthly | Bitcoin energy consumption index |

---

## Self-Update Protocol

```yaml
knowledge_updater_config:
  sources:
    - name: arxiv_cs_CR
      url: "https://export.arxiv.org/api/query"
      params:
        search_query: "cat:cs.CR AND (blockchain OR consensus OR zero-knowledge OR UTXO)"
        max_results: 25
        sortBy: submittedDate
        sortOrder: descending
    - name: arxiv_cs_DC
      url: "https://export.arxiv.org/api/query"
      params:
        search_query: "cat:cs.DC AND (blockchain OR distributed ledger OR byzantine fault)"
        max_results: 25
        sortBy: submittedDate
        sortOrder: descending
    - name: semantic_scholar
      url: "https://api.semanticscholar.org/graph/v1/paper/search"
      params:
        query: "blockchain consensus confidential transactions"
        fields: "title,authors,year,abstract,externalIds"
        limit: 20
    - name: papers_with_code
      url: "https://paperswithcode.com/api/v1/papers/"
      params:
        q: "blockchain throughput consensus"
        ordering: "-arxiv_id_v1"
        items_per_page: 20

  scoring:
    recency_window_days: 90
    recency_weight: 0.6
    relevance_weight: 0.4
    keywords:
      - blockchain
      - consensus
      - proof-of-stake
      - confidential transactions
      - zero-knowledge
      - UTXO
      - throughput
      - finality
      - Pedersen
      - Bulletproof

  output:
    file: SECOND-KNOWLEDGE-BRAIN.md
    max_new_entries_per_run: 10
    dedup_field: doi_or_url
    date_stamp_format: "ISO 8601"

  schedule: "0 2 * * 0"  # Weekly Sunday 02:00 UTC
```

---

## Knowledge Update Log

### 2026-06-08 (Initial Seed)
- Added 15 foundational papers covering Bitcoin UTXO model, PoW consensus, Casper FFG PoS, Confidential Transactions (Pedersen commitments), Bulletproofs, Tendermint, Algorand, and PHANTOM DAG protocol.
- Established prompt templates for multi-paper synthesis, protocol trade-off analysis, and security vulnerability review.
- Populated authoritative data sources table with 9 primary sources.
- Configured knowledge_updater.py with ArXiv cs.CR + cs.DC, Semantic Scholar, Papers with Code.
- **New entries added**: 15 | **Next scheduled run**: 2026-06-14 02:00 UTC
