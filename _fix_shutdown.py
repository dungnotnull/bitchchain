import os
path = r'D:\bitchchain-agent\agent\orchestrator.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = """    async def stop_node(self):
        await self.rpc_server.stop()
        await self.network.stop()
        self._node_running = False
        self.memory.log_event("node_stopped")
        logger.info("Bitchchain node stopped.")"""

new = """    async def stop_node(self):
        \"\"\"Gracefully shut down the node, stopping RPC server and P2P network.\"\"\"
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
        logger.info("Bitchchain node stopped gracefully.")"""

content = content.replace(old, new)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print(f'Added graceful shutdown to orchestrator: {os.path.getsize(path)} bytes')
