"""Token, semantic and sentence-window chunkers."""

from statistics import mean

from llama_index.core.node_parser import (
    SemanticSplitterNodeParser,
    SentenceWindowNodeParser,
    TokenTextSplitter,
)

from .config import (
    SEMANTIC_BREAKPOINT_PERCENTILE,
    SEMANTIC_BUFFER_SIZE,
    SENTENCE_WINDOW_SIZE,
    TOKEN_CHUNK_OVERLAP,
    TOKEN_CHUNK_SIZE,
)
from .embeddings import create_embedding_model
from .ingestion import load_corpus_documents


def create_chunkers(embed_model):
    return {
        "token": TokenTextSplitter(
            chunk_size=TOKEN_CHUNK_SIZE,
            chunk_overlap=TOKEN_CHUNK_OVERLAP,
        ),
        "semantic": SemanticSplitterNodeParser(
            embed_model=embed_model,
            buffer_size=SEMANTIC_BUFFER_SIZE,
            breakpoint_percentile_threshold=(
                SEMANTIC_BREAKPOINT_PERCENTILE
            ),
        ),
        "sentence_window": SentenceWindowNodeParser.from_defaults(
            window_size=SENTENCE_WINDOW_SIZE,
            window_metadata_key="window",
            original_text_metadata_key="original_sentence",
        ),
    }


def chunk_documents(documents, embed_model):
    expected_sources = {
        document.metadata["source_file"] for document in documents
    }

    nodes_by_technique = {}

    for technique, parser in create_chunkers(embed_model).items():
        print(f"Creating {technique} chunks...")

        nodes = parser.get_nodes_from_documents(
            documents,
            show_progress=True,
        )

        if not nodes:
            raise ValueError(f"{technique} produced no chunks")

        for node in nodes:
            node.metadata["chunking_technique"] = technique

            node.excluded_embed_metadata_keys = list(node.metadata.keys())

        loaded_sources = {
            node.metadata.get("source_file") for node in nodes
        }

        missing_sources = sorted(expected_sources - loaded_sources)

        if missing_sources:
            raise ValueError(
                f"{technique} omitted sources: {missing_sources}"
            )

        nodes_by_technique[technique] = nodes

    return nodes_by_technique


def summarize_nodes(technique, nodes):
    chunk_lengths = [len(node.text) for node in nodes]

    return {
        "technique": technique,
        "chunks": len(nodes),
        "avg_chunk_length_chars": round(mean(chunk_lengths), 2),
        "min_chunk_length_chars": min(chunk_lengths),
        "max_chunk_length_chars": max(chunk_lengths),
    }


def main() -> None:
    documents = load_corpus_documents()
    embed_model = create_embedding_model()
    nodes_by_technique = chunk_documents(documents, embed_model)

    print("\nChunking summary")

    for technique, nodes in nodes_by_technique.items():
        summary = summarize_nodes(technique, nodes)
        print(
            f"{technique}: "
            f"chunks={summary['chunks']}, "
            f"avg_chars={summary['avg_chunk_length_chars']}, "
            f"min_chars={summary['min_chunk_length_chars']}, "
            f"max_chars={summary['max_chunk_length_chars']}"
        )


if __name__ == "__main__":
    main()