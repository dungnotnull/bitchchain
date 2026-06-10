"""Bitchchain Blockchain Agent - Core modules."""

from agent.modules.blockchain_core import (
    Blockchain, Block, BlockHeader, Transaction, TxInput, TxOutput,
    UTXOSet, sha256d, bits_to_target, target_to_bits,
    create_genesis_block, BITCHCHAIN_VERSION, MAX_BLOCK_SIZE_BYTES,
    COINBASE_REWARD_SATOSHIS, HALVING_INTERVAL, TARGET_BLOCK_TIME_SEC,
    DIFFICULTY_ADJUSTMENT_BLOCKS,
    build_htlc_script, build_htlc_redeem_script, build_p2pkh_script,
    build_p2sh_script, compute_p2sh_address,
)
from agent.modules.consensus_engine import (
    HybridConsensus, ValidatorRegistry, ValidatorRecord, FinalityVote,
    MiningEngine, Checkpoint,
    MIN_STAKE_SATOSHIS, FINALITY_THRESHOLD, CHECKPOINT_INTERVAL,
)
from agent.modules.privacy_layer import (
    PedersenCommitment, RangeProof, RangeProofData, CTTransaction,
    ConfidentialTransactionEngine,
    _ecdsa_sign, _ecdsa_verify, _ecdsa_sign_data, _ecdsa_verify_data,
    _private_key_to_public_key, G, H, P, N,
)
from agent.modules.wallet import KeyPair, Wallet
from agent.modules.network_node import BitchchainNode
from agent.orchestrator import BitchchainOrchestrator
from agent.memory.memory_manager import MemoryManager

__all__ = [
    "Blockchain", "Block", "BlockHeader", "Transaction", "TxInput", "TxOutput",
    "UTXOSet", "HybridConsensus", "ValidatorRegistry", "ValidatorRecord",
    "FinalityVote", "MiningEngine", "Checkpoint",
    "PedersenCommitment", "RangeProof", "RangeProofData", "CTTransaction",
    "ConfidentialTransactionEngine", "KeyPair", "Wallet",
    "BitchchainNode", "BitchchainOrchestrator", "MemoryManager",
    "create_genesis_block", "sha256d",
]
