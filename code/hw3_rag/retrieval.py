"""Retrieval and independent cosine-similarity verification."""

from hashlib import sha256
from time import perf_counter

import numpy as np
import yaml
from llama_index.core.schema import MetadataMode

from .chunkers import chunk_documents
from .config import PREVIEW_LENGTH, QUESTIONS_PATH
from .embeddings import create_embedding_model
from .indexing import build_indexes
from .ingestion import load_corpus_documents


def cosine_similarity(vector_a, vector_b):
    denominator = np.linalg.norm(vector_a) * np.linalg.norm(vector_b)

    if denominator == 0:
        return 0.0

    return float(np.dot(vector_a, vector_b) / denominator)


def make_preview(text):
    compact_text = " ".join((text or "").split())
    return compact_text[:PREVIEW_LENGTH]


def retrieve_one(index, embed_model, question, top_k):
    query_vector = np.asarray(
        embed_model.get_query_embedding(question),
        dtype=np.float32,
    )

    retriever = index.as_retriever(similarity_top_k=top_k)

    start_time = perf_counter()
    retrieved_nodes = retriever.retrieve(question)
    latency_ms = (perf_counter() - start_time) * 1000

    results = []
    document_vectors = []

    for rank, retrieved in enumerate(retrieved_nodes, start=1):
        node = retrieved.node

        # Because metadata was excluded from embeddings, this is chunk text.
        embedded_text = node.get_content(
            metadata_mode=MetadataMode.EMBED
        )

        document_vector = np.asarray(
            embed_model.get_text_embedding(embedded_text),
            dtype=np.float32,
        )
        document_vectors.append(document_vector)

        results.append(
            {
                "rank": rank,
                "source_file": node.metadata.get("source_file"),
                "page_label": node.metadata.get("page_label"),
                "chunk_sha256": sha256(
                    (
                        str(node.metadata.get("source_file", ""))
                        + "\0"
                        + node.text
                    ).encode("utf-8")
                ).hexdigest(),
                "store_score": float(retrieved.score),
                "independent_cosine": cosine_similarity(
                    query_vector,
                    document_vector,
                ),
                "chunk_length_chars": len(node.text),
                "preview": make_preview(node.text),
                "chunk_text": node.text,
                "window_preview": make_preview(
                    node.metadata.get("window", "")
                ),
                "window_text": node.metadata.get("window"),
            }
        )

    document_matrix = np.vstack(document_vectors)

    return {
        "latency_ms": latency_ms,
        "query_vector_shape": list(query_vector.shape),
        "query_embedding_dimension": int(query_vector.shape[0]),
        "query_vector_first_8": [
            round(float(value), 6) for value in query_vector[:8]
        ],
        "document_vectors_shape": list(document_matrix.shape),
        "results": results,
    }


def main():
    with QUESTIONS_PATH.open(encoding="utf-8") as file:
        question_config = yaml.safe_load(file)

    top_k = question_config["top_k"]
    first_question = question_config["questions"][0]

    documents = load_corpus_documents()
    embed_model = create_embedding_model()
    nodes_by_technique = chunk_documents(documents, embed_model)
    indexes, _ = build_indexes(nodes_by_technique, embed_model)

    print("\nControlled retrieval test")
    print(f"Question: {first_question['question']}")
    print(f"Expected source: {first_question['expected_source']}")

    for technique, index in indexes.items():
        output = retrieve_one(
            index=index,
            embed_model=embed_model,
            question=first_question["question"],
            top_k=top_k,
        )

        print(f"\n=== {technique} chunking ===")
        print(f"Query embedding dimension: {output['query_embedding_dimension']}")
        print(f"Query first 8 values: {output['query_vector_first_8']}")
        print(f"Query vector shape: {output['query_vector_shape']}")
        print(f"Stacked document vectors shape: {output['document_vectors_shape']}")
        print(f"Retrieval latency: {output['latency_ms']:.2f} ms")
        print(f"{'rank':<6}{'store_score':<13}{'cosine_sim':<12}{'chunk_len':<11}preview")

        for result in output["results"]:
            print(
                f"{result['rank']:<6}"
                f"{result['store_score']:<13.6f}"
                f"{result['independent_cosine']:<12.6f}"
                f"{result['chunk_length_chars']:<11}"
                f"{result['preview']}"
            )
            print(f"{'':<6}source: {result['source_file']}")


if __name__ == "__main__":
    main()
