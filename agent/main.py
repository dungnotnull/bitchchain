"""
main.py — Bitchchain CLI entry point.

Usage:
    python -m agent.main start-node [--regtest]
    python -m agent.main mine [--regtest] [--count N]
    python -m agent.main send-tx --to ADDRESS --amount SATS --from-txid TXID --from-vout N
    python -m agent.main send-ct --to SCRIPT --amount SATS --fee SATS --from-txid TXID --from-vout N
    python -m agent.main stake --address ADDR --amount SATS --stake-txid TXID
    python -m agent.main vote --validator ADDR --source HASH --target HASH
    python -m agent.main research-sync
    python -m agent.main ask "Your blockchain question here"
    python -m agent.main status
"""

import argparse
import asyncio
import json
import logging
import os
import sys

import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("bitchchain")


def load_config(config_path: str = "config/agent_config.yaml") -> dict:
    if os.path.exists(config_path):
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    return {}


def print_json(data: dict):
    print(json.dumps(data, indent=2, default=str))


async def cmd_start_node(orchestrator, args):
    print("Starting Bitchchain node... (Ctrl+C to stop)")
    await orchestrator.start_node()
    status = orchestrator.status()
    print_json(status)
    try:
        while True:
            await asyncio.sleep(10)
            tip = orchestrator.chain.get_tip()
            peers = orchestrator.network.peer_count()
            print(f"  Height: {tip[1]} | Peers: {peers} | Mempool: {orchestrator.memory.mempool_size()}")
    except KeyboardInterrupt:
        print("\nShutting down...")
        await orchestrator.stop_node()


def cmd_mine(orchestrator, args):
    regtest = args.regtest
    count = getattr(args, "count", 1)
    results = []
    for i in range(count):
        result = orchestrator.mine_block(regtest=regtest)
        results.append(result)
        if result["success"]:
            print(f"Block {i+1}/{count}: {result['block_hash'][:16]}... height={result['height']}")
        else:
            print(f"Block {i+1}/{count}: FAILED — {result.get('error')}")
            break
    print_json({"mined": len([r for r in results if r["success"]]), "results": results})


def cmd_send_tx(orchestrator, args):
    result = orchestrator.send_transaction(
        to_address=args.to,
        amount_satoshis=args.amount,
        from_txid=args.from_txid,
        from_vout=args.from_vout,
    )
    print_json(result)


def cmd_send_ct(orchestrator, args):
    result = orchestrator.send_ct_transaction(
        sender_address=getattr(args, "sender", "unknown"),
        to_script=args.to,
        amount_satoshis=args.amount,
        fee_satoshis=args.fee,
        input_txid=args.from_txid,
        input_vout=args.from_vout,
        input_blinding=getattr(args, "input_blinding", 0),
    )
    print_json(result)


def cmd_stake(orchestrator, args):
    result = orchestrator.register_validator(
        address=args.address,
        stake_satoshis=args.amount,
        stake_txid=args.stake_txid,
    )
    print_json(result)


def cmd_vote(orchestrator, args):
    result = orchestrator.submit_finality_vote(
        validator_address=args.validator,
        source_checkpoint=args.source,
        target_checkpoint=args.target,
    )
    print_json(result)


def cmd_research_sync(orchestrator, args):
    print("Running research sync (ArXiv cs.CR + cs.DC + Semantic Scholar)...")
    result = orchestrator.run_research_sync()
    print_json(result)


def cmd_ask(orchestrator, args):
    question = " ".join(args.question)
    print(f"Querying LLM: {question}\n")
    answer = orchestrator.ask_llm(question)
    print(answer)


def cmd_status(orchestrator, args):
    print_json(orchestrator.status())


