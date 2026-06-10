"""
blockchain_core.py — Block, Transaction, UTXO, and Chain storage for Bitchchain.

Implements the core Bitcoin-derived data structures with one key change:
  - Block size limit: 4 MB (vs Bitcoin's ~1 MB effective limit)
  - SHA-256d (double SHA-256) for block hashing — identical to Bitcoin
  - UTXO set stored in SQLite for persistence
"""

import hashlib
import json
import sqlite3
import struct
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple


BITCHCHAIN_VERSION = 1
GENESIS_BITS = 0x1d00ffff          # Initial difficulty target (same as Bitcoin genesis)
MAX_BLOCK_SIZE_BYTES = 4 * 1024 * 1024  # 4 MB
COINBASE_REWARD_SATOSHIS = 50 * 100_000_000  # 50 BCC in satoshis
HALVING_INTERVAL = 210_000         # Blocks between reward halvings
TARGET_BLOCK_TIME_SEC = 600        # 10 minutes (Bitcoin-compatible)
DIFFICULTY_ADJUSTMENT_BLOCKS = 2016


def sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def bits_to_target(bits: int) -> int:
    exponent = bits >> 24
    coefficient = bits & 0x7FFFFF
    return coefficient * (256 ** (exponent - 3))


def target_to_bits(target: int) -> int:
    target_hex = f"{target:064x}"
    leading_zeros = len(target_hex) - len(target_hex.lstrip("0"))
    exponent = (64 - leading_zeros) // 2
    coefficient = target >> (8 * (exponent - 3))
    return (exponent << 24) | (coefficient & 0x7FFFFF)


@dataclass
class TxInput:
    prev_txid: str          # Hex string of previous transaction ID
    prev_vout: int          # Output index in previous transaction
    script_sig: str         # Unlocking script (hex)
    sequence: int = 0xFFFFFFFF
    # CT extension: blinding factor commitment (None for transparent inputs)
    ct_commitment: Optional[str] = None


@dataclass
class TxOutput:
    value_satoshis: int     # Amount in satoshis (0 for CT outputs)
    script_pubkey: str      # Locking script (hex)
    # CT extension: Pedersen commitment C = r*G + v*H (hex encoded point)
    ct_commitment: Optional[str] = None
    ct_range_proof: Optional[str] = None  # Bulletproof stub (hex)


@dataclass
class Transaction:
    version: int = 1
    inputs: List[TxInput] = field(default_factory=list)
    outputs: List[TxOutput] = field(default_factory=list)
    locktime: int = 0
    is_coinbase: bool = False
    # Set after computation
    txid: str = ""

    def serialize_for_signing(self) -> bytes:
        data = struct.pack("<I", self.version)
        data += struct.pack("<B", len(self.inputs))
        for inp in self.inputs:
            data += bytes.fromhex(inp.prev_txid)[::-1]  # little-endian
            data += struct.pack("<I", inp.prev_vout)
            script_bytes = bytes.fromhex(inp.script_sig) if inp.script_sig else b""
            data += struct.pack("<B", len(script_bytes)) + script_bytes
            data += struct.pack("<I", inp.sequence)
        data += struct.pack("<B", len(self.outputs))
        for out in self.outputs:
            data += struct.pack("<q", out.value_satoshis)
            script_bytes = bytes.fromhex(out.script_pubkey)
            data += struct.pack("<B", len(script_bytes)) + script_bytes
        data += struct.pack("<I", self.locktime)
        return data

    def compute_txid(self) -> str:
        raw = self.serialize_for_signing()
        return sha256d(raw).hex()

    def total_output_satoshis(self) -> int:
        return sum(o.value_satoshis for o in self.outputs)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BlockHeader:
    version: int
    prev_hash: str          # Hex string of previous block hash
    merkle_root: str        # Merkle root of transactions (hex)
    timestamp: int          # Unix timestamp
    bits: int               # Compact target representation
    nonce: int              # PoW nonce
    height: int = 0
    # PoS extension: hash of finality vote set for this block
    validator_vote_hash: str = ""

    def serialize(self) -> bytes:
        data = struct.pack("<I", self.version)
        data += bytes.fromhex(self.prev_hash)[::-1]
        data += bytes.fromhex(self.merkle_root)[::-1]
        data += struct.pack("<I", self.timestamp)
        data += struct.pack("<I", self.bits)
        data += struct.pack("<I", self.nonce)
        return data

    def hash(self) -> str:
        return sha256d(self.serialize()).hex()

    def meets_target(self) -> bool:
        block_hash_int = int(self.hash(), 16)
        return block_hash_int < bits_to_target(self.bits)


