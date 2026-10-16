#!/usr/bin/env python3
"""Phase 2: embed leaf chunks and insert every chunk into Milvus.

Only `is_leaf` chunks (see chunker.leaves — NOT chunk_type == "child") get a
real BAAI/bge-base-en-v1.5 embedding. Non-leaf rows still get inserted, with
an all-zero placeholder vector, so parent-expansion at answer time is a
plain scalar lookup on `parent_chunk_id` rather than a second search.
"""
from __future__ import annotations

import json

from pymilvus import MilvusClient
from sentence_transformers import SentenceTransformer

import config
from chunker.leaves import leaf_ids
from milvus_schema import COLLECTION_NAME, DENSE_DIM, get_client

OUTPUT_DIR = config.output_dir()
MODEL_NAME = "BAAI/bge-base-en-v1.5"
BATCH_SIZE = 64
ZERO_VECTOR = [0.0] * DENSE_DIM
# Milvus VARCHAR max_length counts bytes; whole-file parent sections of the
# larger docs can exceed it.
MAX_TEXT_BYTES = 65000


def _fit(text: str) -> str:
    b = text.encode("utf-8")
    return text if len(b) <= MAX_TEXT_BYTES else b[:MAX_TEXT_BYTES].decode("utf-8", "ignore")


def embed_text(c: dict) -> str:
    """Spec chunks embed their raw text only (the reranker/boost calibration
    assumes it). Developer docs and plans get their heading breadcrumb
    prepended, since a bare "## Overview" section says nothing about which
    concept it belongs to."""
    if c["file_path"].startswith(("specs/", ".specify/")):
        return c["raw_text"]
    return f"{c['heading_path']}\n\n{c['raw_text']}"


def load_all_chunks() -> list[dict]:
    all_chunks: list[dict] = []
    for p in sorted(OUTPUT_DIR.glob("*.json")):
        chunks = json.loads(p.read_text(encoding="utf-8"))
        eligible = leaf_ids(chunks)
        for c in chunks:
            c["is_leaf"] = c["chunk_id"] in eligible
        all_chunks.extend(chunks)
    return all_chunks


def to_row(c: dict, vector: list[float]) -> dict:
    return {
        "chunk_id": c["chunk_id"],
        "file_path": c["file_path"],
        "heading_path": c["heading_path"][:1000],
        "start_line": c["start_line"],
        "end_line": c["end_line"],
        "chunk_type": c["chunk_type"],
        "parent_chunk_id": c["parent_chunk_id"] or "",
        "is_leaf": c["is_leaf"],
        "item_kind": c.get("item_kind") or "",
        "item_id": c.get("item_id") or "",
        "raw_text": _fit(c["raw_text"]),
        "dense_vector": vector,
        # sparse_vector is a BM25-function output — never provided at insert time.
    }


def main() -> None:
    print("Loading chunk trees from output/*.json ...")
    chunks = load_all_chunks()
    leaves = [c for c in chunks if c["is_leaf"]]
    non_leaves = [c for c in chunks if not c["is_leaf"]]
    print(f"{len(chunks)} total chunks: {len(leaves)} leaves to embed, {len(non_leaves)} non-leaf placeholders")

    print(f"Loading {MODEL_NAME} ...")
    model = SentenceTransformer(MODEL_NAME)
    assert model.get_sentence_embedding_dimension() == DENSE_DIM

    print(f"Embedding {len(leaves)} leaf chunks (batch_size={BATCH_SIZE}) ...")
    texts = [embed_text(c) for c in leaves]
    vectors = model.encode(
        texts, batch_size=BATCH_SIZE, normalize_embeddings=True, show_progress_bar=True,
    )

    rows = [to_row(c, vectors[i].tolist()) for i, c in enumerate(leaves)]
    rows += [to_row(c, ZERO_VECTOR) for c in non_leaves]

    client: MilvusClient = get_client()
    if not client.has_collection(COLLECTION_NAME):
        raise SystemExit(f"Collection '{COLLECTION_NAME}' doesn't exist — run milvus_schema.py first.")

    print(f"Inserting {len(rows)} rows into '{COLLECTION_NAME}' ...")
    for i in range(0, len(rows), 500):
        batch = rows[i:i + 500]
        client.insert(collection_name=COLLECTION_NAME, data=batch)
        print(f"  inserted {min(i + 500, len(rows))}/{len(rows)}")

    client.flush(COLLECTION_NAME)
    stats = client.get_collection_stats(COLLECTION_NAME)
    print(f"\nDone. Collection row count: {stats['row_count']} (expected {len(rows)})")

    print("\nLoading collection for search ...")
    client.load_collection(COLLECTION_NAME)

    print("\n=== test query: dense search for 'how does cart currency change validation work' ===")
    q_vec = model.encode(
        ["Represent this sentence for searching relevant passages: how does cart currency change validation work"],
        normalize_embeddings=True,
    )[0].tolist()
    results = client.search(
        collection_name=COLLECTION_NAME,
        data=[q_vec],
        anns_field="dense_vector",
        filter="is_leaf == true",
        limit=5,
        output_fields=["file_path", "heading_path", "start_line", "end_line", "chunk_type"],
    )
    for hit in results[0]:
        e = hit["entity"]
        print(f"  score={hit['distance']:.4f}  {e['file_path']}#{e['start_line']}-{e['end_line']}  {e['heading_path']}")


if __name__ == "__main__":
    main()
