import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def chunk_text(text: str) -> List[Dict]:
    """Chunk text using LlamaIndex HierarchicalNodeParser."""
    try:
        from llama_index.core import Document
        from llama_index.core.node_parser import (
            HierarchicalNodeParser,
            get_leaf_nodes
        )

        doc = Document(text=text)

        node_parser = HierarchicalNodeParser.from_defaults(
            chunk_sizes=[2048, 512, 128]
        )

        nodes = node_parser.get_nodes_from_documents([doc])
        leaf_nodes = get_leaf_nodes(nodes)

        chunks = []
        for i, node in enumerate(leaf_nodes):
            chunks.append({
                "id": i,
                "text": node.get_content(),
                "metadata": {
                    "start_char_idx": getattr(node, "start_char_idx", None),
                    "end_char_idx": getattr(node, "end_char_idx", None),
                }
            })

        logger.info(f"Created {len(chunks)} chunks from text")
        return chunks

    except ImportError:
        logger.warning("LlamaIndex not available, falling back to simple chunking")
        return _simple_chunk(text)


def _simple_chunk(text: str, chunk_size: int = 512, overlap: int = 50) -> List[Dict]:
    """Fallback simple text chunking."""
    chunks = []
    start = 0
    chunk_id = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk_text_content = text[start:end]
        if chunk_text_content.strip():
            chunks.append({
                "id": chunk_id,
                "text": chunk_text_content,
                "metadata": {"start_char_idx": start, "end_char_idx": end}
            })
            chunk_id += 1
        start += chunk_size - overlap
    return chunks