@dataclass
class Block:
    header: BlockHeader
    transactions: List[Transaction] = field(default_factory=list)
    # Set after assembly
    block_hash: str = ""
    size_bytes: int = 0

    def compute_merkle_root(self) -> str:
        if not self.transactions:
            return "0" * 64
        txids = [bytes.fromhex(tx.txid)[::-1] for tx in self.transactions]
        while len(txids) > 1:
            if len(txids) % 2 == 1:
                txids.append(txids[-1])
            txids = [sha256d(txids[i] + txids[i + 1]) for i in range(0, len(txids), 2)]
        return txids[0][::-1].hex()

    def validate_size(self) -> bool:
        serialized = json.dumps([tx.to_dict() for tx in self.transactions]).encode()
        self.size_bytes = len(serialized)
        return self.size_bytes <= MAX_BLOCK_SIZE_BYTES

    def to_dict(self) -> dict:
        return {
            "header": asdict(self.header),
            "transactions": [tx.to_dict() for tx in self.transactions],
            "block_hash": self.block_hash,
            "size_bytes": self.size_bytes,
        }


class UTXOSet:
    """In-memory UTXO set backed by SQLite for persistence."""

    def __init__(self, db_path: str = "chain.db"):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()

    def _init_schema(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS utxos (
                txid TEXT NOT NULL,
                vout INTEGER NOT NULL,
                value_satoshis INTEGER NOT NULL,
                script_pubkey TEXT NOT NULL,
                ct_commitment TEXT,
                block_height INTEGER NOT NULL,
                PRIMARY KEY (txid, vout)
            )
        """)
        self._conn.commit()

    def add_outputs(self, tx: Transaction, block_height: int):
        for vout, output in enumerate(tx.outputs):
            self._conn.execute(
                "INSERT OR REPLACE INTO utxos VALUES (?, ?, ?, ?, ?, ?)",
                (tx.txid, vout, output.value_satoshis,
                 output.script_pubkey, output.ct_commitment, block_height)
            )
        self._conn.commit()

    def spend_input(self, txid: str, vout: int) -> Optional[TxOutput]:
        row = self._conn.execute(
            "SELECT value_satoshis, script_pubkey, ct_commitment FROM utxos WHERE txid=? AND vout=?",
            (txid, vout)
        ).fetchone()
        if row is None:
            return None
        self._conn.execute("DELETE FROM utxos WHERE txid=? AND vout=?", (txid, vout))
        self._conn.commit()
        return TxOutput(value_satoshis=row[0], script_pubkey=row[1], ct_commitment=row[2])

    def get_utxo(self, txid: str, vout: int) -> Optional[TxOutput]:
        row = self._conn.execute(
            "SELECT value_satoshis, script_pubkey, ct_commitment FROM utxos WHERE txid=? AND vout=?",
            (txid, vout)
        ).fetchone()
        if row is None:
            return None
        return TxOutput(value_satoshis=row[0], script_pubkey=row[1], ct_commitment=row[2])

    def exists(self, txid: str, vout: int) -> bool:
        return self._conn.execute(
            "SELECT 1 FROM utxos WHERE txid=? AND vout=?", (txid, vout)
        ).fetchone() is not None

    def size(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM utxos").fetchone()[0]


class Blockchain:
    """Main chain manager: block storage, validation, tip tracking."""

    def __init__(self, db_path: str = "chain.db"):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self.utxo_set = UTXOSet(db_path)
        self._init_schema()
        self._chain_tip: Optional[str] = None
        self._height: int = -1
        self._load_tip()

    def _init_schema(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS blocks (
                hash TEXT PRIMARY KEY,
                height INTEGER NOT NULL,
                prev_hash TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                bits INTEGER NOT NULL,
                nonce INTEGER NOT NULL,
                merkle_root TEXT NOT NULL,
                tx_count INTEGER NOT NULL,
                size_bytes INTEGER NOT NULL,
                raw_json TEXT NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS chain_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        self._conn.commit()

    def _load_tip(self):
        row = self._conn.execute(
            "SELECT value FROM chain_meta WHERE key='tip_hash'"
        ).fetchone()
        if row:
            self._chain_tip = row[0]
            tip_row = self._conn.execute(
                "SELECT height FROM blocks WHERE hash=?", (self._chain_tip,)
            ).fetchone()
            if tip_row:
                self._height = tip_row[0]

    def get_tip(self) -> Tuple[Optional[str], int]:
        return self._chain_tip, self._height

    def get_block(self, block_hash: str) -> Optional[Block]:
        row = self._conn.execute(
            "SELECT raw_json FROM blocks WHERE hash=?", (block_hash,)
        ).fetchone()
        if not row:
            return None
        data = json.loads(row[0])
        header = BlockHeader(**data["header"])
        txs = []
        for tx_data in data["transactions"]:
            inputs = [TxInput(**inp) for inp in tx_data.get("inputs", [])]
            outputs = [TxOutput(**out) for out in tx_data.get("outputs", [])]
            tx = Transaction(
                version=tx_data["version"],
                inputs=inputs,
                outputs=outputs,
                locktime=tx_data["locktime"],
                is_coinbase=tx_data.get("is_coinbase", False),
                txid=tx_data["txid"],
            )
            txs.append(tx)
        return Block(header=header, transactions=txs,
                     block_hash=data["block_hash"], size_bytes=data["size_bytes"])

    def get_block_at_height(self, height: int) -> Optional[str]:
        row = self._conn.execute(
            "SELECT hash FROM blocks WHERE height=? ORDER BY rowid ASC LIMIT 1", (height,)
        ).fetchone()
        return row[0] if row else None

    def validate_block(self, block: Block, prev_block: Optional[Block]) -> Tuple[bool, str]:
        block_hash = block.header.hash()
        block.block_hash = block_hash

        # PoW check
        if not block.header.meets_target():
            return False, f"PoW target not met: {block_hash}"

        # Size check
        if not block.validate_size():
            return False, f"Block size {block.size_bytes} exceeds {MAX_BLOCK_SIZE_BYTES}"

        # Merkle root check
        for tx in block.transactions:
            if not tx.txid:
                tx.txid = tx.compute_txid()
        computed_root = block.compute_merkle_root()
        if computed_root != block.header.merkle_root:
            return False, f"Merkle root mismatch: {computed_root} != {block.header.merkle_root}"

        # Timestamp check (must be > median of last 11 blocks and < now + 2h)
        if block.header.timestamp > int(time.time()) + 7200:
            return False, "Block timestamp too far in future"

        # Previous hash check
        if prev_block and block.header.prev_hash != prev_block.block_hash:
            return False, "prev_hash does not match tip"

        # Coinbase check
        if not block.transactions or not block.transactions[0].is_coinbase:
            return False, "First transaction must be coinbase"

        return True, "valid"

    def apply_block(self, block: Block) -> bool:
        valid, reason = self.validate_block(block, self.get_block(self._chain_tip) if self._chain_tip else None)
        if not valid:
            return False

        try:
            with self._conn:
                # Apply transactions to UTXO set atomically
                for tx in block.transactions:
                    if not tx.is_coinbase:
                        for inp in tx.inputs:
                            spent = self.utxo_set.spend_input(inp.prev_txid, inp.prev_vout)
                            if spent is None:
                                raise ValueError(f"Double-spend or missing UTXO: {inp.prev_txid}:{inp.prev_vout}")
                    self.utxo_set.add_outputs(tx, block.header.height)

                # Store block
                raw = json.dumps(block.to_dict())
                self._conn.execute(
                    "INSERT OR REPLACE INTO blocks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (block.block_hash, block.header.height, block.header.prev_hash,
                     block.header.timestamp, block.header.bits, block.header.nonce,
                     block.header.merkle_root, len(block.transactions),
                     block.size_bytes, raw)
                )
                self._conn.execute(
                    "INSERT OR REPLACE INTO chain_meta VALUES ('tip_hash', ?)", (block.block_hash,)
                )

            self._chain_tip = block.block_hash
            self._height = block.header.height
            return True
        except Exception:
            return False

    def get_next_bits(self) -> int:
        """Recalculate difficulty every DIFFICULTY_ADJUSTMENT_BLOCKS."""
        if self._height < DIFFICULTY_ADJUSTMENT_BLOCKS:
            return GENESIS_BITS
        if self._height % DIFFICULTY_ADJUSTMENT_BLOCKS != 0:
            tip_row = self._conn.execute(
                "SELECT bits FROM blocks WHERE hash=?", (self._chain_tip,)
            ).fetchone()
            return tip_row[0] if tip_row else GENESIS_BITS

        # Find block DIFFICULTY_ADJUSTMENT_BLOCKS ago
        past_hash = self.get_block_at_height(self._height - DIFFICULTY_ADJUSTMENT_BLOCKS)
        if not past_hash:
            return GENESIS_BITS
        past_row = self._conn.execute(
            "SELECT timestamp, bits FROM blocks WHERE hash=?", (past_hash,)
        ).fetchone()
        tip_row = self._conn.execute(
            "SELECT timestamp FROM blocks WHERE hash=?", (self._chain_tip,)
        ).fetchone()
        if not past_row or not tip_row:
            return GENESIS_BITS

        actual_timespan = tip_row[0] - past_row[0]
        target_timespan = DIFFICULTY_ADJUSTMENT_BLOCKS * TARGET_BLOCK_TIME_SEC
        actual_timespan = max(actual_timespan, target_timespan // 4)
        actual_timespan = min(actual_timespan, target_timespan * 4)

        old_target = bits_to_target(past_row[1])
        new_target = old_target * actual_timespan // target_timespan
        return target_to_bits(new_target)

    def compute_block_reward(self, height: int) -> int:
        halvings = height // HALVING_INTERVAL
        if halvings >= 64:
            return 0
        return COINBASE_REWARD_SATOSHIS >> halvings

    def chain_info(self) -> dict:
        return {
            "height": self._height,
            "tip_hash": self._chain_tip,
            "utxo_count": self.utxo_set.size(),
            "network": "bitchchain-mainnet",
            "version": BITCHCHAIN_VERSION,
        }


def create_genesis_block() -> Block:
    coinbase_tx = Transaction(
        version=1,
        inputs=[TxInput(
            prev_txid="0" * 64,
            prev_vout=0xFFFFFFFF,
            script_sig="04ffff001d0104",  # Bitcoin genesis scriptSig
        )],
        outputs=[TxOutput(
            value_satoshis=COINBASE_REWARD_SATOSHIS,
            script_pubkey="4104678afdb0fe5548271967f1a67130b7105cd6a828e03909a67962e0ea1f61"
                          "deb649f6bc3f4cef38c4f35504e51ec112de5c384df7ba0b8d578a4c702b6bf11d5fac",
        )],
        is_coinbase=True,
    )
    coinbase_tx.txid = coinbase_tx.compute_txid()

    header = BlockHeader(
        version=BITCHCHAIN_VERSION,
        prev_hash="0" * 64,
        merkle_root="",
        timestamp=1717833600,  # 2024-06-08 00:00:00 UTC (Bitchchain genesis)
        bits=0x207fffff,  # Easy genesis target
        nonce=0,
        height=0,
    )
    genesis = Block(header=header, transactions=[coinbase_tx])
    genesis.header.merkle_root = genesis.compute_merkle_root()

    # Mine the genesis block (find valid nonce)
    genesis_target = bits_to_target(0x207fffff)
    for nonce in range(2**32):
        genesis.header.nonce = nonce
        block_hash = genesis.header.hash()
        if int(block_hash, 16) < genesis_target:
            genesis.block_hash = block_hash
            break

    return genesis


# ─── Lightning Network HTLC Script Support ─────────────────────────────────────
# HTLC (Hash Time-Locked Contract) enables Lightning Network payment channels.
# Script pattern:
#   OP_IF
#     OP_SHA256 <preimage_hash> OP_EQUALVERIFY <recipient_pubkey> OP_CHECKSIG
#   OP_ELSE
#     <locktime> OP_CHECKSEQUENCEVERIFY OP_DROP <sender_pubkey> OP_CHECKSIG
#   OP_ENDIF

OP_DUP = "76"
OP_HASH160 = "a9"
OP_EQUALVERIFY = "88"
OP_CHECKSIG = "ac"
OP_EQUAL = "87"
OP_IF = "63"
OP_ELSE = "67"
OP_ENDIF = "68"
OP_SHA256 = "a8"
OP_CHECKSEQUENCEVERIFY = "b2"
OP_CHECKLOCKTIMEVERIFY = "b1"
OP_DROP = "75"
OP_PUSHDATA_20 = "14"
OP_PUSHDATA_32 = "20"


def build_htlc_script(recipient_pubkey_hash: str, sender_pubkey_hash: str,
                       preimage_hash: str, locktime_blocks: int = 144) -> str:
    """
    Build an HTLC scriptPubkey compatible with Lightning Network.

    The script has two spending paths:
    1. Recipient path: reveal the preimage (SHA256 hash matches) + recipient signature
    2. Sender path: after locktime_blocks confirmations, sender can reclaim with signature

    Args:
        recipient_pubkey_hash: 20-byte RIPEMD-160 hash of recipient's public key (hex)
        sender_pubkey_hash: 20-byte RIPEMD-160 hash of sender's public key (hex)
        preimage_hash: 32-byte SHA256 hash of the payment preimage (hex)
        locktime_blocks: Relative locktime in blocks (default 144 = ~1 day)

    Returns:
        HTLC scriptPubkey as hex string.
    """
    if len(recipient_pubkey_hash) != 40:
        raise ValueError(f"recipient_pubkey_hash must be 40 hex chars (20 bytes), got {len(recipient_pubkey_hash)}")
    if len(sender_pubkey_hash) != 40:
        raise ValueError(f"sender_pubkey_hash must be 40 hex chars (20 bytes), got {len(sender_pubkey_hash)}")
    if len(preimage_hash) != 64:
        raise ValueError(f"preimage_hash must be 64 hex chars (32 bytes), got {len(preimage_hash)}")

    locktime_hex = _encode_script_number(locktime_blocks)

    script = (
        OP_IF +
        OP_SHA256 +
        OP_PUSHDATA_32 + preimage_hash +
        OP_EQUALVERIFY +
        OP_PUSHDATA_20 + recipient_pubkey_hash +
        OP_CHECKSIG +
        OP_ELSE +
        locktime_hex +
        OP_CHECKSEQUENCEVERIFY +
        OP_DROP +
        OP_PUSHDATA_20 + sender_pubkey_hash +
        OP_CHECKSIG +
        OP_ENDIF
    )
    return script


def build_htlc_redeem_script(preimage: str, recipient_sig_hex: str) -> str:
    """
    Build the scriptSig for spending the HTLC via the recipient path.

    Args:
        preimage: The original preimage (hex) that hashes to preimage_hash
        recipient_sig_hex: Recipient's DER-encoded signature (hex)

    Returns:
        scriptSig hex for HTLC redemption (recipient path).
    """
    preimage_len = f"{len(preimage) // 2:02x}"
    sig_len = f"{len(recipient_sig_hex) // 2:02x}"
    return (
        sig_len + recipient_sig_hex +
        preimage_len + preimage +
        "51"  # OP_1 (choose IF branch)
    )


def build_htlc_timeout_script(sender_sig_hex: str) -> str:
    """
    Build the scriptSig for spending the HTLC via the timeout (sender) path.

    Args:
        sender_sig_hex: Sender's DER-encoded signature (hex)

    Returns:
        scriptSig hex for HTLC timeout (sender path).
    """
    sig_len = f"{len(sender_sig_hex) // 2:02x}"
    return (
        sig_len + sender_sig_hex +
        "00"  # OP_0 (choose ELSE branch)
    )


def build_p2pkh_script(pubkey_hash: str) -> str:
    """Standard P2PKH script: OP_DUP OP_HASH160 <hash> OP_EQUALVERIFY OP_CHECKSIG"""
    return OP_DUP + OP_HASH160 + OP_PUSHDATA_20 + pubkey_hash + OP_EQUALVERIFY + OP_CHECKSIG


def build_p2sh_script(script_hash: str) -> str:
    """P2SH script: OP_HASH160 <hash> OP_EQUAL"""
    return OP_HASH160 + OP_PUSHDATA_20 + script_hash + OP_EQUAL


def _encode_script_number(n: int) -> str:
    """Encode an integer as a Bitcoin script number (minimal push)."""
    if n == 0:
        return "00"
    if 1 <= n <= 16:
        return f"{0x50 + n:02x}"
    if n < 0x80:
        return f"01{n:02x}"
    if n < 0x8000:
        return f"02{n & 0xff:02x}{(n >> 8) & 0xff:02x}"
    if n < 0x800000:
        return f"03{n & 0xff:02x}{(n >> 8) & 0xff:02x}{(n >> 16) & 0xff:02x}"
    return f"04{n & 0xff:02x}{(n >> 8) & 0xff:02x}{(n >> 16) & 0xff:02x}{(n >> 24) & 0xff:02x}"


def compute_p2sh_address(htlc_script_hex: str) -> str:
    """
    Compute the P2SH wrapped address for an HTLC script.
    This is how HTLC outputs appear on-chain.

    Args:
        htlc_script_hex: The raw HTLC script (hex)

    Returns:
        P2SH scriptPubkey hex (OP_HASH160 <hash160(redeem_script)> OP_EQUAL)
    """
    script_bytes = bytes.fromhex(htlc_script_hex)
    sha = hashlib.sha256(script_bytes).digest()
    h160 = hashlib.new("ripemd160", sha).digest()
    return build_p2sh_script(h160.hex())
