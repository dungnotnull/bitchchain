"""
rpc_server.py -- JSON-RPC 2.0 server for Bitchchain.

Provides programmatic access to the blockchain node on port 8332.
Methods follow Bitcoin Core's RPC API conventions where applicable.

Protocol: JSON-RPC 2.0 (https://www.jsonrpc.org/specification)
Transport: HTTP POST on /rpc
Authentication: Basic auth (username:password from config)
"""

import asyncio
import json
import logging
import base64
from typing import Any, Callable, Dict, List, Optional

from aiohttp import web

logger = logging.getLogger(__name__)

JSONRPC_VERSION = "2.0"
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
SERVER_ERROR_START = -32000


class JSONRPCError(Exception):
    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)

    def to_dict(self) -> dict:
        d = {"code": self.code, "message": self.message}
        if self.data is not None:
            d["data"] = self.data
        return d


class JSONRPCServer:
    """
    Async JSON-RPC 2.0 server using aiohttp.

    Registers handler methods and dispatches incoming RPC calls.
    Supports batch requests and proper error handling per the spec.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8332,
                 rpc_user: str = "", rpc_password: str = ""):
        self.host = host
        self.port = port
        self.rpc_user = rpc_user
        self.rpc_password = rpc_password
        self._methods: Dict[str, Callable] = {}
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._register_core_methods()

    def register_method(self, name: str, handler: Callable):
        self._methods[name] = handler

    def _register_core_methods(self):
        self.register_method("getblockcount", self._not_implemented_stub)
        self.register_method("getbestblockhash", self._not_implemented_stub)
        self.register_method("getmempoolsize", self._not_implemented_stub)
        self.register_method("getpeercount", self._not_implemented_stub)
        self.register_method("getblock", self._not_implemented_stub)
        self.register_method("getrawtransaction", self._not_implemented_stub)
        self.register_method("sendrawtransaction", self._not_implemented_stub)
        self.register_method("startmining", self._not_implemented_stub)
        self.register_method("stopmining", self._not_implemented_stub)
        self.register_method("getconsensusstatus", self._not_implemented_stub)
        self.register_method("getnetworkinfo", self._not_implemented_stub)
        self.register_method("getblockchaininfo", self._not_implemented_stub)
        self.register_method("help", self._help)

    async def _not_implemented_stub(self, *args, **kwargs) -> Any:
        raise JSONRPCError(SERVER_ERROR_START, "Method not wired to orchestrator")

    async def _help(self, *args, **kwargs) -> str:
        methods = sorted(self._methods.keys())
        return "Available RPC methods:\n" + "\n".join(f"  {m}" for m in methods)

    def wire_orchestrator(self, orchestrator):
        """
        Wire all RPC methods to the live orchestrator instance.
        This replaces the stub handlers with real implementations.
        """
        chain = orchestrator.chain
        consensus = orchestrator.consensus
        network = orchestrator.network
        memory = orchestrator.memory
        ct_engine = orchestrator.ct_engine

        async def getblockcount(params: list) -> int:
            _, height = chain.get_tip()
            return height

        async def getbestblockhash(params: list) -> str:
            tip_hash, _ = chain.get_tip()
            return tip_hash or ""

        async def getmempoolsize(params: list) -> int:
            return memory.mempool_size()

        async def getpeercount(params: list) -> int:
            return network.peer_count()

        async def getblock(params: list) -> dict:
            if not params:
                raise JSONRPCError(INVALID_PARAMS, "Usage: getblock <block_hash> [verbosity]")
            block_hash = params[0]
            if not isinstance(block_hash, str) or len(block_hash) != 64:
                raise JSONRPCError(INVALID_PARAMS, "block_hash must be a 64-character hex string")
            try:
                int(block_hash, 16)
            except ValueError:
                raise JSONRPCError(INVALID_PARAMS, "block_hash must be valid hexadecimal")
            block = chain.get_block(block_hash)
            if block is None:
                raise JSONRPCError(SERVER_ERROR_START, f"Block not found: {block_hash}")
            verbosity = params[1] if len(params) > 1 else 1
            if verbosity == 0:
                return block.block_hash
            return block.to_dict()

        async def getrawtransaction(params: list) -> dict:
            if not params:
                raise JSONRPCError(INVALID_PARAMS, "Usage: getrawtransaction <txid>")
            txid = params[0]
            if not isinstance(txid, str) or len(txid) != 64:
                raise JSONRPCError(INVALID_PARAMS, "txid must be a 64-character hex string")
            try:
                int(txid, 16)
            except ValueError:
                raise JSONRPCError(INVALID_PARAMS, "txid must be valid hexadecimal")
            mempool_txs = memory.get_mempool()
            for tx in mempool_txs:
                if tx.get("txid") == txid:
                    return tx
            raise JSONRPCError(SERVER_ERROR_START, f"Transaction not found: {txid}")

        async def sendrawtransaction(params: list) -> str:
            if not params:
                raise JSONRPCError(INVALID_PARAMS, "Usage: sendrawtransaction <tx_hex_or_json>")
            tx_data = params[0]
            if isinstance(tx_data, str):
                try:
                    tx_data = json.loads(tx_data)
                except json.JSONDecodeError:
                    raise JSONRPCError(INVALID_PARAMS, "Invalid transaction JSON")
            if not isinstance(tx_data, dict):
                raise JSONRPCError(INVALID_PARAMS, "Transaction must be a JSON object")
            txid = tx_data.get("txid", "")
            if not txid or not isinstance(txid, str) or len(txid) != 64:
                raise JSONRPCError(INVALID_PARAMS, "Transaction must have a valid 64-char hex txid")
            memory.add_to_mempool(txid, tx_data)
            return txid

        async def startmining(params: list) -> str:
            regtest = bool(params and params[0] in (True, "true", 1, "regtest"))
            result = orchestrator.mine_block(regtest=regtest)
            if result.get("success"):
                return f"Block mined: {result['block_hash']}"
            return f"Mining failed: {result.get('error', 'unknown')}"

        async def stopmining(params: list) -> str:
            return "Mining stopped (single-shot miner, no background thread to stop)"

        async def getconsensusstatus(params: list) -> dict:
            return consensus.consensus_status()

        async def getnetworkinfo(params: list) -> dict:
            return network.network_info()

        async def getblockchaininfo(params: list) -> dict:
            info = chain.chain_info()
            _, height = chain.get_tip()
            info["difficulty"] = chain.get_next_bits()
            info["consensus"] = consensus.consensus_status()
            info["mempool_size"] = memory.mempool_size()
            info["peers"] = network.peer_count()
            return info

        self.register_method("getblockcount", getblockcount)
        self.register_method("getbestblockhash", getbestblockhash)
        self.register_method("getmempoolsize", getmempoolsize)
        self.register_method("getpeercount", getpeercount)
        self.register_method("getblock", getblock)
        self.register_method("getrawtransaction", getrawtransaction)
        self.register_method("sendrawtransaction", sendrawtransaction)
        self.register_method("startmining", startmining)
        self.register_method("stopmining", stopmining)
        self.register_method("getconsensusstatus", getconsensusstatus)
        self.register_method("getnetworkinfo", getnetworkinfo)
        self.register_method("getblockchaininfo", getblockchaininfo)

        logger.info(f"RPC server wired: {len(self._methods)} methods registered")

    async def start(self):
        self._app = web.Application()
        self._app.router.add_post("/rpc", self._handle_rpc)
        self._app.router.add_post("/", self._handle_rpc)
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        logger.info(f"JSON-RPC server listening on {self.host}:{self.port}")

    async def stop(self):
        if self._runner:
            await self._runner.cleanup()
            logger.info("JSON-RPC server stopped")

    async def _handle_rpc(self, request: web.Request) -> web.Response:
        if self.rpc_user and self.rpc_password:
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Basic "):
                return self._json_response(self._error_response(
                    None, INVALID_REQUEST, "Authentication required"
                ))
            try:
                decoded = base64.b64decode(auth[6:]).decode("utf-8")
                user, password = decoded.split(":", 1)
                if user != self.rpc_user or password != self.rpc_password:
                    return self._json_response(self._error_response(
                        None, INVALID_REQUEST, "Invalid credentials"
                    ))
            except Exception:
                return self._json_response(self._error_response(
                    None, INVALID_REQUEST, "Invalid authentication header"
                ))

        try:
            body = await request.text()
            parsed = json.loads(body)
        except json.JSONDecodeError:
            return self._json_response(self._error_response(
                None, PARSE_ERROR, "Parse error"
            ))

        if isinstance(parsed, list):
            results = []
            for req in parsed:
                results.append(await self._dispatch(req))
            return self._json_response(results)

        result = await self._dispatch(parsed)
        return self._json_response(result)

    async def _dispatch(self, request: dict) -> dict:
        request_id = request.get("id")

        if not isinstance(request, dict):
            return self._error_response(request_id, INVALID_REQUEST, "Invalid request")

        jsonrpc = request.get("jsonrpc")
        method_name = request.get("method")
        params = request.get("params", [])

        if jsonrpc != JSONRPC_VERSION or not method_name:
            return self._error_response(request_id, INVALID_REQUEST, "Invalid JSON-RPC request")

        handler = self._methods.get(method_name)
        if handler is None:
            return self._error_response(request_id, METHOD_NOT_FOUND, f"Method not found: {method_name}")

        try:
            if isinstance(params, list):
                result = await handler(params)
            elif isinstance(params, dict):
                result = await handler(**params)
            else:
                result = await handler()

            return {
                "jsonrpc": JSONRPC_VERSION,
                "result": result,
                "id": request_id,
            }
        except JSONRPCError as e:
            return self._error_response(request_id, e.code, e.message, e.data)
        except Exception as e:
            logger.error(f"RPC method {method_name} failed: {e}")
            return self._error_response(request_id, INTERNAL_ERROR, str(e))

    def _error_response(self, request_id: Optional[Any], code: int,
                         message: str, data: Any = None) -> dict:
        error = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return {
            "jsonrpc": JSONRPC_VERSION,
            "error": error,
            "id": request_id,
        }

    def _json_response(self, data: Any) -> web.Response:
        return web.Response(
            text=json.dumps(data, default=str),
            content_type="application/json",
        )

    def status(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "methods": sorted(self._methods.keys()),
            "auth_enabled": bool(self.rpc_user),
        }
