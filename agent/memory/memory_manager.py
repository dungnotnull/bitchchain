"""
memory_manager.py — Persistent memory for the Bitchchain agent.

Stores: chain tip, mempool, peer list, validator state, research notes, and session logs.
Backend: SQLite (embedded, no server required).
"""

import json
import sqlite3
import time
from typing import Any, Dict, List, Optional


class MemoryManager:
    def __init__(self, db_path: str = "agent_memory.db"):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()

    def _init_schema(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS kv_store (
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (namespace, key)
            );
            CREATE TABLE IF NOT EXISTS mempool (
                txid TEXT PRIMARY KEY,
                tx_json TEXT NOT NULL,
                added_at REAL NOT NULL,
                fee_satoshis INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS session_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event TEXT NOT NULL,
                data TEXT,
                timestamp REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS research_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT,
                relevance_score REAL NOT NULL DEFAULT 0.0,
                added_at TEXT NOT NULL
            );
        """)
        self._conn.commit()

    # --- Generic KV store ---

    def set(self, namespace: str, key: str, value: Any):
        self._conn.execute(
            "INSERT OR REPLACE INTO kv_store VALUES (?, ?, ?, ?)",
            (namespace, key, json.dumps(value), time.time())
        )
        self._conn.commit()

    def get(self, namespace: str, key: str, default: Any = None) -> Any:
        row = self._conn.execute(
            "SELECT value FROM kv_store WHERE namespace=? AND key=?", (namespace, key)
        ).fetchone()
        return json.loads(row[0]) if row else default

    def delete(self, namespace: str, key: str):
        self._conn.execute(
            "DELETE FROM kv_store WHERE namespace=? AND key=?", (namespace, key)
        )
        self._conn.commit()

    def get_namespace(self, namespace: str) -> Dict[str, Any]:
        rows = self._conn.execute(
            "SELECT key, value FROM kv_store WHERE namespace=?", (namespace,)
        ).fetchall()
        return {r[0]: json.loads(r[1]) for r in rows}

    # --- Chain state ---

    def save_chain_tip(self, tip_hash: str, height: int):
        self.set("chain", "tip_hash", tip_hash)
        self.set("chain", "height", height)
        self.set("chain", "tip_updated_at", time.time())

    def get_chain_tip(self) -> Dict[str, Any]:
        return {
            "tip_hash": self.get("chain", "tip_hash"),
            "height": self.get("chain", "height", -1),
            "tip_updated_at": self.get("chain", "tip_updated_at"),
        }

    # --- Mempool ---

    def add_to_mempool(self, txid: str, tx_dict: dict, fee_satoshis: int = 0):
        self._conn.execute(
            "INSERT OR REPLACE INTO mempool VALUES (?, ?, ?, ?)",
            (txid, json.dumps(tx_dict), time.time(), fee_satoshis)
        )
        self._conn.commit()

    def remove_from_mempool(self, txid: str):
        self._conn.execute("DELETE FROM mempool WHERE txid=?", (txid,))
        self._conn.commit()

    def get_mempool(self, limit: int = 1000) -> List[dict]:
        rows = self._conn.execute(
            "SELECT txid, tx_json, fee_satoshis FROM mempool ORDER BY fee_satoshis DESC LIMIT ?",
            (limit,)
        ).fetchall()
        result = []
        for row in rows:
            tx = json.loads(row[1])
            tx["txid"] = row[0]
            tx["fee_satoshis"] = row[2]
            result.append(tx)
        return result

    def mempool_size(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM mempool").fetchone()[0]

    def clear_mempool_txids(self, txids: List[str]):
        for txid in txids:
            self.remove_from_mempool(txid)

    # --- Peer list ---

    def save_peers(self, peers: List[dict]):
        self.set("network", "peers", peers)

    def get_peers(self) -> List[dict]:
        return self.get("network", "peers", [])

    # --- Validator registry cache ---

    def save_validator_summary(self, summary: dict):
        self.set("consensus", "validator_summary", summary)

    def get_validator_summary(self) -> dict:
        return self.get("consensus", "validator_summary", {})

    # --- Session log ---

    def log_event(self, event: str, data: Optional[dict] = None):
        self._conn.execute(
            "INSERT INTO session_log (event, data, timestamp) VALUES (?, ?, ?)",
            (event, json.dumps(data) if data else None, time.time())
        )
        self._conn.commit()

    def get_recent_events(self, limit: int = 50) -> List[dict]:
        rows = self._conn.execute(
            "SELECT event, data, timestamp FROM session_log ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [{"event": r[0], "data": json.loads(r[1]) if r[1] else None,
                 "timestamp": r[2]} for r in rows]

    # --- Research notes ---

    def save_research_note(self, source: str, title: str, summary: str,
                           relevance_score: float = 0.0):
        import datetime
        self._conn.execute(
            "INSERT INTO research_notes (source, title, summary, relevance_score, added_at) VALUES (?, ?, ?, ?, ?)",
            (source, title, summary, relevance_score,
             datetime.datetime.utcnow().isoformat())
        )
        self._conn.commit()

    def get_research_notes(self, limit: int = 20, min_score: float = 0.0) -> List[dict]:
        rows = self._conn.execute(
            "SELECT source, title, summary, relevance_score, added_at FROM research_notes "
            "WHERE relevance_score >= ? ORDER BY relevance_score DESC LIMIT ?",
            (min_score, limit)
        ).fetchall()
        return [{"source": r[0], "title": r[1], "summary": r[2],
                 "relevance_score": r[3], "added_at": r[4]} for r in rows]

    # --- Agent config cache ---

    def save_config(self, config: dict):
        self.set("agent", "config", config)

    def get_config(self) -> dict:
        return self.get("agent", "config", {})

    def status(self) -> dict:
        chain = self.get_chain_tip()
        return {
            "chain_height": chain.get("height", -1),
            "tip_hash": chain.get("tip_hash"),
            "mempool_size": self.mempool_size(),
            "peer_count": len(self.get_peers()),
            "research_notes": self._conn.execute(
                "SELECT COUNT(*) FROM research_notes"
            ).fetchone()[0],
            "session_events": self._conn.execute(
                "SELECT COUNT(*) FROM session_log"
            ).fetchone()[0],
        }
