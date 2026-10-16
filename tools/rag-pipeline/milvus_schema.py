"""Phase 2: Milvus collection schema for the speckit-doc RAG pipeline.

One collection, dense + native BM25 sparse vectors side by side (Milvus
2.4+ hybrid search — this server is 2.6.20, confirmed via
`client.get_server_version()` before writing this), so no separate BM25
engine is needed.

Every chunk (leaf or not) is stored, so a matched leaf can be expanded to
its parent's `raw_text` via a plain scalar lookup on `parent_chunk_id`. Only
leaf chunks (`is_leaf: True`, per `chunker.leaves.leaf_ids` — NOT
`chunk_type == "child"`, see that module's docstring) get a real embedding;
non-leaf rows get an all-zero placeholder vector and are excluded from
search results via an `is_leaf == true` filter, not by omitting them from
the collection.
"""
from __future__ import annotations

from pymilvus import DataType, Function, FunctionType, MilvusClient

import config

COLLECTION_NAME = config.collection_name()
DENSE_DIM = 768  # BAAI/bge-base-en-v1.5

MILVUS_URI = "http://127.0.0.1:19530"


def get_client() -> MilvusClient:
    return MilvusClient(uri=MILVUS_URI)


def build_schema():
    schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
    schema.add_field("chunk_id", DataType.VARCHAR, is_primary=True, max_length=256)
    schema.add_field("file_path", DataType.VARCHAR, max_length=512)
    schema.add_field("heading_path", DataType.VARCHAR, max_length=1024)
    schema.add_field("start_line", DataType.INT64)
    schema.add_field("end_line", DataType.INT64)
    schema.add_field("chunk_type", DataType.VARCHAR, max_length=16)       # "parent" | "child" (structural, NOT the embed-eligibility flag)
    schema.add_field("parent_chunk_id", DataType.VARCHAR, max_length=256)  # "" sentinel for a file's H1 root
    schema.add_field("is_leaf", DataType.BOOL)                            # the actual embedding-eligibility flag
    schema.add_field("item_kind", DataType.VARCHAR, max_length=64)        # "" when not a template-rule child
    schema.add_field("item_id", DataType.VARCHAR, max_length=64)          # "" when not a template-rule child
    schema.add_field("raw_text", DataType.VARCHAR, max_length=65535, enable_analyzer=True)
    schema.add_field("dense_vector", DataType.FLOAT_VECTOR, dim=DENSE_DIM)
    schema.add_field("sparse_vector", DataType.SPARSE_FLOAT_VECTOR)

    schema.add_function(Function(
        name="bm25_fn",
        function_type=FunctionType.BM25,
        input_field_names=["raw_text"],
        output_field_names=["sparse_vector"],
    ))
    return schema


def build_index_params(client: MilvusClient):
    index_params = client.prepare_index_params()
    index_params.add_index(field_name="dense_vector", index_type="HNSW", metric_type="COSINE")
    index_params.add_index(field_name="sparse_vector", index_type="SPARSE_INVERTED_INDEX", metric_type="BM25")
    return index_params


def create_collection(client: MilvusClient, *, recreate: bool = False) -> None:
    exists = client.has_collection(COLLECTION_NAME)
    if exists and not recreate:
        print(f"Collection '{COLLECTION_NAME}' already exists — leaving it as-is.")
        return
    if exists and recreate:
        print(f"Dropping existing '{COLLECTION_NAME}' (recreate=True)...")
        client.drop_collection(COLLECTION_NAME)

    client.create_collection(
        collection_name=COLLECTION_NAME,
        schema=build_schema(),
        index_params=build_index_params(client),
    )
    print(f"Created collection '{COLLECTION_NAME}'.")


if __name__ == "__main__":
    client = get_client()
    create_collection(client)
    print(client.describe_collection(COLLECTION_NAME))
