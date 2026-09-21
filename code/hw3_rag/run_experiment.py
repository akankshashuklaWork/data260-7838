"""Run and save the complete HW3 retrieval-only experiment."""

import json
import random

import numpy as np
import yaml

from .chunkers import chunk_documents, summarize_nodes
from .config import (
    DOMAIN_ID,
    DOMAIN_NAME,
    EMBEDDING_MODEL_NAME,
    QUESTIONS_PATH,
    RAW_DIR,
    SEED,
    SID4,
)
from .embeddings import create_embedding_model
from .indexing import build_indexes
from .ingestion import load_corpus_documents
from .retrieval import retrieve_one


def load_question_configuration():
    with QUESTIONS_PATH.open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def main():
    random.seed(SEED)
    np.random.seed(SEED)

    configuration = load_question_configuration()
    questions = configuration["questions"]
    top_k = configuration["top_k"]

    documents = load_corpus_documents()
    embed_model = create_embedding_model()
    nodes_by_technique = chunk_documents(documents, embed_model)

    indexes, build_times_ms = build_indexes(
        nodes_by_technique,
        embed_model,
    )

    chunking_summary = {
        "embedding_model": EMBEDDING_MODEL_NAME,
        "techniques": [
            summarize_nodes(technique, nodes)
            for technique, nodes in nodes_by_technique.items()
        ],
    }
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with (RAW_DIR / "chunking_summary.json").open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(chunking_summary, file, indent=2)
        file.write("\n")

    written_files = 0

    for question in questions:
        print(f"\nRunning {question['id']}: {question['question']}")

        for technique, index in indexes.items():
            retrieval_output = retrieve_one(
                index=index,
                embed_model=embed_model,
                question=question["question"],
                top_k=top_k,
            )

            raw_record = {
                "experiment": "HW3 Part 2 retrieval-only RAG",
                "sid4": SID4,
                "seed": SEED,
                "domain_id": DOMAIN_ID,
                "domain": DOMAIN_NAME,
                "embedding_model": EMBEDDING_MODEL_NAME,
                "technique": technique,
                "chunk_count": len(nodes_by_technique[technique]),
                "index_build_ms": round(
                    build_times_ms[technique],
                    6,
                ),
                "question_id": question["id"],
                "question": question["question"],
                "expected_answer": question["expected_answer"],
                "expected_source": question["expected_source"],
                "unique_source": question["unique_source"],
                "top_k": top_k,
                **retrieval_output,
            }

            output_directory = RAW_DIR / "retrieval" / technique
            output_directory.mkdir(parents=True, exist_ok=True)
            output_path = output_directory / f"{question['id']}.json"

            with output_path.open("w", encoding="utf-8") as file:
                json.dump(
                    raw_record,
                    file,
                    indent=2,
                    ensure_ascii=False,
                )
                file.write("\n")

            written_files += 1
            top_result = retrieval_output["results"][0]

            print(
                f"  {technique}: "
                f"top1={top_result['source_file']}, "
                f"score={top_result['independent_cosine']:.6f}, "
                f"latency={retrieval_output['latency_ms']:.2f} ms"
            )

    print(
        f"\nSaved {written_files} raw retrieval files under "
        f"{RAW_DIR / 'retrieval'}"
    )


if __name__ == "__main__":
    main()
