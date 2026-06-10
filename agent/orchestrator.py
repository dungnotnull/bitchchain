"""
orchestrator.py — Core agent decision loop for the Bitchchain node.

Routes CLI commands to the appropriate domain module, manages state transitions,
and coordinates the research synthesis pipeline with the blockchain node.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional

from agent.memory.memory_manager import MemoryManager
from agent.modules.blockchain_core import (
    Blockchain, Transaction, TxInput, TxOutput,
    create_genesis_block, BITCHCHAIN_VERSION
)
from agent.modules.consensus_engine import (
    HybridConsensus, ValidatorRegistry, FinalityVote
)
from agent.modules.privacy_layer import ConfidentialTransactionEngine
from agent.modules.network_node import BitchchainNode
from agent.rpc_server import JSONRPCServer

logger = logging.getLogger(__name__)


class BitchchainOrchestrator:
    """
    Central coordinator. Manages node lifecycle, routes commands, and runs the
    research agent loop when triggered.
    """

    def __init__(self, config: dict):
        self.config = config
        db_path = config.get("storage", {}).get("chain_db", "chain.db")
        agent_db = config.get("storage", {}).get("agent_db", "agent_memory.db")

        self.memory = MemoryManager(agent_db)
        self.chain = Blockchain(db_path)
        self.validator_registry = ValidatorRegistry(db_path)
        self.consensus = HybridConsensus(
            chain=self.chain,
            validator_registry=self.validator_registry,
            miner_address=config.get("node", {}).get("miner_address", ""),
        )
        self.ct_engine = ConfidentialTransactionEngine()
        self.network = BitchchainNode(
            host=config.get("node", {}).get("host", "0.0.0.0"),
            port=config.get("node", {}).get("p2p_port", 8333),
            chain_height_provider=lambda: self.chain.get_tip()[1],
        )
        self._node_running = False

        self.rpc_server = JSONRPCServer(
            host=config.get("node", {}).get("rpc_host", "127.0.0.1"),
            port=config.get("node", {}).get("rpc_port", 8332),
            rpc_user=config.get("node", {}).get("rpc_user", ""),
            rpc_password=config.get("node", {}).get("rpc_password", ""),
        )
        self.rpc_server.wire_orchestrator(self)

        # Wire network handlers
        self.network.set_block_handler(self._on_block_received)
        self.network.set_tx_handler(self._on_tx_received)

        self.memory.log_event("orchestrator_init", {"config": config})

    # ─── Node lifecycle ───────────────────────────────────────────────────────

    async def start_node(self):
        tip_hash, height = self.chain.get_tip()
        if height < 0:
            # First run: apply genesis block
            genesis = create_genesis_block()
            self.chain.apply_block(genesis)
            logger.info(f"Genesis block applied: {genesis.block_hash}")
        await self.network.start()
        await self.rpc_server.start()
        self._node_running = True
        self.memory.log_event("node_started", {"height": self.chain.get_tip()[1]})
        logger.info(f"Bitchchain node started. Chain height: {self.chain.get_tip()[1]}")

    async def stop_node(self):
        """Gracefully shut down the node, stopping RPC server and P2P network."""
        self._node_running = False
        try:
            await self.rpc_server.stop()
        except Exception as e:
            logger.warning(f"Error stopping RPC server: {e}")
        try:
            await self.network.stop()
        except Exception as e:
            logger.warning(f"Error stopping network: {e}")
        try:
            self.chain._conn.close()
            self.chain.utxo_set._conn.close()
            self.validator_registry._conn.close()
            self.memory._conn.close()
        except Exception as e:
            logger.warning(f"Error closing databases: {e}")
        self.memory.log_event("node_stopped")
        logger.info("Bitchchain node stopped gracefully.")

    # ─── Mining ───────────────────────────────────────────────────────────────

    def mine_block(self, regtest: bool = False) -> dict:
        mempool_txs_raw = self.memory.get_mempool()
        mempool_txs: List[Transaction] = []
        for tx_dict in mempool_txs_raw:
            try:
                inputs = [TxInput(**i) for i in tx_dict.get("inputs", [])]
                outputs = [TxOutput(**o) for o in tx_dict.get("outputs", [])]
                tx = Transaction(
                    version=tx_dict.get("version", 1),
                    inputs=inputs, outputs=outputs,
                    locktime=tx_dict.get("locktime", 0),
                    txid=tx_dict.get("txid", ""),
                )
                mempool_txs.append(tx)
            except Exception as e:
                logger.warning(f"Skipping invalid mempool tx: {e}")

        logger.info(f"Mining block with {len(mempool_txs)} mempool txs (regtest={regtest})")
        block = self.consensus.propose_block(mempool_txs, regtest=regtest)
        if block is None:
            return {"success": False, "error": "Mining failed (nonce exhausted)"}

        success, result = self.consensus.submit_block(block)
        if success:
            # Clear mined transactions from mempool
            mined_txids = [tx.txid for tx in block.transactions[1:]]
            self.memory.clear_mempool_txids(mined_txids)
            self.memory.save_chain_tip(block.block_hash, block.header.height)
            self.memory.log_event("block_mined", {
                "hash": block.block_hash, "height": block.header.height,
                "tx_count": len(block.transactions)
            })
            # Broadcast asynchronously
            asyncio.create_task(
                self.network.broadcast_block(block.block_hash, block.to_dict())
            ) if self._node_running else None
            return {
                "success": True,
                "block_hash": block.block_hash,
                "height": block.header.height,
                "tx_count": len(block.transactions),
                "size_bytes": block.size_bytes,
            }
        return {"success": False, "error": result}

    # ─── Transactions ─────────────────────────────────────────────────────────

    def send_transaction(self, to_address: str, amount_satoshis: int,
                          from_txid: str, from_vout: int,
                          from_script_sig: str = "",
                          fee_satoshis: int = 0) -> dict:
        script_pubkey = (
            "76a914" +
            __import__("hashlib").new(
                "ripemd160",
                __import__("hashlib").sha256(to_address.encode()).digest()
            ).hexdigest() + "88ac"
        )
        inp = TxInput(prev_txid=from_txid, prev_vout=from_vout, script_sig=from_script_sig)
        out = TxOutput(value_satoshis=amount_satoshis, script_pubkey=script_pubkey)
        tx = Transaction(version=1, inputs=[inp], outputs=[out])
        tx.txid = tx.compute_txid()
        self.memory.add_to_mempool(tx.txid, tx.to_dict(), fee_satoshis=fee_satoshis)
        self.memory.log_event("tx_submitted", {"txid": tx.txid, "amount": amount_satoshis})
        return {"success": True, "txid": tx.txid}

    def send_ct_transaction(self, sender_address: str, to_script: str,
                             amount_satoshis: int, fee_satoshis: int,
                             input_txid: str, input_vout: int,
                             input_blinding: int = 0) -> dict:
        ct_tx, output_blindings = self.ct_engine.build_ct_transaction(
            sender_address=sender_address,
            input_refs=[(input_txid, input_vout, input_blinding)],
            outputs_spec=[(amount_satoshis - fee_satoshis, to_script)],
            fee_satoshis=fee_satoshis,
        )
        self.memory.add_to_mempool(ct_tx.txid, ct_tx.to_dict(), fee_satoshis=fee_satoshis)
        self.memory.log_event("ct_tx_submitted", {"txid": ct_tx.txid})
        return {
            "success": True,
            "txid": ct_tx.txid,
            "output_blinding_factors": [hex(b) for b in output_blindings],
            "note": "Share blinding factors with recipient via encrypted channel.",
        }

    # ─── Validator staking ────────────────────────────────────────────────────

    def register_validator(self, address: str, stake_satoshis: int,
                            stake_txid: str) -> dict:
        _, height = self.chain.get_tip()
        success, msg = self.consensus.register_validator(address, stake_satoshis, stake_txid, height)
        self.memory.log_event("validator_registered", {"address": address, "stake": stake_satoshis, "success": success})
        return {"success": success, "message": msg}

    def submit_finality_vote(self, validator_address: str,
                              source_checkpoint: str, target_checkpoint: str,
                              signature: str = "") -> dict:
        vote = FinalityVote(
            validator_address=validator_address,
            source_checkpoint=source_checkpoint,
            target_checkpoint=target_checkpoint,
            stake_weight=0,  # Set by submit_vote
            signature=signature,
        )
        success, msg = self.consensus.submit_vote(vote)
        self.memory.log_event("finality_vote", {"validator": validator_address, "target": target_checkpoint})
        return {"success": success, "message": msg}

    # ─── Research pipeline ────────────────────────────────────────────────────

    def run_research_sync(self) -> dict:
        """Trigger knowledge_updater.py and LLM synthesis."""
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        try:
            from tools.knowledge_updater import KnowledgeUpdater
            from tools.llm_client import LLMClient

            updater = KnowledgeUpdater(
                config=self.config.get("knowledge_updater", {}),
                brain_path=self.config.get("paths", {}).get(
                    "knowledge_brain", "SECOND-KNOWLEDGE-BRAIN.md"
                ),
            )
            result = updater.run()
            self.memory.log_event("research_sync", result)

            # LLM synthesis of top new papers
            if result.get("new_entries"):
                client = LLMClient(config=self.config.get("llm", {}))
                synthesis = client.synthesize_blockchain_papers(result["new_entries"])
                self.memory.set("research", "latest_synthesis", synthesis)
                return {**result, "synthesis": synthesis}
            return result
        except Exception as e:
            logger.error(f"Research sync failed: {e}")
            return {"success": False, "error": str(e)}

    def ask_llm(self, question: str) -> str:
        """Direct LLM query about blockchain protocol design."""
        try:
            from tools.llm_client import LLMClient
            client = LLMClient(config=self.config.get("llm", {}))
            return client.ask(
                f"You are a blockchain protocol expert working on Bitchchain "
                f"(Bitcoin fork with hybrid PoW/PoS and Confidential Transactions). "
                f"Answer this question:\n\n{question}"
            )
        except Exception as e:
            return f"LLM unavailable: {e}"

    # ─── Network event handlers ───────────────────────────────────────────────

    def _on_block_received(self, block_data: dict):
        logger.info(f"Received block from peer: {block_data.get('block_hash', '?')[:16]}...")
        self.memory.log_event("block_received", {"hash": block_data.get("block_hash")})

    def _on_tx_received(self, tx_data: dict):
        txid = tx_data.get("txid", "")
        if txid:
            self.memory.add_to_mempool(txid, tx_data)
            self.memory.log_event("tx_received", {"txid": txid})

    # ─── Status ───────────────────────────────────────────────────────────────

    def status(self) -> dict:
        chain_info = self.chain.chain_info()
        consensus_info = self.consensus.consensus_status()
        network_info = self.network.network_info()
        memory_info = self.memory.status()
        rpc_info = self.rpc_server.status()
        return {
            "node": "running" if self._node_running else "stopped",
            "chain": chain_info,
            "consensus": consensus_info,
            "network": network_info,
            "rpc": rpc_info,
            "memory": memory_info,
            "improvement_targets": {
                "tps_goal": ">= 70 TPS (4 MB blocks + parallel validation)",
                "energy_goal": "<= 50% of Bitcoin PoW (hybrid PoW/PoS with PoS finality)",
                "privacy_goal": "Optional Confidential Transactions (Pedersen commitments + range proofs)",
                "htlc_support": "Lightning Network compatible HTLC scripts (P2SH wrapped)",
            },
        }
