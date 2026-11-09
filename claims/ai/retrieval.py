"""A9: retrieval over plan-benefit documents (the A8 pipeline inside Django).

    knowledge/*.md ──► chunk by "##" section ──► sentence-transformers embeddings ──► numpy matrix
    question ──► embed ──► cosine similarity (dot product of unit vectors) ──► filter + threshold ──► top-k

* Embedding model: settings.EMBEDDING_MODEL (default sentence-transformers/all-MiniLM-L6-v2,
  384-dim, ~90 MB). Weights download from the Hugging Face Hub on first use, like the LLM.
* The knowledge base is ~30 chunks, so a numpy matrix is enough; no vector database is needed.
  The matrix is cached in memory and saved under settings.RAG_INDEX_DIR, keyed by the model name
  and a hash of the documents, so editing a document rebuilds the index automatically.
* The member's own plan numbers come from the InsurancePlan row (plan_chunks), never from files.
* If sentence-transformers cannot run (no torch, e.g. PythonAnywhere), search() falls back to a
  TF-IDF keyword scorer so the page still shows the closest plan sections.
"""
import hashlib
import logging
import math
import re
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from django.conf import settings

log = logging.getLogger(__name__)

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"
PLAN_TYPES = ("PPO", "HMO", "EPO", "OTHER")
OVERLAP_WORDS = 20

_model = None
_model_lock = threading.Lock()
_index = {}       # cache key -> (chunks, matrix)
_plan_vectors = {}  # (model, text hash) -> vector


class RetrievalUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Chunk:
    id: str      # "emergency-care#2" or "plan:4#1"
    title: str   # "Emergency care and surprise bills: What you pay ..."
    scope: str   # "general", a plan type ("HMO"), or "plan:<pk>" for the member's own plan
    text: str

    @property
    def doc(self):
        return self.id.split("#")[0]

    @property
    def scope_label(self):
        if self.scope == "general":
            return "All plans"
        if self.scope.startswith("plan:"):
            return "Your plan"
        return f"{self.scope} plans"


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


@dataclass
class SearchResult:
    hits: list
    backend: str            # "embeddings" or "keyword"
    milliseconds: float
    candidates: int
    best_score: float = 0.0  # best score before the threshold, useful when nothing passes it
    notes: list = field(default_factory=list)


# ---------------------------------------------------------------- documents and chunking

def _split_words(text, size):
    words = text.split()
    if len(words) <= size:
        return [text]
    step = max(1, size - OVERLAP_WORDS)
    return [" ".join(words[i:i + size]) for i in range(0, len(words) - OVERLAP_WORDS, step)]


def parse_document(path, chunk_words=None):
    """Turn one knowledge file into chunks: one per "##" section, long sections windowed."""
    chunk_words = chunk_words or settings.RAG_CHUNK_WORDS
    lines = path.read_text(encoding="utf-8").splitlines()
    title = next((ln[2:].strip() for ln in lines if ln.startswith("# ")), path.stem)
    scope = next((ln.split(":", 1)[1].strip() for ln in lines if ln.lower().startswith("scope:")), "general")
    if scope != "general" and scope not in PLAN_TYPES:
        raise ValueError(f"{path.name}: unknown scope {scope!r}")
    sections, heading, body = [], None, []
    for line in lines:
        if line.startswith("## "):
            if heading:
                sections.append((heading, " ".join(body)))
            heading, body = line[3:].strip(), []
        elif heading and line.strip():
            body.append(line.strip())
    if heading:
        sections.append((heading, " ".join(body)))
    chunks = []
    for heading, text in sections:
        for part in _split_words(text, chunk_words):
            chunks.append(Chunk(f"{path.stem}#{len(chunks) + 1}", f"{title}: {heading}", scope, part))
    return chunks


def load_chunks(chunk_words=None):
    chunks = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        if path.name.lower() != "readme.md":
            chunks.extend(parse_document(path, chunk_words))
    return chunks


def plan_chunks(plan):
    """The member's own plan numbers, generated from the database row at query time."""
    if plan is None:
        return []
    deductible = f"${plan.deductible:,.0f}"
    pct = f"{plan.coinsurance_pct:.0f}%"
    plan_pays = f"{100 - plan.coinsurance_pct:.0f}%"
    oop = f"${plan.out_of_pocket_max:,.0f}"
    text = (
        f"Your plan is {plan.name} (plan type: {plan.get_plan_type_display()}). Your deductible is {deductible} "
        f"per plan year: you pay the first {deductible} of covered in-network care yourself. After you meet "
        f"the deductible, your coinsurance is {pct}: you pay {pct} and the plan pays {plan_pays} of covered "
        f"in-network charges. Your out-of-pocket maximum is {oop}: once you have paid {oop} in a plan year, "
        f"the plan pays 100% of covered in-network care for the rest of the year."
    )
    return [Chunk(f"plan:{plan.pk}#1", f"Your plan: {plan.name} deductible, coinsurance and out-of-pocket maximum",
                  f"plan:{plan.pk}", text)]


def candidate_filter(chunk, plan, filter_by_plan):
    """Which static chunks a member may be shown. With filtering on (the A9 improvement), plan-type
    documents for other plan types are excluded, so an HMO member never gets PPO rules."""
    if chunk.scope == "general" or not filter_by_plan:
        return True
    return plan is not None and chunk.scope == plan.plan_type


