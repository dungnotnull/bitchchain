"""
knowledge_updater.py — Research paper crawler for Bitchchain.

Pipeline:
  1. Fetch papers from ArXiv (cs.CR, cs.DC), Semantic Scholar, Papers with Code
  2. Score by recency (90-day window) × keyword relevance
  3. Deduplicate by DOI/URL hash
  4. Append top-10 scored entries to SECOND-KNOWLEDGE-BRAIN.md
  5. Schedule: weekly (Sunday 02:00 UTC) via APScheduler

Keywords: blockchain, consensus, proof-of-stake, confidential transactions,
          zero-knowledge, UTXO, throughput, finality, Pedersen, Bulletproof
"""

import hashlib
import json
import logging
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ARXIV_API = "https://export.arxiv.org/api/query"
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
PAPERS_WITH_CODE_API = "https://paperswithcode.com/api/v1/papers/"

BLOCKCHAIN_KEYWORDS = [
    "blockchain", "consensus", "proof-of-stake", "proof of stake",
    "confidential transactions", "zero-knowledge", "UTXO",
    "throughput", "finality", "Pedersen commitment", "Bulletproof",
    "byzantine fault", "distributed ledger", "smart contract",
    "lightning network", "layer 2", "rollup",
]

RECENCY_WINDOW_DAYS = 90
MAX_NEW_ENTRIES_PER_RUN = 10


