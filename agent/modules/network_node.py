"""
network_node.py — Async P2P network node for Bitchchain.

Implements a subset of the Bitcoin P2P protocol:
  - Message framing: 4-byte magic + 12-byte command + 4-byte length + 4-byte checksum + payload
  - Handshake: version → verack
  - Block/transaction gossip: inv → getdata → block/tx
  - Peer management: DNS seed lookup, max peers, disconnect on error

Magic bytes: 0xBCC14221 (Bitchchain mainnet)
Default port: 8333 (same as Bitcoin — change for mainnet deployment)
"""

import asyncio
import hashlib
import json
import logging
import socket
import struct
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

NETWORK_MAGIC = b"\xbc\xc1\x42\x21"
DEFAULT_PORT = 8333
MAX_PEERS = 8
PROTOCOL_VERSION = 70015
USER_AGENT = "/Bitchchain:0.1.0/"
HANDSHAKE_TIMEOUT = 30
MESSAGE_MAX_SIZE = 32 * 1024 * 1024  # 32 MB

# DNS seeds for mainnet peer discovery
DNS_SEEDS = [
    "seed.bitchchain.example.com",
    "seed2.bitchchain.example.com",
]

# Network parameters by mode
NETWORK_PARAMS = {
    "mainnet": {
        "magic": b"\xbc\xc1\x42\x21",
        "default_port": 8333,
        "rpc_port": 8332,
        "genesis_timestamp": 1717833600,
        "genesis_message": "Bitchchain Genesis Block - Hybrid PoW/PoS with Confidential Transactions",
    },
    "testnet": {
        "magic": b"\xbc\xc1\x42\x22",
        "default_port": 18333,
        "rpc_port": 18332,
        "genesis_timestamp": 1717833600,
        "genesis_message": "Bitchchain Testnet Genesis",
    },
    "regtest": {
        "magic": b"\xbc\xc1\x42\x23",
        "default_port": 18444,
        "rpc_port": 18443,
        "genesis_timestamp": 1717833600,
        "genesis_message": "Bitchchain Regtest Genesis",
    },
}


def _sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def _checksum(payload: bytes) -> bytes:
    return _sha256d(payload)[:4]


def build_message(command: str, payload: bytes) -> bytes:
    cmd = command.encode("ascii").ljust(12, b"\x00")[:12]
    length = struct.pack("<I", len(payload))
    ck = _checksum(payload)
    return NETWORK_MAGIC + cmd + length + ck + payload


def parse_message(data: bytes) -> Optional[tuple]:
    if len(data) < 24:
        return None
    if data[:4] != NETWORK_MAGIC:
        return None
    command = data[4:16].rstrip(b"\x00").decode("ascii", errors="replace")
    length = struct.unpack("<I", data[16:20])[0]
    if length > MESSAGE_MAX_SIZE:
        return None
    checksum = data[20:24]
    if len(data) < 24 + length:
        return None
    payload = data[24:24 + length]
    if _checksum(payload) != checksum:
        return None
    return command, payload, 24 + length


def build_version_payload(height: int, recv_addr: str = "127.0.0.1") -> bytes:
    data = struct.pack("<i", PROTOCOL_VERSION)
    data += struct.pack("<Q", 1)  # services
    data += struct.pack("<q", int(time.time()))
    data += b"\x00" * 26  # addr_recv (simplified)
    data += b"\x00" * 26  # addr_from
    data += struct.pack("<Q", 0)  # nonce
    ua = USER_AGENT.encode("ascii")
    data += bytes([len(ua)]) + ua
    data += struct.pack("<i", height)
    data += b"\x01"  # relay
    return data


def build_inv_payload(inv_type: int, hashes: List[str]) -> bytes:
    data = bytes([len(hashes)])
    for h in hashes:
        data += struct.pack("<I", inv_type)
        data += bytes.fromhex(h)[::-1]  # little-endian
    return data


def build_getdata_payload(inv_type: int, hashes: List[str]) -> bytes:
    return build_inv_payload(inv_type, hashes)


INV_TX = 1
INV_BLOCK = 2


@dataclass
class PeerInfo:
    address: str
    port: int
    version: int = 0
    height: int = 0
    user_agent: str = ""
    connected_at: float = field(default_factory=time.time)
    handshake_done: bool = False
    known_inv: Set[str] = field(default_factory=set)


