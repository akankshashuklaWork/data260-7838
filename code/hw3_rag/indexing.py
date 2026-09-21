"""One in-memory vector index per chunking technique."""

from time import perf_counter

from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.vector_stores import SimpleVectorStore

from .chunkers import chunk_documents
from .embeddings import create_embedding_model
from .ingestion import load_corpus_documents


def build_indexes(nodes_by_technique, embed_model):
    indexes = {}
    build_times_ms = {}

    for technique, nodes in nodes_by_technique.items():
        print(f"Building {technique} in-memory index...")

        vector_store = SimpleVectorStore()
        storage_context = StorageContext.from_defaults(
            vector_store=vector_store
        )

        start_time = perf_counter()

        index = VectorStoreIndex(
            nodes=nodes,
            storage_context=storage_context,
            embed_model=embed_model,
            show_progress=True,
        )

        elapsed_ms = (perf_counter() - start_time) * 1000

        indexes[technique] = index
        build_times_ms[technique] = elapsed_ms

    return indexes, build_times_ms


def main() -> None:
    documents = load_corpus_documents()
    embed_model = create_embedding_model()
    nodes_by_technique = chunk_documents(documents, embed_model)

    indexes, build_times_ms = build_indexes(
        nodes_by_technique,
        embed_model,
    )

    print("\nIndexing summary")

    for technique in indexes:
        print(
            f"{technique}: "
            f"nodes={len(nodes_by_technique[technique])}, "
            f"build_ms={build_times_ms[technique]:.2f}"
        )


if __name__ == "__main__":
    main()