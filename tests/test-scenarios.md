# test-scenarios.md — Bitchchain End-to-End Test Scenarios

## Scenario 1: Genesis Block and Chain Growth (Regtest)

**Setup**: Fresh database (delete chain.db if it exists). Network: regtest.
**Steps**:
1. `python -m agent.main start-node --regtest`  
   Expected: "Genesis block applied" log message; chain height = 0.
2. `python -m agent.main mine --regtest --count 10`  
   Expected: 10 blocks mined, heights 1–10, each with valid PoW hash.
3. `python -m agent.main status`  
   Expected: `"height": 10`, `"tip_hash"` = hash of block 10, UTXO set non-empty.
**Pass criteria**: Chain grows to height 10; all block hashes pass PoW target check.

---

## Scenario 2: Confidential Transaction — Send and Verify

**Setup**: Node running with at least 1 mined block (for UTXO to spend).
**Steps**:
1. `python -m agent.main send-ct --to 76a914...88ac --amount 100000000 --fee 1000 --from-txid <genesis_coinbase_txid> --from-vout 0`  
   Expected: `{"success": true, "txid": "...", "output_blinding_factors": ["0x..."]}`
2. `python -m agent.main mine --regtest` to confirm the CT transaction.
3. **Privacy verification**: inspect the mined block; output `value_satoshis` = 0 (hidden); `ct_commitment` present.
4. **Balance proof**: run `python tests/test_agent.py::test_ct_balance_proof`  
   Expected: `"Balance proof OK"` — input commitment = output commitment + fee commitment.
5. **Recipient decode**: using the blinding factor from step 1, call `ct_engine.recipient_decode_amount(commitment_hex, blinding_factor)` → should return `99999000` (amount minus fee).
**Pass criteria**: Observer cannot read amount; recipient with blinding factor can; balance proof passes.

---

## Scenario 3: Validator Registration and PoS Finality

**Setup**: Node running with height ≥ 100 (checkpoint height).
**Steps**:
1. `python -m agent.main stake --address BCC1TEST... --amount 3200000000 --stake-txid <txid>`  
   Expected: `{"success": true, "message": "Validator BCC1TEST... registered with 32 BCC stake"}`
2. `python -m agent.main vote --validator BCC1TEST... --source <block_0_hash> --target <block_100_hash>`  
   Expected: vote recorded; if single validator holds >2/3 total stake, `"FINALIZED"` in response.
3. `python -m agent.main status` → check `"last_checkpoint_finalized": true`.
**Pass criteria**: Finality vote accepted; checkpoint finalized when threshold met; double-vote triggers slashing.

---

## Scenario 4: Throughput Benchmark — ≥ 70 TPS

**Setup**: Regtest mode. Script creates 1000 transactions with pre-mined UTXOs.
**Steps**:
1. Run `python tests/test_agent.py::test_tps_benchmark`
2. Script mines 5 blocks each containing 200 transactions.
3. Measure: total transactions / total mining time = TPS.
**Expected**:
- Block size: ≤ 4 MB per block (verified by `block.size_bytes`)
- TPS on simulated local benchmark: ≥ 70 TPS (200 txs / target block time)
- All 1000 transactions confirmed in ≤ 5 blocks
**Pass criteria**: TPS ≥ 70; no double-spend detected; all UTXO set entries correct.

---

## Scenario 5: Research Sync — Knowledge Brain Update

**Setup**: Valid `ANTHROPIC_API_KEY` set (or Ollama running for offline mode).
**Steps**:
1. `python -m agent.main research-sync`
2. Expected log: "Fetched N candidate papers", "Appended M new entries to SECOND-KNOWLEDGE-BRAIN.md"
3. Open `SECOND-KNOWLEDGE-BRAIN.md`: verify new dated section appended with ≥ 5 entries.
4. Check LLM synthesis output: `{"applicable_findings": [...], "priority_action": "..."}`
5. Run again immediately: verify 0 duplicate entries (dedup working).
**Pass criteria**:
- ≥ 5 new papers added per run
- Zero duplicates on consecutive runs
- LLM synthesis produces JSON with at least 1 applicable finding
- Total run time < 5 minutes

---

## Scenario 6: Two-Node Block Propagation (Docker Testnet)

**Setup**: `docker-compose --profile testnet up`
**Steps**:
1. Node 1 mines a block: `docker exec bitchchain-node python -m agent.main mine --regtest`
2. Node 2 status: `docker exec bitchchain-node-2 python -m agent.main status`
3. Expected: Node 2 receives the block via P2P gossip; height matches Node 1 within 5 seconds.
4. Node 2 mines a block; Node 1 receives it.
**Pass criteria**: Both nodes maintain identical chain tips; no orphaned blocks in 10-block test.

---

## Scenario 7: Energy Model Verification

**Setup**: Hybrid PoW/PoS enabled (default).
**Measurement**:
1. Count PoW hash iterations to mine 100 blocks (recorded by mining engine).
2. Compare to pure-PoW equivalent: Bitcoin requires 6 confirmations; Bitchchain requires 1 (PoS finality).
3. Energy reduction = (6 confirmations × PoW work) vs (1 confirmation × PoW work + PoS vote).
**Expected**: PoS finality allows ≤ 1 confirmation; energy cost per finalized transaction ≤ 50% of Bitcoin 6-conf model.
**Pass criteria**: Ratio of confirmation work: Bitchchain/Bitcoin ≤ 0.5.