class BitchchainNode:
    """
    Async P2P node. Manages peer connections, message routing, and block/tx gossip.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = DEFAULT_PORT,
                 chain_height_provider: Callable[[], int] = lambda: 0):
        self.host = host
        self.port = port
        self._get_height = chain_height_provider
        self._peers: Dict[str, PeerInfo] = {}
        self._writers: Dict[str, asyncio.StreamWriter] = {}
        self._known_blocks: Set[str] = set()
        self._known_txs: Set[str] = set()
        self._on_block_received: Optional[Callable] = None
        self._on_tx_received: Optional[Callable] = None
        self._server: Optional[asyncio.Server] = None

    def set_block_handler(self, handler: Callable):
        self._on_block_received = handler

    def set_tx_handler(self, handler: Callable):
        self._on_tx_received = handler

    async def start(self):
        self._server = await asyncio.start_server(
            self._handle_connection, self.host, self.port
        )
        logger.info(f"Bitchchain node listening on {self.host}:{self.port}")
        asyncio.create_task(self._connect_to_seeds())

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        for writer in self._writers.values():
            try:
                writer.close()
            except Exception:
                pass

    async def _connect_to_seeds(self):
        """Resolve DNS seeds and connect to first few addresses."""
        for seed in DNS_SEEDS:
            try:
                loop = asyncio.get_event_loop()
                results = await loop.getaddrinfo(seed, DEFAULT_PORT,
                                                  family=socket.AF_INET,
                                                  type=socket.SOCK_STREAM)
                for _, _, _, _, sockaddr in results[:2]:
                    addr, port = sockaddr[0], sockaddr[1]
                    if len(self._peers) < MAX_PEERS:
                        asyncio.create_task(self.connect_to_peer(addr, port))
            except Exception as e:
                logger.debug(f"DNS seed {seed} failed: {e}")

    async def connect_to_peer(self, addr: str, port: int = DEFAULT_PORT) -> bool:
        peer_key = f"{addr}:{port}"
        if peer_key in self._peers:
            return False
        if len(self._peers) >= MAX_PEERS:
            return False
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(addr, port), timeout=HANDSHAKE_TIMEOUT
            )
            self._peers[peer_key] = PeerInfo(address=addr, port=port)
            self._writers[peer_key] = writer
            asyncio.create_task(self._peer_loop(peer_key, reader, writer))
            await self._send_version(peer_key, writer)
            return True
        except Exception as e:
            logger.debug(f"Failed to connect to {peer_key}: {e}")
            return False

    async def _handle_connection(self, reader: asyncio.StreamReader,
                                  writer: asyncio.StreamWriter):
        addr = writer.get_extra_info("peername")
        peer_key = f"{addr[0]}:{addr[1]}"
        self._peers[peer_key] = PeerInfo(address=addr[0], port=addr[1])
        self._writers[peer_key] = writer
        await self._send_version(peer_key, writer)
        await self._peer_loop(peer_key, reader, writer)

    async def _send_version(self, peer_key: str, writer: asyncio.StreamWriter):
        payload = build_version_payload(self._get_height())
        msg = build_message("version", payload)
        try:
            writer.write(msg)
            await writer.drain()
        except Exception as e:
            logger.debug(f"send_version failed for {peer_key}: {e}")

    async def _peer_loop(self, peer_key: str, reader: asyncio.StreamReader,
                          writer: asyncio.StreamWriter):
        buffer = b""
        try:
            while True:
                chunk = await asyncio.wait_for(reader.read(65536), timeout=60)
                if not chunk:
                    break
                buffer += chunk
                if len(buffer) > MESSAGE_MAX_SIZE:
                    logger.warning(f"Peer {peer_key} buffer overflow, disconnecting")
                    break
                while len(buffer) >= 24:
                    result = parse_message(buffer)
                    if result is None:
                        break
                    command, payload, consumed = result
                    buffer = buffer[consumed:]
                    await self._handle_message(peer_key, writer, command, payload)
        except Exception as e:
            logger.debug(f"Peer {peer_key} disconnected: {e}")
        finally:
            self._peers.pop(peer_key, None)
            self._writers.pop(peer_key, None)
            try:
                writer.close()
            except Exception:
                pass

    async def _handle_message(self, peer_key: str, writer: asyncio.StreamWriter,
                               command: str, payload: bytes):
        peer = self._peers.get(peer_key)
        if peer is None:
            return

        if command == "version":
            if len(payload) >= 4:
                peer.version = struct.unpack("<i", payload[:4])[0]
            writer.write(build_message("verack", b""))
            await writer.drain()
            peer.handshake_done = True
            logger.info(f"Handshake complete with {peer_key}")

        elif command == "verack":
            peer.handshake_done = True

        elif command == "ping":
            writer.write(build_message("pong", payload))
            await writer.drain()

        elif command == "inv":
            if not peer.handshake_done:
                return
            await self._handle_inv(peer_key, writer, payload)

        elif command == "block":
            try:
                block_data = json.loads(payload.decode("utf-8"))
                if self._on_block_received:
                    await asyncio.get_event_loop().run_in_executor(
                        None, self._on_block_received, block_data
                    )
            except Exception as e:
                logger.debug(f"Block parse error from {peer_key}: {e}")

        elif command == "tx":
            try:
                tx_data = json.loads(payload.decode("utf-8"))
                if self._on_tx_received:
                    await asyncio.get_event_loop().run_in_executor(
                        None, self._on_tx_received, tx_data
                    )
            except Exception as e:
                logger.debug(f"TX parse error from {peer_key}: {e}")

        elif command == "getaddr":
            # Return known peer addresses
            writer.write(build_message("addr", b"\x00"))
            await writer.drain()

    async def _handle_inv(self, peer_key: str, writer: asyncio.StreamWriter,
                           payload: bytes):
        if len(payload) < 1:
            return
        count = payload[0]
        getdata_hashes_block = []
        getdata_hashes_tx = []
        offset = 1
        for _ in range(count):
            if offset + 36 > len(payload):
                break
            inv_type = struct.unpack("<I", payload[offset:offset + 4])[0]
            inv_hash = payload[offset + 4:offset + 36][::-1].hex()
            offset += 36
            if inv_type == INV_BLOCK and inv_hash not in self._known_blocks:
                getdata_hashes_block.append(inv_hash)
            elif inv_type == INV_TX and inv_hash not in self._known_txs:
                getdata_hashes_tx.append(inv_hash)

        if getdata_hashes_block:
            writer.write(build_message("getdata",
                                       build_getdata_payload(INV_BLOCK, getdata_hashes_block)))
            await writer.drain()
        if getdata_hashes_tx:
            writer.write(build_message("getdata",
                                       build_getdata_payload(INV_TX, getdata_hashes_tx)))
            await writer.drain()

    async def broadcast_block(self, block_hash: str, block_data: dict):
        if block_hash in self._known_blocks:
            return
        self._known_blocks.add(block_hash)
        payload = json.dumps(block_data).encode("utf-8")
        msg = build_message("block", payload)
        for peer_key, writer in list(self._writers.items()):
            peer = self._peers.get(peer_key)
            if peer and peer.handshake_done and block_hash not in peer.known_inv:
                try:
                    writer.write(msg)
                    await writer.drain()
                    peer.known_inv.add(block_hash)
                except Exception as e:
                    logger.debug(f"Broadcast block to {peer_key} failed: {e}")

    async def broadcast_tx(self, tx_hash: str, tx_data: dict):
        if tx_hash in self._known_txs:
            return
        self._known_txs.add(tx_hash)
        payload = json.dumps(tx_data).encode("utf-8")
        msg = build_message("tx", payload)
        for peer_key, writer in list(self._writers.items()):
            peer = self._peers.get(peer_key)
            if peer and peer.handshake_done and tx_hash not in peer.known_inv:
                try:
                    writer.write(msg)
                    await writer.drain()
                    peer.known_inv.add(tx_hash)
                except Exception as e:
                    logger.debug(f"Broadcast tx to {peer_key} failed: {e}")

    def peer_count(self) -> int:
        return len([p for p in self._peers.values() if p.handshake_done])

    def peer_list(self) -> List[dict]:
        return [
            {
                "address": f"{p.address}:{p.port}",
                "version": p.version,
                "height": p.height,
                "user_agent": p.user_agent,
                "handshake_done": p.handshake_done,
                "connected_duration_sec": int(time.time() - p.connected_at),
            }
            for p in self._peers.values()
        ]

    def network_info(self) -> dict:
        return {
            "listening": f"{self.host}:{self.port}",
            "connected_peers": self.peer_count(),
            "known_blocks": len(self._known_blocks),
            "known_txs": len(self._known_txs),
            "max_peers": MAX_PEERS,
            "protocol_version": PROTOCOL_VERSION,
            "user_agent": USER_AGENT,
        }
