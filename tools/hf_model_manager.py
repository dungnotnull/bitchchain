"""
hf_model_manager.py — HuggingFace model manager for Bitchchain agent.

Models used:
  - BAAI/bge-large-en-v1.5     : Paper embedding + semantic search (MTEB #1)
  - facebook/bart-large-cnn    : Research paper abstractive summarization

Lazy loading: models downloaded on first use, cached in ./models/
GPU: CUDA if available, CPU fallback.
"""

import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

MODEL_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")

MODEL_REGISTRY = {
    "text_embedding": {
        "model_id": "BAAI/bge-large-en-v1.5",
        "task": "feature-extraction",
        "description": "Dense vector embeddings for semantic search over research papers (MTEB #1 2024)",
    },
    "summarization": {
        "model_id": "facebook/bart-large-cnn",
        "task": "summarization",
        "description": "Abstractive summarization of long ArXiv papers (ROUGE-L 44.16)",
    },
}


class HFModelManager:
    def __init__(self, cache_dir: str = MODEL_CACHE_DIR):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self._loaded: Dict[str, any] = {}
        self._device = self._get_device()

    def _get_device(self) -> str:
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    def _load_model(self, name: str):
        if name in self._loaded:
            return self._loaded[name]
        if name not in MODEL_REGISTRY:
            raise ValueError(f"Unknown model '{name}'. Available: {list(MODEL_REGISTRY)}")

        info = MODEL_REGISTRY[name]
        model_id = info["model_id"]
        logger.info(f"Loading {model_id} (device={self._device})")

        try:
            from transformers import pipeline
            pipe = pipeline(
                info["task"],
                model=model_id,
                device=0 if self._device == "cuda" else -1,
                model_kwargs={"cache_dir": self.cache_dir},
            )
            self._loaded[name] = pipe
            logger.info(f"Loaded {model_id}")
            return pipe
        except Exception as e:
            logger.error(f"Failed to load {model_id}: {e}")
            raise

    # ─── Embedding ────────────────────────────────────────────────────────────

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Compute BGE embeddings for a list of texts."""
        pipe = self._load_model("text_embedding")
        results = pipe(texts, batch_size=8)
        # BGE pipeline returns token embeddings; take mean of last hidden state
        embeddings = []
        for result in results:
            if isinstance(result, list):
                vec = result[0] if result else []
                if isinstance(vec, list) and vec and isinstance(vec[0], list):
                    mean_vec = [sum(row[i] for row in vec) / len(vec) for i in range(len(vec[0]))]
                    embeddings.append(mean_vec)
                else:
                    embeddings.append(vec)
            else:
                embeddings.append(result)
        return embeddings

    def embed_single(self, text: str) -> List[float]:
        return self.embed([text])[0]

    def semantic_search(self, query: str, corpus: List[dict],
                         text_key: str = "abstract", top_k: int = 5) -> List[dict]:
        """Find the most semantically similar items in corpus to query."""
        if not corpus:
            return []
        texts = [item.get(text_key, item.get("title", "")) for item in corpus]
        all_texts = [query] + texts
        embeddings = self.embed(all_texts)
        query_emb = embeddings[0]
        corpus_embs = embeddings[1:]

        def cosine_sim(a: List[float], b: List[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = sum(x ** 2 for x in a) ** 0.5
            norm_b = sum(x ** 2 for x in b) ** 0.5
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)

        scored = [(cosine_sim(query_emb, emb), item)
                  for emb, item in zip(corpus_embs, corpus)]
        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, item in scored[:top_k]:
            results.append({**item, "similarity_score": round(score, 4)})
        return results

    # ─── Summarization ────────────────────────────────────────────────────────

    def summarize(self, text: str, max_length: int = 200, min_length: int = 50) -> str:
        """Abstractive summarization of research paper text."""
        pipe = self._load_model("summarization")
        # BART max input is 1024 tokens; truncate long texts
        truncated = text[:3000]
        try:
            result = pipe(
                truncated,
                max_length=max_length,
                min_length=min_length,
                do_sample=False,
            )
            return result[0]["summary_text"]
        except Exception as e:
            logger.warning(f"Summarization failed: {e}")
            return text[:max_length]

    def summarize_papers(self, papers: List[dict]) -> List[dict]:
        """Batch summarize a list of paper dicts (adds 'summary' key)."""
        for paper in papers:
            text = paper.get("abstract", paper.get("title", ""))
            if len(text) > 100:
                paper["summary"] = self.summarize(text)
            else:
                paper["summary"] = text
        return papers

    # ─── Status ───────────────────────────────────────────────────────────────

    def status(self) -> dict:
        return {
            "device": self._device,
            "cache_dir": self.cache_dir,
            "loaded_models": list(self._loaded.keys()),
            "available_models": {k: v["model_id"] for k, v in MODEL_REGISTRY.items()},
        }

    def unload(self, name: str):
        if name in self._loaded:
            del self._loaded[name]
            try:
                import gc
                gc.collect()
                if self._device == "cuda":
                    import torch
                    torch.cuda.empty_cache()
            except Exception:
                pass

    def unload_all(self):
        for name in list(self._loaded.keys()):
            self.unload(name)

    def benchmark_embedding(self, num_papers: int = 50, text_length: int = 200) -> dict:
        """
        Benchmark embedding throughput on the current device.

        Generates synthetic paper abstracts and measures how many papers
        can be embedded per second. Reports both wall-clock time and
        papers-per-second throughput.

        Returns a dict with: device, num_papers, total_seconds, papers_per_second.
        """
        import time as _time

        sample_abstracts = [
            f"This paper presents a novel approach to blockchain consensus mechanism "
            f"design using {text_length}-character analysis of Byzantine fault tolerance "
            f"in distributed ledger systems with proof-of-stake validation. "
            f"Paper variant {i} explores the trade-offs between decentralization and throughput."
            for i in range(num_papers)
        ]

        logger.info(f"Benchmarking embedding throughput: {num_papers} papers on {self._device}")
        start = _time.perf_counter()
        embeddings = self.embed(sample_abstracts)
        elapsed = _time.perf_counter() - start

        throughput = num_papers / elapsed if elapsed > 0 else 0
        result = {
            "device": self._device,
            "num_papers": num_papers,
            "total_seconds": round(elapsed, 3),
            "papers_per_second": round(throughput, 2),
            "embedding_dim": len(embeddings[0]) if embeddings else 0,
            "target_met": throughput >= (50 / 60),
        }
        logger.info(
            f"Embedding benchmark: {num_papers} papers in {elapsed:.2f}s "
            f"= {throughput:.1f} papers/s on {self._device}"
        )
        return result
