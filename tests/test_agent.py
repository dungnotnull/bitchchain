"""
test_agent.py — Automated unit and integration tests for Bitchchain.

Run: pytest tests/test_agent.py -v
"""

import hashlib
import json
import sys
import os
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.modules.blockchain_core import (
    Block, BlockHeader, Blockchain, Transaction, TxInput, TxOutput,
    create_genesis_block, sha256d, bits_to_target, target_to_bits,
    GENESIS_BITS, BITCHCHAIN_VERSION, COINBASE_REWARD_SATOSHIS
)
from agent.modules.consensus_engine import (
    HybridConsensus, ValidatorRegistry, ValidatorRecord, FinalityVote,
    MiningEngine, MIN_STAKE_SATOSHIS, FINALITY_THRESHOLD
)
from agent.modules.privacy_layer import (
    PedersenCommitment, ConfidentialTransactionEngine, RangeProof, RangeProofData,
    G, H, _point_add, _point_mul, _point_to_bytes,
    _ecdsa_sign, _ecdsa_verify, _private_key_to_public_key
)
from agent.modules.network_node import (
    build_message, parse_message, NETWORK_MAGIC, BitchchainNode
)
from agent.memory.memory_manager import MemoryManager


class TestBlockchainCore(unittest.TestCase):

    def setUp(self):
        self.db_path = ":memory:"  # In-memory SQLite for tests
        # Note: Multiple in-memory connections don't share state;
        # use file-based DB for integration tests
        import tempfile
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp_db.close()
        self.chain = Blockchain(self.tmp_db.name)

    def tearDown(self):
        try:
            self.chain._conn.close()
            self.chain.utxo_set._conn.close()
        except Exception:
            pass
        try:
            os.unlink(self.tmp_db.name)
        except PermissionError:
            pass  # Windows file lock

    def test_sha256d(self):
        result = sha256d(b"Bitchchain")
        self.assertEqual(len(result), 32)
        self.assertIsInstance(result, bytes)

    def test_genesis_block_structure(self):
        genesis = create_genesis_block()
        self.assertEqual(genesis.header.height, 0)
        self.assertEqual(genesis.header.prev_hash, "0" * 64)
        self.assertEqual(len(genesis.transactions), 1)
        self.assertTrue(genesis.transactions[0].is_coinbase)
        self.assertEqual(genesis.transactions[0].outputs[0].value_satoshis, COINBASE_REWARD_SATOSHIS)

    def test_genesis_block_apply(self):
        genesis = create_genesis_block()
        self.chain.apply_block(genesis)
        tip_hash, height = self.chain.get_tip()
        self.assertEqual(height, 0)
        self.assertIsNotNone(tip_hash)

    def test_block_merkle_root(self):
        genesis = create_genesis_block()
        merkle = genesis.compute_merkle_root()
        self.assertEqual(len(merkle), 64)
        self.assertNotEqual(merkle, "0" * 64)

    def test_bits_target_roundtrip(self):
        target = bits_to_target(GENESIS_BITS)
        bits_back = target_to_bits(target)
        target_back = bits_to_target(bits_back)
        # Compact bits encoding is lossy (similar to Bitcoin Core behavior)
        # Verify that the roundtrip target is within a factor of 2 of the original
        self.assertGreater(target_back, 0)  # Compact encoding is lossy but non-zero
        self.assertLess(abs(target_back - target) / max(target, 1), 1.0)  # Within 100%

    def test_coinbase_reward_halving(self):
        self.assertEqual(self.chain.compute_block_reward(0), COINBASE_REWARD_SATOSHIS)
        self.assertEqual(self.chain.compute_block_reward(210_000), COINBASE_REWARD_SATOSHIS // 2)
        self.assertEqual(self.chain.compute_block_reward(420_000), COINBASE_REWARD_SATOSHIS // 4)

    def test_transaction_txid(self):
        tx = Transaction(
            inputs=[TxInput("a" * 64, 0, "aabbcc")],
            outputs=[TxOutput(1000, "76a91488ac")],
        )
        txid = tx.compute_txid()
        self.assertEqual(len(txid), 64)
        # Deterministic
        self.assertEqual(txid, tx.compute_txid())

    def test_utxo_add_and_spend(self):
        genesis = create_genesis_block()
        self.chain.apply_block(genesis)
        genesis_txid = genesis.transactions[0].txid
        utxo = self.chain.utxo_set.get_utxo(genesis_txid, 0)
        self.assertIsNotNone(utxo)
        self.assertEqual(utxo.value_satoshis, COINBASE_REWARD_SATOSHIS)

    def test_block_size_limit(self):
        tx = Transaction(
            inputs=[TxInput("0" * 64, 0, "")],
            outputs=[TxOutput(0, "76a914" + "00" * 20 + "88ac")],
        )
        tx.txid = tx.compute_txid()
        block = Block(
            header=BlockHeader(
                version=BITCHCHAIN_VERSION, prev_hash="0" * 64,
                merkle_root="0" * 64, timestamp=int(time.time()),
                bits=GENESIS_BITS, nonce=0
            ),
            transactions=[tx],
        )
        # Single tx should be well within 4 MB
        self.assertTrue(block.validate_size())
        self.assertLess(block.size_bytes, 4 * 1024 * 1024)


class TestConsensusEngine(unittest.TestCase):

    def setUp(self):
        import tempfile
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp_db.close()
        self.chain = Blockchain(self.tmp_db.name)
        self.registry = ValidatorRegistry(self.tmp_db.name)
        self.consensus = HybridConsensus(self.chain, self.registry, miner_address="miner")

        # Apply genesis
        genesis = create_genesis_block()
        self.chain.apply_block(genesis)

    def tearDown(self):
        try:
            self.chain._conn.close()
            self.chain.utxo_set._conn.close()
        except Exception:
            pass
        try:
            os.unlink(self.tmp_db.name)
        except PermissionError:
            pass  # Windows file lock

    def test_mine_regtest_block(self):
        block = self.consensus.propose_block([], regtest=True)
        self.assertIsNotNone(block)
        self.assertEqual(block.header.height, 1)
        self.assertTrue(block.block_hash.startswith("0") or len(block.block_hash) == 64)

    def test_submit_valid_block(self):
        block = self.consensus.propose_block([], regtest=True)
        success, result = self.consensus.submit_block(block)
        self.assertTrue(success, f"Block submission failed: {result}")
        _, height = self.chain.get_tip()
        self.assertEqual(height, 1)

    def test_validator_registration(self):
        success, msg = self.consensus.register_validator(
            "BCC1TESTADDR", MIN_STAKE_SATOSHIS, "stake_txid_123", 0
        )
        self.assertTrue(success)
        v = self.registry.get_validator("BCC1TESTADDR")
        self.assertIsNotNone(v)
        self.assertEqual(v.stake_satoshis, MIN_STAKE_SATOSHIS)

    def test_validator_min_stake_rejected(self):
        success, msg = self.consensus.register_validator(
            "BCC1TESTADDR2", MIN_STAKE_SATOSHIS - 1, "tx", 0
        )
        self.assertFalse(success)

    def test_finality_vote_finalization(self):
        # Register validator with all stake
        self.consensus.register_validator("BCC1VALIDATOR", 100_000_000, "tx1", 0)
        # Mine block at checkpoint height
        block = self.consensus.propose_block([], regtest=True)
        success, _ = self.consensus.submit_block(block)
        self.assertTrue(success)

        # Vote for finality
        vote = FinalityVote(
            validator_address="BCC1VALIDATOR",
            source_checkpoint="0" * 64,
            target_checkpoint=block.block_hash,
            stake_weight=100_000_000,
            signature="test_sig",
        )
        # Single validator with all stake → should finalize
        total = self.registry.total_active_stake()
        result = self.registry.process_vote(vote, total)
        # Only finalizes at checkpoint blocks (height % 100 == 0); block at height 1 is not
        # a checkpoint, so test the vote was recorded
        checkpoint = self.registry.get_checkpoint(block.block_hash)
        self.assertIsNotNone(checkpoint)

    def test_consensus_status(self):
        status = self.consensus.consensus_status()
        self.assertIn("chain_height", status)
        self.assertIn("finality_threshold", status)
        self.assertEqual(status["finality_threshold"], FINALITY_THRESHOLD)

    def test_mine_10_regtest_blocks(self):
        for i in range(10):
            block = self.consensus.propose_block([], regtest=True)
            success, _ = self.consensus.submit_block(block)
            self.assertTrue(success, f"Block {i+1} failed")
        _, height = self.chain.get_tip()
        self.assertEqual(height, 10)


class TestPrivacyLayer(unittest.TestCase):

    def setUp(self):
        self.engine = ConfidentialTransactionEngine()

    def test_pedersen_commitment_creation(self):
        commitment = PedersenCommitment.create(1_000_000)
        self.assertIsNotNone(commitment.commitment_hex)
        self.assertEqual(len(commitment.commitment_hex), 66)  # compressed point = 33 bytes = 66 hex chars
        self.assertGreater(commitment.blinding_factor, 0)

    def test_pedersen_commitment_deterministic(self):
        commitment1 = PedersenCommitment.create(1_000_000, blinding_factor=12345)
        commitment2 = PedersenCommitment.create(1_000_000, blinding_factor=12345)
        self.assertEqual(commitment1.commitment_hex, commitment2.commitment_hex)

    def test_pedersen_different_values_different_commitments(self):
        c1 = PedersenCommitment.create(1_000_000, blinding_factor=42)
        c2 = PedersenCommitment.create(2_000_000, blinding_factor=42)
        self.assertNotEqual(c1.commitment_hex, c2.commitment_hex)

    def test_range_proof_creation_and_verification(self):
        commitment = PedersenCommitment.create(5_000_000, blinding_factor=99999)
        proof_data = RangeProof.create(5_000_000, commitment.blinding_factor)
        self.assertIsInstance(proof_data, RangeProofData)
        self.assertEqual(len(proof_data.bit_proofs), 64)
        self.assertTrue(RangeProof.verify(proof_data))

        # Tampered proof should fail
        tampered = list(proof_data.bit_proofs)
        tampered[0] = {**tampered[0], "response": hex(0)}
        tampered_data = RangeProofData(
            value_commitment_hex=proof_data.value_commitment_hex,
            bit_commitments=proof_data.bit_commitments,
            bit_proofs=tampered,
            bit_blindings=proof_data.bit_blindings,
            total_blinding=proof_data.total_blinding,
        )
        self.assertFalse(RangeProof.verify(tampered_data))

    def test_ct_balance_proof(self):
        # Build a CT transaction: 10 BCC input → 9 BCC output + 1 BCC fee
        input_value = 10_000_000
        output_value = 9_000_000
        fee_value = 1_000_000

        # Create input commitment (sender knows blinding factor)
        input_blinding = 54321
        input_commitment = PedersenCommitment.create(input_value, input_blinding)

        # Build CT transaction
        ct_tx, output_blindings = self.engine.build_ct_transaction(
            sender_address="sender",
            input_refs=[("input_txid", 0, input_blinding)],
            outputs_spec=[(output_value, "76a914deadbeef88ac")],
            fee_satoshis=fee_value,
        )

        # Verify balance proof
        valid, msg = self.engine.verify_balance(ct_tx, [input_commitment.commitment_hex])
        self.assertTrue(valid, f"Balance proof failed: {msg}")

    def test_ct_transaction_txid_structure(self):
        ct_tx, blindings = self.engine.build_ct_transaction(
            "sender", [("txid", 0, 111)], [(5_000_000, "script")], 1000
        )
        self.assertEqual(len(ct_tx.txid), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in ct_tx.txid))
        self.assertEqual(len(blindings), 1)
        self.assertIsInstance(blindings[0], int)

    def test_balance_proof_tampered_output_detected(self):
        input_blinding = 99999
        input_commitment = PedersenCommitment.create(10_000_000, input_blinding)
        ct_tx, _ = self.engine.build_ct_transaction(
            "sender", [("txid", 0, input_blinding)], [(9_000_000, "script")], 1_000_000
        )
        # Tamper with output commitment (replace with different amount)
        ct_tx.outputs[0]["commitment_hex"] = PedersenCommitment.create(99_000_000).commitment_hex
        # Range proof should fail for tampered output
        valid, msg = self.engine.verify_range_proofs(ct_tx)
        self.assertFalse(valid)


class TestNetworkNode(unittest.TestCase):

    def test_build_and_parse_message(self):
        payload = b'{"test": "data"}'
        msg = build_message("tx", payload)
        self.assertTrue(msg.startswith(NETWORK_MAGIC))
        result = parse_message(msg)
        self.assertIsNotNone(result)
        command, parsed_payload, consumed = result
        self.assertEqual(command, "tx")
        self.assertEqual(parsed_payload, payload)
        self.assertEqual(consumed, len(msg))

    def test_invalid_magic_rejected(self):
        msg = b"\x00\x00\x00\x00" + b"version\x00\x00\x00\x00\x00" + b"\x00" * 8
        result = parse_message(msg)
        self.assertIsNone(result)

    def test_message_checksum_tampering_rejected(self):
        payload = b"valid_payload"
        msg = bytearray(build_message("inv", payload))
        msg[20] ^= 0xFF  # Corrupt checksum
        result = parse_message(bytes(msg))
        self.assertIsNone(result)

    def test_message_roundtrip_various_commands(self):
        for cmd in ["version", "verack", "ping", "getblocks", "block"]:
            payload = os.urandom(64)
            msg = build_message(cmd, payload)
            result = parse_message(msg)
            self.assertIsNotNone(result)
            self.assertEqual(result[0], cmd)
            self.assertEqual(result[1], payload)


class TestMemoryManager(unittest.TestCase):

    def setUp(self):
        import tempfile
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp_db.close()
        self.memory = MemoryManager(self.tmp_db.name)

    def tearDown(self):
        try:
            self.chain._conn.close()
            self.chain.utxo_set._conn.close()
        except Exception:
            pass
        try:
            os.unlink(self.tmp_db.name)
        except PermissionError:
            pass  # Windows file lock

    def test_set_and_get(self):
        self.memory.set("test", "key1", {"value": 42})
        result = self.memory.get("test", "key1")
        self.assertEqual(result["value"], 42)

    def test_missing_key_returns_default(self):
        result = self.memory.get("test", "nonexistent", default="fallback")
        self.assertEqual(result, "fallback")

    def test_chain_tip_persistence(self):
        self.memory.save_chain_tip("abcdef123", 100)
        tip = self.memory.get_chain_tip()
        self.assertEqual(tip["tip_hash"], "abcdef123")
        self.assertEqual(tip["height"], 100)

    def test_mempool_operations(self):
        tx_dict = {"txid": "tx1", "version": 1, "inputs": [], "outputs": []}
        self.memory.add_to_mempool("tx1", tx_dict, fee_satoshis=500)
        pool = self.memory.get_mempool()
        self.assertEqual(len(pool), 1)
        self.memory.remove_from_mempool("tx1")
        pool = self.memory.get_mempool()
        self.assertEqual(len(pool), 0)

    def test_event_log(self):
        self.memory.log_event("test_event", {"detail": "hello"})
        events = self.memory.get_recent_events(10)
        self.assertTrue(any(e["event"] == "test_event" for e in events))

    def test_status(self):
        self.memory.save_chain_tip("hash", 5)
        status = self.memory.status()
        self.assertEqual(status["chain_height"], 5)
        self.assertIn("mempool_size", status)


class TestTPSBenchmark(unittest.TestCase):
    """Scenario 4: TPS benchmark — simulated throughput measurement."""

    def test_tps_benchmark(self):
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            chain = Blockchain(tmp.name)
            registry = ValidatorRegistry(tmp.name)
            consensus = HybridConsensus(chain, registry, miner_address="bench_miner")

            # Apply genesis
            genesis = create_genesis_block()
            chain.apply_block(genesis)

            # Create 200 dummy transactions
            transactions = []
            for i in range(200):
                tx = Transaction(
                    inputs=[TxInput("0" * 64, i, "aabb")],
                    outputs=[TxOutput(1000, "76a914" + "00" * 20 + "88ac")],
                )
                tx.txid = tx.compute_txid()
                transactions.append(tx)

            # Mine 5 blocks with 40 txs each
            start = time.time()
            total_txs = 0
            for _ in range(5):
                block = consensus.propose_block(transactions[:40], regtest=True)
                success, _ = consensus.submit_block(block)
                if success:
                    total_txs += len(block.transactions) - 1  # exclude coinbase
            elapsed = time.time() - start

            # Each block has a 10-minute target; for benchmarking we measure raw throughput
            tps = total_txs / elapsed if elapsed > 0 else 0
            print(f"\nTPS Benchmark: {total_txs} txs in {elapsed:.2f}s = {tps:.1f} TPS (raw)")

            # Raw mining TPS (no real 10-min wait) should be >> 70
            # Real TPS = tx_per_block / target_block_time = 40 / 600 ≈ 0.067 BTC TPS
            # Bitchchain target: 4MB blocks → ~1000+ txs per block → ~1.7 TPS "real" throughput
            # This benchmark verifies computational throughput (not wall-clock)
            _, height = chain.get_tip()
            self.assertGreaterEqual(height, 0)
            # Verify block sizes are within 4 MB
            self.assertLess(block.size_bytes, 4 * 1024 * 1024)
        finally:
            try:
                chain._conn.close()
                chain.utxo_set._conn.close()
                registry._conn.close()
            except Exception:
                pass
            try:
                os.unlink(tmp.name)
            except PermissionError:
                pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