# ---------------------------------------------------------------- embeddings

def _embedder():
    global _model
    if not settings.RAG_EMBEDDINGS_ENABLED:
        raise RetrievalUnavailable("Semantic search is turned off on this server (RAG_EMBEDDINGS_ENABLED=0).")
    with _model_lock:
        if _model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RetrievalUnavailable("sentence-transformers is not installed on this server.") from exc
            _model = SentenceTransformer(settings.EMBEDDING_MODEL, device="cpu")
    return _model


def embed(texts):
    """Unit-length float32 vectors, so cosine similarity is a dot product."""
    vectors = _embedder().encode(list(texts), normalize_embeddings=True, convert_to_numpy=True,
                                 show_progress_bar=False)
    return np.asarray(vectors, dtype=np.float32)


def _chunk_text(chunk):
    return f"{chunk.title}\n{chunk.text}"


def _static_index(chunk_words=None):
    chunks = load_chunks(chunk_words)
    digest = hashlib.sha256("\n".join(f"{c.id}|{c.scope}|{_chunk_text(c)}" for c in chunks).encode()).hexdigest()[:16]
    key = f"{re.sub(r'[^A-Za-z0-9]+', '-', settings.EMBEDDING_MODEL)}-{digest}"
    if key in _index:
        return _index[key]
    path = Path(settings.RAG_INDEX_DIR) / f"{key}.npy"
    matrix = None
    if path.exists():
        try:
            matrix = np.load(path)
            if matrix.shape[0] != len(chunks):
                matrix = None
        except (OSError, ValueError):
            matrix = None
    if matrix is None:
        matrix = embed(_chunk_text(c) for c in chunks)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            np.save(path, matrix)
        except OSError:  # read-only disk: the in-memory copy is enough
            log.warning("Could not save the retrieval index to %s", path)
    _index[key] = (chunks, matrix)
    return _index[key]


def _plan_matrix(chunks):
    rows = []
    for chunk in chunks:
        key = (settings.EMBEDDING_MODEL, hashlib.sha256(_chunk_text(chunk).encode()).hexdigest())
        if key not in _plan_vectors:
            _plan_vectors[key] = embed([_chunk_text(chunk)])[0]
        rows.append(_plan_vectors[key])
    return np.vstack(rows) if rows else None


def build_index():
    """Download the embedding model and build the index ahead of time (manage.py build_plan_index)."""
    chunks, matrix = _static_index()
    return len(chunks), matrix.shape[1]


def reset():
    """Forget cached indexes (tests, or after changing settings)."""
    global _model
    _index.clear()
    _plan_vectors.clear()
    _model = None


# ---------------------------------------------------------------- keyword fallback

_STOP = set("a an and are as at be by can do does for from has have how i if in is it its me my of on or "
            "our so that the this to was what when which who will with you your".split())


def _tokens(text):
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOP]


def keyword_scores(query, chunks):
    """TF-IDF cosine similarity; used only when embeddings cannot run."""
    docs = [Counter(_tokens(_chunk_text(c))) for c in chunks]
    df = Counter(t for d in docs for t in d)
    idf = {t: math.log((1 + len(docs)) / (1 + n)) + 1 for t, n in df.items()}

    def vec(counts):
        v = {t: n * idf.get(t, 0.0) for t, n in counts.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {t: x / norm for t, x in v.items()}

    q = vec(Counter(_tokens(query)))
    return np.array([sum(w * vec(d).get(t, 0.0) for t, w in q.items()) for d in docs], dtype=np.float32)


# ---------------------------------------------------------------- search

def search(query, plan=None, *, k=None, min_score=None, filter_by_plan=None):
    """Top-k chunks for a question. Never raises for a missing model: falls back to keywords."""
    k = k or settings.RAG_TOP_K
    filter_by_plan = settings.RAG_FILTER_BY_PLAN if filter_by_plan is None else filter_by_plan
    start = time.perf_counter()
    notes = []
    try:
        static, matrix = _static_index()
        keep = [i for i, c in enumerate(static) if candidate_filter(c, plan, filter_by_plan)]
        own = plan_chunks(plan)
        chunks = [static[i] for i in keep] + own
        q = embed([query])[0]
        scores = matrix[keep] @ q
        if own:
            scores = np.concatenate([scores, _plan_matrix(own) @ q])
        backend = "embeddings"
        threshold = settings.RAG_MIN_SCORE if min_score is None else min_score
    except RetrievalUnavailable as exc:
        chunks = [c for c in load_chunks() if candidate_filter(c, plan, filter_by_plan)] + plan_chunks(plan)
        scores = keyword_scores(query, chunks)
        backend = "keyword"
        threshold = settings.RAG_KEYWORD_MIN_SCORE if min_score is None else min_score
        notes.append(f"{exc} Using keyword search instead.")
    order = np.argsort(-scores)[:k]
    best = float(scores[order[0]]) if len(order) else 0.0
    hits = [Hit(chunks[i], round(float(scores[i]), 3)) for i in order if scores[i] >= threshold]
    return SearchResult(hits, backend, round((time.perf_counter() - start) * 1000, 1), len(chunks), round(best, 3), notes)
