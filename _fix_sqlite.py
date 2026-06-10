import os

# Fix memory_manager.py
path = r'D:\bitchchain-agent\agent\memory\memory_manager.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = "self._conn = sqlite3.connect(db_path, check_same_thread=False)\n        self._init_schema()"
new = 'self._conn = sqlite3.connect(db_path, check_same_thread=False)\n        self._conn.execute("PRAGMA journal_mode=WAL")\n        self._conn.execute("PRAGMA synchronous=NORMAL")\n        self._init_schema()'
content = content.replace(old, new)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print(f'Fixed memory_manager.py with WAL mode')

# Fix blockchain_core.py - there are multiple SQLite connections
path = r'D:\bitchchain-agent\agent\modules\blockchain_core.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add WAL to Blockchain.__init__
content = content.replace(
    'self._conn = sqlite3.connect(db_path, check_same_thread=False)\n        self.utxo_set = UTXOSet(db_path)\n        self._init_schema()',
    'self._conn = sqlite3.connect(db_path, check_same_thread=False)\n        self._conn.execute("PRAGMA journal_mode=WAL")\n        self._conn.execute("PRAGMA synchronous=NORMAL")\n        self.utxo_set = UTXOSet(db_path)\n        self._init_schema()'
)

# Add WAL to UTXOSet.__init__
content = content.replace(
    'self._conn = sqlite3.connect(db_path, check_same_thread=False)\n        self._init_schema()\n\n    def _init_schema(self):\n        self._conn.execute("""\n            CREATE TABLE IF NOT EXISTS utxos',
    'self._conn = sqlite3.connect(db_path, check_same_thread=False)\n        self._conn.execute("PRAGMA journal_mode=WAL")\n        self._conn.execute("PRAGMA synchronous=NORMAL")\n        self._init_schema()\n\n    def _init_schema(self):\n        self._conn.execute("""\n            CREATE TABLE IF NOT EXISTS utxos'
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed blockchain_core.py with WAL mode')
