import os
import json
import faiss
import numpy as np
import logging
from typing import List, Dict
from sentence_transformers import SentenceTransformer
from config import EMBEDDING_MODEL, FAISS_DIR

logger = logging.getLogger(__name__)

# Load embedding model once
_model = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def create_faiss_index(chunks: List[Dict], chat_id: int, user_id: int, upload_timestamp: str) -> str:
    """Create a FAISS index from text chunks and persist to disk."""
    model = _get_model()

    texts = [chunk["text"] for chunk in chunks]
    embeddings = model.encode(texts, show_progress_bar=False)
    embeddings = np.array(embeddings).astype("float32")

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)

    # Create directory for this index
    index_dir = os.path.join(FAISS_DIR, f"chat_{chat_id}", f"user_{user_id}", upload_timestamp)
    os.makedirs(index_dir, exist_ok=True)

    index_path = os.path.join(index_dir, "index.faiss")
    chunks_path = os.path.join(index_dir, "chunks.json")

    faiss.write_index(index, index_path)

    with open(chunks_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    logger.info(f"Created FAISS index at {index_path} with {len(chunks)} chunks")
    return index_path, chunks_path


def search_faiss_index(query: str, index_path: str, chunks_path: str, top_k: int = 5) -> List[Dict]:
    """Search a FAISS index for chunks relevant to the query."""
    model = _get_model()

    if not os.path.exists(index_path) or not os.path.exists(chunks_path):
        logger.error(f"FAISS index or chunks file not found: {index_path}")
        return []

    index = faiss.read_index(index_path)

    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    query_embedding = model.encode([query], show_progress_bar=False)
    query_embedding = np.array(query_embedding).astype("float32")

    k = min(top_k, index.ntotal)
    distances, indices = index.search(query_embedding, k)

    results = []
    for i, idx in enumerate(indices[0]):
        if idx < len(chunks) and idx >= 0:
            results.append({
                "chunk": chunks[idx],
                "score": float(distances[0][i])
            })

    return results


def delete_faiss_index(index_path: str):
    """Delete a FAISS index and its chunks file from disk."""
    import shutil
    index_dir = os.path.dirname(index_path)
    if os.path.exists(index_dir):
        shutil.rmtree(index_dir)
        logger.info(f"Deleted FAISS index directory: {index_dir}")
