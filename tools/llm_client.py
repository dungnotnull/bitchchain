"""
llm_client.py — Unified LLM client for Bitchchain agent.

Provider priority: Claude (claude-opus-4-8) → OpenAI (gpt-4o) → Ollama (llama3)
Use cases:
  - Multi-paper blockchain research synthesis
  - Protocol trade-off analysis
  - Security vulnerability review
  - General blockchain Q&A
"""

import json
import logging
import os
import time
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_CLAUDE_MODEL = "claude-opus-4-8"
DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_OLLAMA_MODEL = "llama3"
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0


class LLMClient:
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self._anthropic_key = os.getenv("ANTHROPIC_API_KEY", self.config.get("anthropic_api_key", ""))
        self._openai_key = os.getenv("OPENAI_API_KEY", self.config.get("openai_api_key", ""))
        self._ollama_url = os.getenv("OLLAMA_BASE_URL", self.config.get("ollama_base_url", "http://localhost:11434"))
        self._claude_model = self.config.get("claude_model", DEFAULT_CLAUDE_MODEL)
        self._openai_model = self.config.get("openai_model", DEFAULT_OPENAI_MODEL)
        self._ollama_model = self.config.get("ollama_model", DEFAULT_OLLAMA_MODEL)

    def ask(self, prompt: str, system: Optional[str] = None,
            max_tokens: int = 4096) -> str:
        """Single-turn LLM query with automatic provider fallback."""
        for provider in ["claude", "openai", "ollama"]:
            try:
                return self._call_provider(provider, prompt, system, max_tokens)
            except Exception as e:
                logger.warning(f"Provider {provider} failed: {e}")
        return "All LLM providers unavailable. Falling back to SECOND-KNOWLEDGE-BRAIN.md."

    def ask_json(self, prompt: str, system: Optional[str] = None,
                 max_tokens: int = 4096) -> dict:
        """Query expecting JSON response."""
        response = self.ask(prompt + "\n\nRespond with valid JSON only.", system, max_tokens)
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except Exception:
            pass
        return {"raw_response": response}

    def synthesize_blockchain_papers(self, papers: List[dict]) -> dict:
        """Multi-paper synthesis → actionable protocol recommendations."""
        summaries = "\n\n".join([
            f"Paper {i+1}: {p.get('title', 'Unknown')}\n"
            f"Authors: {p.get('authors', '')}\n"
            f"Key finding: {p.get('abstract', '')[:500]}"
            for i, p in enumerate(papers[:10])
        ])
        prompt = f"""You are a blockchain protocol researcher reviewing recent academic papers
for applicability to Bitchchain: a Bitcoin-forked blockchain targeting:
1. Throughput ≥ 70 TPS (via 4 MB blocks + parallel UTXO validation)
2. Energy ≤ 50% of Bitcoin PoW (via hybrid PoW/PoS with 2/3 stake finality)
3. Privacy: optional Confidential Transactions (Pedersen commitments + range proofs)

Here are recent paper summaries:
{summaries}

Analyze for applicability and return JSON:
{{
  "applicable_findings": [
    {{"paper_title": "...", "finding": "...", "target": "tps|energy|privacy|security", "priority": "high|medium|low"}}
  ],
  "recommended_parameter_changes": [
    {{"parameter": "...", "current": "...", "recommended": "...", "rationale": "..."}}
  ],
  "risk_analysis": [
    {{"risk": "...", "severity": "critical|high|medium|low", "mitigation": "..."}}
  ],
  "priority_action": "..."
}}"""
        return self.ask_json(prompt)

    def analyze_protocol_change(self, change_description: str) -> str:
        """Analyze a proposed protocol change for security and feasibility."""
        prompt = f"""Analyze this proposed Bitchchain protocol change:

{change_description}

Consider:
- Security: selfish mining (>25% hash rate), nothing-at-stake (PoS), long-range attacks, eclipse attacks
- Throughput: impact on TPS target (≥ 70 TPS)
- Energy: impact on energy target (≤ 50% of Bitcoin PoW)
- Privacy: impact on Confidential Transaction completeness
- Lightning Network compatibility: does this break HTLC-compatible scripts?

Provide: risk assessment, recommendation (approve/reject/modify), and specific concerns."""
        return self.ask(prompt)

    def explain_cryptographic_concept(self, concept: str) -> str:
        """Plain-language explanation of blockchain cryptography."""
        return self.ask(
            f"Explain '{concept}' in the context of blockchain cryptography. "
            "Be precise but accessible to a blockchain developer (not a cryptographer). "
            "Include: what it does, why it's used, known limitations."
        )

    def _call_provider(self, provider: str, prompt: str,
                       system: Optional[str], max_tokens: int) -> str:
        for attempt in range(MAX_RETRIES):
            try:
                if provider == "claude":
                    return self._call_claude(prompt, system, max_tokens)
                elif provider == "openai":
                    return self._call_openai(prompt, system, max_tokens)
                elif provider == "ollama":
                    return self._call_ollama(prompt, system, max_tokens)
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
                else:
                    raise

    def _call_claude(self, prompt: str, system: Optional[str], max_tokens: int) -> str:
        if not self._anthropic_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        import anthropic
        client = anthropic.Anthropic(api_key=self._anthropic_key)
        kwargs: Dict[str, Any] = {
            "model": self._claude_model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        response = client.messages.create(**kwargs)
        return response.content[0].text

    def _call_openai(self, prompt: str, system: Optional[str], max_tokens: int) -> str:
        if not self._openai_key:
            raise ValueError("OPENAI_API_KEY not set")
        import openai
        client = openai.OpenAI(api_key=self._openai_key)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(
            model=self._openai_model,
            messages=messages,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    def _call_ollama(self, prompt: str, system: Optional[str], max_tokens: int) -> str:
        import urllib.request
        payload = json.dumps({
            "model": self._ollama_model,
            "prompt": (f"System: {system}\n\n" if system else "") + prompt,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }).encode()
        req = urllib.request.Request(
            f"{self._ollama_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data.get("response", "")

    def stream(self, prompt: str, system: Optional[str] = None) -> Generator[str, None, None]:
        """Streaming output (Claude only)."""
        if not self._anthropic_key:
            yield self.ask(prompt, system)
            return
        import anthropic
        client = anthropic.Anthropic(api_key=self._anthropic_key)
        kwargs: Dict[str, Any] = {
            "model": self._claude_model,
            "max_tokens": 8192,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        with client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield text

    def provider_status(self) -> dict:
        return {
            "claude": "configured" if self._anthropic_key else "missing ANTHROPIC_API_KEY",
            "openai": "configured" if self._openai_key else "missing OPENAI_API_KEY",
            "ollama": f"url={self._ollama_url}",
            "active_models": {
                "claude": self._claude_model,
                "openai": self._openai_model,
                "ollama": self._ollama_model,
            },
        }

    def evaluate_prompts(self) -> dict:
        """
        Evaluate LLM answer quality on 10 known blockchain protocol questions.

        Each question has expected key terms that a correct answer should contain.
        Scoring: 1 point per question where the answer contains at least one expected term.
        Returns per-question results and aggregate score.
        """
        eval_set = [
            {
                "question": "What is the maximum block size in Bitcoin and how does Bitchchain improve on it?",
                "expected_terms": ["1 MB", "4 MB", "segwit", "throughput"],
            },
            {
                "question": "Explain how Pedersen commitments enable Confidential Transactions.",
                "expected_terms": ["r*G", "v*H", "blinding", "elliptic curve", "commitment"],
            },
            {
                "question": "What is the 2/3 finality threshold in Casper FFG?",
                "expected_terms": ["2/3", "supermajority", "stake", "finalize"],
            },
            {
                "question": "How does SHA-256d differ from SHA-256 and why does Bitcoin use it?",
                "expected_terms": ["double", "two", "collision", "length extension"],
            },
            {
                "question": "What is the UTXO model and how does it differ from the account model?",
                "expected_terms": ["unspent", "transaction output", "balance", "account"],
            },
            {
                "question": "Explain the nothing-at-stake problem in Proof-of-Stake systems.",
                "expected_terms": ["fork", "vote", "penalty", "slashing"],
            },
            {
                "question": "What is a Merkle tree and how is it used in block headers?",
                "expected_terms": ["hash", "root", "binary tree", "verification"],
            },
            {
                "question": "How does Bitcoin's difficulty adjustment algorithm work?",
                "expected_terms": ["2016", "target", "retarget", "timespan"],
            },
            {
                "question": "What are Bulletproofs and how do they improve on earlier range proofs?",
                "expected_terms": ["range proof", "logarithmic", "size", "confidential"],
            },
            {
                "question": "Explain the trade-offs between block size, decentralization, and throughput.",
                "expected_terms": ["block size", "bandwidth", "centralization", "verification"],
            },
        ]

        results = []
        total_score = 0
        for item in eval_set:
            answer = self.ask(
                f"You are a blockchain protocol expert. Answer concisely and accurately:\n\n{item['question']}"
            )
            answer_lower = answer.lower()
            matched = [t for t in item["expected_terms"] if t.lower() in answer_lower]
            score = 1 if matched else 0
            total_score += score
            results.append({
                "question": item["question"],
                "matched_terms": matched,
                "expected_terms": item["expected_terms"],
                "score": score,
                "answer_preview": answer[:200],
            })

        return {
            "total_questions": len(eval_set),
            "total_score": total_score,
            "percentage": round(total_score / len(eval_set) * 100, 1),
            "per_question": results,
            "provider_used": "claude" if self._anthropic_key else (
                "openai" if self._openai_key else "ollama"
            ),
        }