async def cmd_rpc_test(orchestrator, args):
    import urllib.request
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": args.method,
        "params": args.params,
        "id": 1,
    }).encode()
    url = f"http://{args.host}:{args.port}/rpc"
    req = urllib.request.Request(url, data=payload,
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
        print_json(result)
    except Exception as e:
        print(f"RPC call failed: {e}")
        print("Ensure the node is running: python -m agent.main start-node")


def cmd_benchmark(orchestrator, args):
    from agent.benchmark import BenchmarkRunner
    runner = BenchmarkRunner(orchestrator)
    results = {}

    if args.run_all or args.tps:
        results["tps"] = runner.run_tps_benchmark()
        print(f"TPS Benchmark: {results['tps']['measured_tps']:.1f} TPS (target: >= 70)")
    if args.run_all or args.energy:
        results["energy"] = runner.run_energy_benchmark()
        print(f"Energy Benchmark: {results['energy']['reduction_pct']:.1f}% reduction (target: >= 50%)")
    if args.run_all or args.privacy:
        results["privacy"] = runner.run_privacy_benchmark()
        print(f"Privacy Benchmark: {'PASS' if results['privacy']['passed'] else 'FAIL'}")

    if args.publish and results:
        runner.publish_results(results)
        print("Benchmark results published to SECOND-KNOWLEDGE-BRAIN.md")

    print_json(results)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bitchchain",
        description="Bitchchain — Bitcoin-forked blockchain with hybrid PoW/PoS and CT privacy"
    )
    parser.add_argument("--config", default="config/agent_config.yaml",
                        help="Path to agent_config.yaml")
    sub = parser.add_subparsers(dest="command")

    # start-node
    p_node = sub.add_parser("start-node", help="Start the full P2P node")
    p_node.add_argument("--regtest", action="store_true",
                        help="Run in regtest mode (instant mining)")

    # mine
    p_mine = sub.add_parser("mine", help="Mine a new block")
    p_mine.add_argument("--regtest", action="store_true")
    p_mine.add_argument("--count", type=int, default=1, help="Number of blocks to mine")

    # send-tx
    p_tx = sub.add_parser("send-tx", help="Send a transparent transaction")
    p_tx.add_argument("--to", required=True, help="Recipient address")
    p_tx.add_argument("--amount", type=int, required=True, help="Amount in satoshis")
    p_tx.add_argument("--from-txid", required=True, dest="from_txid")
    p_tx.add_argument("--from-vout", type=int, required=True, dest="from_vout")

    # send-ct
    p_ct = sub.add_parser("send-ct", help="Send a Confidential Transaction")
    p_ct.add_argument("--to", required=True, help="Recipient script_pubkey (hex)")
    p_ct.add_argument("--amount", type=int, required=True, help="Amount in satoshis")
    p_ct.add_argument("--fee", type=int, default=1000)
    p_ct.add_argument("--from-txid", required=True, dest="from_txid")
    p_ct.add_argument("--from-vout", type=int, required=True, dest="from_vout")
    p_ct.add_argument("--sender", default="unknown")
    p_ct.add_argument("--input-blinding", type=int, default=0, dest="input_blinding")

    # stake
    p_stake = sub.add_parser("stake", help="Register as PoS validator")
    p_stake.add_argument("--address", required=True)
    p_stake.add_argument("--amount", type=int, required=True, help="Stake amount in satoshis")
    p_stake.add_argument("--stake-txid", required=True, dest="stake_txid")

    # vote
    p_vote = sub.add_parser("vote", help="Submit a finality vote")
    p_vote.add_argument("--validator", required=True)
    p_vote.add_argument("--source", required=True, help="Source checkpoint block hash")
    p_vote.add_argument("--target", required=True, help="Target checkpoint block hash")

    # research-sync
    sub.add_parser("research-sync", help="Sync research papers to SECOND-KNOWLEDGE-BRAIN.md")

    # ask
    p_ask = sub.add_parser("ask", help="Ask LLM a blockchain protocol question")
    p_ask.add_argument("question", nargs="+")

    # status
    sub.add_parser("status", help="Show node status")

    # rpc-test
    p_rpc = sub.add_parser("rpc-test", help="Test JSON-RPC server")
    p_rpc.add_argument("--method", default="getblockchaininfo", help="RPC method to call")
    p_rpc.add_argument("--params", nargs="*", default=[], help="RPC params")
    p_rpc.add_argument("--host", default="127.0.0.1", help="RPC host")
    p_rpc.add_argument("--port", type=int, default=8332, help="RPC port")

    # benchmark
    p_bench = sub.add_parser("benchmark", help="Run performance benchmarks")
    p_bench.add_argument("--tps", action="store_true", help="Run TPS benchmark")
    p_bench.add_argument("--energy", action="store_true", help="Run energy model benchmark")
    p_bench.add_argument("--privacy", action="store_true", help="Run CT privacy verification")
    p_bench.add_argument("--all", action="store_true", dest="run_all", help="Run all benchmarks")
    p_bench.add_argument("--publish", action="store_true", help="Publish results to SECOND-KNOWLEDGE-BRAIN.md")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    config = load_config(args.config)

    # Lazy import to keep startup fast
    from agent.orchestrator import BitchchainOrchestrator
    orchestrator = BitchchainOrchestrator(config)

    command_map = {
        "mine": cmd_mine,
        "send-tx": cmd_send_tx,
        "send-ct": cmd_send_ct,
        "stake": cmd_stake,
        "vote": cmd_vote,
        "research-sync": cmd_research_sync,
        "ask": cmd_ask,
        "status": cmd_status,
    }

    if args.command == "start-node":
        asyncio.run(cmd_start_node(orchestrator, args))
    elif args.command == "rpc-test":
        asyncio.run(cmd_rpc_test(orchestrator, args))
    elif args.command == "benchmark":
        cmd_benchmark(orchestrator, args)
    elif args.command in command_map:
        command_map[args.command](orchestrator, args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
