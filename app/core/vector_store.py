import re
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
import numpy as np
import faiss

try:
    from fastembed import TextEmbedding
    HAS_FASTEMBED = True
except Exception:
    HAS_FASTEMBED = False

@dataclass
class CodeChunk:
    chunk_id: str
    file_path: str
    symbol_name: str
    symbol_type: str  # 'function', 'class', 'method', 'import', 'module', 'block'
    start_line: int
    end_line: int
    content: str
    summary: str = ""
    language: str = "text"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class VectorIndex:
    """
    Code-aware hybrid vector store using FAISS & FastEmbed neural embeddings.
    Combines dense semantic similarity with exact symbol token matching.
    """

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", dimension: int = 384):
        self.dimension = dimension
        self.model_name = model_name
        self.index = faiss.IndexFlatIP(self.dimension)
        self.chunks: List[CodeChunk] = []
        self._embedder = None
        self._init_embedder()

    def _init_embedder(self):
        if HAS_FASTEMBED:
            try:
                self._embedder = TextEmbedding(model_name=self.model_name)
            except Exception as e:
                self._embedder = None

    def _compute_embeddings(self, texts: List[str]) -> np.ndarray:
        if self._embedder:
            try:
                embeddings = list(self._embedder.embed(texts))
                arr = np.array(embeddings, dtype=np.float32)
                faiss.normalize_L2(arr)
                return arr
            except Exception:
                pass

        # Fallback deterministic pseudo-embedding if FastEmbed fails
        vectors = []
        for text in texts:
            words = re.findall(r'[a-zA-Z0-9_]+', text.lower())
            vec = np.zeros(self.dimension, dtype=np.float32)
            for w in words:
                h = abs(hash(w)) % self.dimension
                vec[h] += 1.0
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            vectors.append(vec)
        return np.array(vectors, dtype=np.float32)

    def clear(self):
        self.index.reset()
        self.chunks.clear()

    def add_chunks(self, chunks: List[CodeChunk]):
        if not chunks:
            return

        # Prepare rich contextual text for each chunk
        texts_to_embed = []
        for c in chunks:
            header = f"File: {c.file_path} | {c.symbol_type.upper()} {c.symbol_name} (lines {c.start_line}-{c.end_line})"
            desc = c.summary or ""
            text = f"{header}\n{desc}\n{c.content[:600]}"
            texts_to_embed.append(text)

        embeddings = self._compute_embeddings(texts_to_embed)
        self.index.add(embeddings)
        self.chunks.extend(chunks)

    def search(
        self,
        query: str,
        top_k: int = 10,
        symbol_type: Optional[str] = None,
        file_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Executes hybrid search:
        1. Dense vector cosine similarity
        2. Exact symbol name / file keyword boost
        """
        if not self.chunks or self.index.ntotal == 0:
            return []

        q_vec = self._compute_embeddings([query])
        k = min(top_k * 3, self.index.ntotal)
        scores, indices = self.index.search(q_vec, k)

        query_terms = set(re.findall(r'[a-zA-Z0-9_]+', query.lower()))
        results = []

        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.chunks):
                continue

            chunk = self.chunks[idx]

            # Apply filters
            if symbol_type and symbol_type.lower() != "all":
                if chunk.symbol_type.lower() != symbol_type.lower():
                    continue

            if file_filter:
                if file_filter.lower() not in chunk.file_path.lower():
                    continue

            # Hybrid scoring: boost if symbol name or file path matches query terms
            final_score = float(score)
            symbol_lower = chunk.symbol_name.lower()
            file_lower = chunk.file_path.lower()

            for term in query_terms:
                if term in symbol_lower:
                    final_score += 0.25  # Symbol match bonus
                if term in file_lower:
                    final_score += 0.15  # Path match bonus

            results.append({
                "chunk": chunk.to_dict(),
                "score": round(final_score, 4),
                "semantic_score": round(float(score), 4)
            })

        # Sort by hybrid score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