class KnowledgeUpdater:
    def __init__(self, config: Optional[dict] = None, brain_path: str = "SECOND-KNOWLEDGE-BRAIN.md"):
        self.config = config or {}
        self.brain_path = brain_path
        self._seen_hashes = self._load_seen_hashes()

    def _load_seen_hashes(self) -> set:
        if not os.path.exists(self.brain_path):
            return set()
        seen = set()
        with open(self.brain_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Extract URLs/DOIs already in the knowledge brain
        urls = re.findall(r'https?://[^\s\)\"]+', content)
        for url in urls:
            seen.add(hashlib.sha256(url.strip().encode()).hexdigest()[:16])
        return seen

    def _is_seen(self, url: str) -> bool:
        h = hashlib.sha256(url.strip().encode()).hexdigest()[:16]
        return h in self._seen_hashes

    def _mark_seen(self, url: str):
        h = hashlib.sha256(url.strip().encode()).hexdigest()[:16]
        self._seen_hashes.add(h)

    def _score_paper(self, paper: dict) -> float:
        """Score = recency_score × relevance_score."""
        # Recency score
        pub_date_str = paper.get("published_date", "")
        recency = 0.0
        if pub_date_str:
            try:
                pub_date = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
                days_old = (datetime.now(timezone.utc) - pub_date).days
                if days_old <= RECENCY_WINDOW_DAYS:
                    recency = 1.0 - (days_old / RECENCY_WINDOW_DAYS)
            except Exception:
                recency = 0.3

        # Relevance score (keyword hit count)
        text = (paper.get("title", "") + " " + paper.get("abstract", "")).lower()
        hits = sum(1 for kw in BLOCKCHAIN_KEYWORDS if kw.lower() in text)
        relevance = min(hits / 3.0, 1.0)

        return 0.6 * recency + 0.4 * relevance

    def fetch_arxiv(self, categories: List[str], max_results: int = 25) -> List[dict]:
        papers = []
        for cat in categories:
            query = f"cat:{cat} AND (blockchain OR consensus OR zero-knowledge OR UTXO)"
            params = urllib.parse.urlencode({
                "search_query": query,
                "max_results": max_results,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            })
            url = f"{ARXIV_API}?{params}"
            try:
                with urllib.request.urlopen(url, timeout=30) as resp:
                    content = resp.read()
                root = ET.fromstring(content)
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall("atom:entry", ns):
                    title_el = entry.find("atom:title", ns)
                    abstract_el = entry.find("atom:summary", ns)
                    published_el = entry.find("atom:published", ns)
                    id_el = entry.find("atom:id", ns)
                    authors = [a.find("atom:name", ns).text
                               for a in entry.findall("atom:author", ns)
                               if a.find("atom:name", ns) is not None]
                    if id_el is not None:
                        paper_url = id_el.text.strip()
                        if self._is_seen(paper_url):
                            continue
                        papers.append({
                            "source": "arxiv",
                            "title": (title_el.text or "").strip().replace("\n", " "),
                            "authors": ", ".join(authors[:5]),
                            "abstract": (abstract_el.text or "").strip()[:500],
                            "url": paper_url,
                            "published_date": (published_el.text or "").strip()[:10],
                            "category": cat,
                        })
            except Exception as e:
                logger.warning(f"ArXiv fetch failed for {cat}: {e}")
        return papers

    def fetch_semantic_scholar(self, max_results: int = 20) -> List[dict]:
        papers = []
        query = "blockchain consensus confidential transactions zero-knowledge"
        params = urllib.parse.urlencode({
            "query": query,
            "fields": "title,authors,year,abstract,externalIds",
            "limit": max_results,
        })
        url = f"{SEMANTIC_SCHOLAR_API}?{params}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "BitchchainAgent/0.1"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            for paper in data.get("data", []):
                doi = paper.get("externalIds", {}).get("DOI", "")
                paper_url = f"https://doi.org/{doi}" if doi else f"https://semanticscholar.org/paper/{paper.get('paperId', '')}"
                if self._is_seen(paper_url):
                    continue
                authors = [a.get("name", "") for a in paper.get("authors", [])[:5]]
                year = paper.get("year") or 0
                published_date = f"{year}-01-01" if year else ""
                papers.append({
                    "source": "semantic_scholar",
                    "title": paper.get("title", ""),
                    "authors": ", ".join(authors),
                    "abstract": (paper.get("abstract") or "")[:500],
                    "url": paper_url,
                    "published_date": published_date,
                    "category": "cs.CR/cs.DC",
                })
        except Exception as e:
            logger.warning(f"Semantic Scholar fetch failed: {e}")
        return papers

    def fetch_papers_with_code(self, max_results: int = 20) -> List[dict]:
        papers = []
        params = urllib.parse.urlencode({
            "q": "blockchain throughput consensus",
            "ordering": "-arxiv_id_v1",
            "items_per_page": max_results,
        })
        url = f"{PAPERS_WITH_CODE_API}?{params}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "BitchchainAgent/0.1"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            for paper in data.get("results", []):
                paper_url = paper.get("url_abs", "") or paper.get("paper_pdf", "")
                if not paper_url or self._is_seen(paper_url):
                    continue
                papers.append({
                    "source": "papers_with_code",
                    "title": paper.get("title", ""),
                    "authors": ", ".join(paper.get("authors", [])[:5]),
                    "abstract": (paper.get("abstract") or "")[:500],
                    "url": paper_url,
                    "published_date": (paper.get("published", "") or "")[:10],
                    "category": "cs.CR",
                })
        except Exception as e:
            logger.warning(f"Papers with Code fetch failed: {e}")
        return papers

    def _format_entry(self, paper: dict, score: float) -> str:
        date_stamp = datetime.utcnow().strftime("%Y-%m-%d")
        return (
            f"| {paper['title'][:80]} | {paper['authors'][:40]} | "
            f"{paper.get('published_date', '')[:7]} | {paper['source']} | "
            f"{paper['url']} | {paper['abstract'][:150]}... | "
            f"Score: {score:.2f} | Added: {date_stamp} |\n"
        )

    def _append_to_brain(self, entries: List[tuple]):
        date_stamp = datetime.utcnow().strftime("%Y-%m-%d")
        section = f"\n### {date_stamp} Knowledge Update\n"
        section += f"*{len(entries)} new papers added by automated crawl*\n\n"
        section += "| Title | Authors | Published | Source | URL | Key Finding | |\n"
        section += "|-------|---------|-----------|--------|-----|-------------|---|\n"
        for paper, score in entries:
            section += self._format_entry(paper, score)

        section += f"\n**Update log entry**: {len(entries)} new entries added | Next run: +7 days\n"

        if not os.path.exists(self.brain_path):
            with open(self.brain_path, "w", encoding="utf-8") as f:
                f.write("# SECOND-KNOWLEDGE-BRAIN.md\n\n")

        with open(self.brain_path, "a", encoding="utf-8") as f:
            f.write(section)

        for paper, _ in entries:
            self._mark_seen(paper["url"])

    def run(self) -> dict:
        logger.info("Knowledge updater: starting research crawl...")
        start_time = time.time()
        all_papers = []

        # Fetch from all sources
        all_papers.extend(self.fetch_arxiv(["cs.CR", "cs.DC"], max_results=25))
        all_papers.extend(self.fetch_semantic_scholar(max_results=20))
        all_papers.extend(self.fetch_papers_with_code(max_results=20))

        logger.info(f"Fetched {len(all_papers)} candidate papers")

        # Score and rank
        scored = [(p, self._score_paper(p)) for p in all_papers]
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:MAX_NEW_ENTRIES_PER_RUN]

        new_entries = []
        for paper, score in top:
            if score > 0.1:
                new_entries.append((paper, score))

        if new_entries:
            self._append_to_brain(new_entries)
            logger.info(f"Appended {len(new_entries)} new entries to SECOND-KNOWLEDGE-BRAIN.md")
        else:
            logger.info("No new relevant papers found this run")

        elapsed = time.time() - start_time
        result = {
            "success": True,
            "candidates_fetched": len(all_papers),
            "new_entries": [{"title": p["title"], "url": p["url"], "score": round(s, 3)}
                            for p, s in new_entries],
            "elapsed_seconds": round(elapsed, 1),
            "next_run": (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d"),
        }
        logger.info(f"Knowledge update complete: {len(new_entries)} new entries in {elapsed:.1f}s")
        return result

    def schedule_weekly(self):
        """Run on a weekly cron schedule using APScheduler."""
        try:
            from apscheduler.schedulers.blocking import BlockingScheduler
            scheduler = BlockingScheduler()
            scheduler.add_job(self.run, "cron", day_of_week="sun", hour=2, minute=0)
            logger.info("Knowledge updater scheduled: every Sunday at 02:00 UTC")
            scheduler.start()
        except ImportError:
            logger.warning("APScheduler not installed. Run manually: python -m tools.knowledge_updater")

    def status(self) -> dict:
        return {
            "brain_path": self.brain_path,
            "seen_hashes_count": len(self._seen_hashes),
            "sources": ["arxiv:cs.CR", "arxiv:cs.DC", "semantic_scholar", "papers_with_code"],
            "schedule": "weekly Sunday 02:00 UTC",
            "max_entries_per_run": MAX_NEW_ENTRIES_PER_RUN,
        }

    def verify_live_crawl(self) -> dict:
        """
        Execute a live crawl and verify that entries are correctly appended
        to SECOND-KNOWLEDGE-BRAIN.md with deduplication.

        Returns a verification report with entry counts before/after, dedup
        check results, and pass/fail status for each criterion.
        """
        brain_path = self.brain_path
        initial_lines = 0
        if os.path.exists(brain_path):
            with open(brain_path, "r", encoding="utf-8") as f:
                initial_lines = len(f.readlines())

        initial_hashes = set(self._seen_hashes)

        result = self.run()

        final_lines = 0
        if os.path.exists(brain_path):
            with open(brain_path, "r", encoding="utf-8") as f:
                final_lines = len(f.readlines())

        new_entries = result.get("new_entries", [])
        new_count = len(new_entries)

        # Verify dedup: run again and check zero duplicates
        dedup_result = self.run()
        second_new = len(dedup_result.get("new_entries", []))
        duplicates_found = second_new

        # Verify brain file has new content
        lines_added = final_lines - initial_lines

        passed = new_count >= 5 and duplicates_found == 0 and lines_added > 0

        report = {
            "crawl_success": result.get("success", False),
            "entries_before": len(initial_hashes),
            "entries_after_crawl1": new_count,
            "entries_after_crawl2": second_new,
            "duplicates_found": duplicates_found,
            "lines_added_to_brain": lines_added,
            "criteria": {
                "at_least_5_new_entries": new_count >= 5,
                "zero_duplicates_on_rerun": duplicates_found == 0,
                "brain_file_updated": lines_added > 0,
            },
            "passed": passed,
            "elapsed_seconds": result.get("elapsed_seconds", 0),
        }

        logger.info(f"Live crawl verification: {'PASSED' if passed else 'FAILED'}")
        return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    updater = KnowledgeUpdater(brain_path="SECOND-KNOWLEDGE-BRAIN.md")
    result = updater.run()
    print(json.dumps(result, indent=2))
