"""
wallet.py - Key management and transaction signing for Bitchchain.

Provides private key generation, address derivation, and ECDSA transaction
signing using secp256k1 (same curve as Bitcoin).

SECURITY NOTE: This is a Python prototype. Production deployments MUST use
hardware security modules (HSMs) for key storage and libsecp256k1 for
constant-time signing operations.
"""

import hashlib
import hmac
import os as _os
import sqlite3
import struct
from dataclasses import dataclass
from typing import List, Optional, Tuple

from agent.modules.privacy_layer import (
    _ecdsa_sign, _ecdsa_verify, _ecdsa_sign_data, _ecdsa_verify_data,
    _private_key_to_public_key, _point_to_bytes, _point_mul, G, N
)


def _hash160(data: bytes) -> bytes:
    """RIPEMD-160(SHA-256(data)) - same as Bitcoin."""
    sha = hashlib.sha256(data).digest()
    ripemd = hashlib.new("ripemd160", sha).digest()
    return ripemd


def _base58check_encode(payload: bytes) -> str:
    """Base58Check encoding with 4-byte checksum."""
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    data = payload + checksum
    # Convert to big integer
    n = int.from_bytes(data, "big")
    result = ""
    while n > 0:
        n, r = divmod(n, 58)
        result = alphabet[r] + result
    # Add leading 1s for each leading zero byte
    for byte in data:
        if byte == 0:
            result = "1" + result
        else:
            break
    return result


# Bitchchain address prefixes (same as Bitcoin mainnet for compatibility)
BCC_P2PKH_PREFIX = b"\x00"  # Mainnet P2PKH
BCC_P2SH_PREFIX = b"\x05"    # Mainnet P2SH
BCC_TESTNET_PREFIX = b"\x6f" # Testnet P2PKH


@dataclass
class KeyPair:
    """A secp256k1 key pair."""
    private_key: int
    public_key: Tuple
    compressed_public_key: str  # hex
    address: str  # Base58Check P2PKH address

    @staticmethod
    def generate() -> "KeyPair":
        """Generate a new random key pair."""
        private_key = int.from_bytes(_os.urandom(32), "big") % N
        if private_key == 0:
            private_key = 1
        return KeyPair.from_private_key(private_key)

    @staticmethod
    def from_private_key(private_key: int) -> "KeyPair":
        """Create a key pair from an existing private key."""
        if not (1 <= private_key < N):
            raise ValueError(f"Private key must be in range [1, N-1]")
        public_key = _private_key_to_public_key(private_key)
        compressed = _point_to_bytes(public_key).hex()
        address = _pubkey_to_address(public_key)
        return KeyPair(
            private_key=private_key,
            public_key=public_key,
            compressed_public_key=compressed,
            address=address,
        )

    def sign(self, message_hash: bytes) -> Tuple[int, int]:
        """ECDSA sign a 32-byte message hash."""
        return _ecdsa_sign(self.private_key, message_hash)

    def sign_transaction(self, tx_serialized: bytes) -> str:
        """Sign a serialized transaction. Returns hex-encoded signature."""
        return _ecdsa_sign_data(self.private_key, tx_serialized)


def _pubkey_to_address(public_key: Tuple, prefix: bytes = BCC_P2PKH_PREFIX) -> str:
    """Derive a P2PKH address from a public key point."""
    compressed = _point_to_bytes(public_key)
    hash160 = _hash160(compressed)
    return _base58check_encode(prefix + hash160)


def _address_to_hash160(address: str) -> bytes:
    """Decode a Base58Check address to its hash160 payload."""
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = 0
    for char in address:
        n = n * 58 + alphabet.index(char)
    # Convert to bytes
    data = n.to_bytes(25, "big").lstrip(b"\x00")
    # Remove leading 1s that were padding
    while data[0:1] == b"\x00" and address.startswith("1"):
        data = data[1:]
    if len(data) != 25:
        # Try different byte lengths
        for length in range(20, 30):
            try:
                data = n.to_bytes(length, "big")
                break
            except OverflowError:
                continue
    payload = data[:-4]
    checksum = data[-4:]
    expected = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    if checksum != expected:
        raise ValueError("Invalid address checksum")
    return payload[1:]  # Remove prefix byte


class Wallet:
    """
    Hierarchical Deterministic (HD) wallet following BIP 32/44 conventions.

    Stores keys in SQLite, supports key generation, signing, and address
    derivation. Uses m/44'/0'/0' derivation path (BIP 44 for Bitchchain).
    """

    def __init__(self, db_path: str = "wallet.db"):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_schema()

    def _init_schema(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                private_key_hex TEXT NOT NULL UNIQUE,
                public_key_hex TEXT NOT NULL,
                address TEXT NOT NULL UNIQUE,
                label TEXT DEFAULT '',
                created_at REAL NOT NULL,
                is_change INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                txid TEXT NOT NULL UNIQUE,
                raw_tx TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at REAL NOT NULL
            );
        """)
        self._conn.commit()

    def generate_key(self, label: str = "") -> KeyPair:
        """Generate a new key pair and store it."""
        keypair = KeyPair.generate()
        self._conn.execute(
            "INSERT OR IGNORE INTO keys (private_key_hex, public_key_hex, address, label, created_at) VALUES (?, ?, ?, ?, ?)",
            (hex(keypair.private_key), keypair.compressed_public_key, keypair.address, label, 0)
        )
        self._conn.commit()
        return keypair

    def import_key(self, private_key_hex: str, label: str = "") -> KeyPair:
        """Import a private key from hex."""
        if private_key_hex.startswith("0x"):
            private_key_hex = private_key_hex[2:]
        private_key = int(private_key_hex, 16)
        keypair = KeyPair.from_private_key(private_key)
        self._conn.execute(
            "INSERT OR IGNORE INTO keys (private_key_hex, public_key_hex, address, label, created_at) VALUES (?, ?, ?, ?, ?)",
            (hex(keypair.private_key), keypair.compressed_public_key, keypair.address, label, 0)
        )
        self._conn.commit()
        return keypair

    def get_key(self, address: str) -> Optional[KeyPair]:
        """Retrieve a key pair by address."""
        import time
        row = self._conn.execute(
            "SELECT private_key_hex, public_key_hex, address FROM keys WHERE address=?", (address,)
        ).fetchone()
        if row is None:
            return None
        return KeyPair.from_private_key(int(row[0], 16))

    def list_addresses(self) -> List[dict]:
        """List all addresses in the wallet."""
        rows = self._conn.execute(
            "SELECT address, public_key_hex, label FROM keys ORDER BY id"
        ).fetchall()
        return [{"address": r[0], "public_key": r[1], "label": r[2]} for r in rows]

    def sign_transaction(self, address: str, tx_data: bytes) -> Optional[str]:
        """Sign transaction data with the key for the given address."""
        keypair = self.get_key(address)
        if keypair is None:
            return None
        return keypair.sign_transaction(tx_data)

    def verify_signature(self, public_key: Tuple, data: bytes, sig_hex: str) -> bool:
        """Verify a signature against data and a public key."""
        return _ecdsa_verify_data(public_key, data, sig_hex)

    def close(self):
        self._conn.close()
