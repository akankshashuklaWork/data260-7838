"""Verify the committed corpus and generated HW3 Part 2 evidence."""

import json
from pathlib import Path

import yaml

from .config import (
    DOMAIN_ID,
    EMBEDDING_MODEL_NAME,
    MANIFEST_PATH,
    QUESTIONS_PATH,
    RAW_DIR,
    REPORT_DIR,
    SEED,
    SID4,
)
from .ingestion import validate_corpus


EXPECTED_TECHNIQUES = {"token", "semantic", "sentence_window"}
EXPECTED_QUESTION_IDS = {"q1", "q2", "q3", "q4", "q5"}


def check(condition, description, checks):
    checks.append({"check": description, "passed": bool(condition)})
    if not condition:
        raise AssertionError(description)


def main():
    checks = []

    manifest_paths = validate_corpus()
    with MANIFEST_PATH.open(encoding="utf-8") as file:
        manifest = json.load(file)
    check(manifest["domain_id"] == DOMAIN_ID, "domain ID is 6", checks)
    check(len(manifest_paths) == 5, "manifest contains five PDFs", checks)
    check(
        manifest["total_bytes"] >= 200_000,
        "corpus exceeds the 200 KB minimum",
        checks,
    )

    with QUESTIONS_PATH.open(encoding="utf-8") as file:
        question_config = yaml.safe_load(file)
    questions = question_config["questions"]
    question_ids = {question["id"] for question in questions}
    check(len(questions) == 5, "five retrieval questions exist", checks)
    check(
        question_ids == EXPECTED_QUESTION_IDS,
        "question IDs are q1 through q5",
        checks,
    )
    check(
        sum(bool(question["unique_source"]) for question in questions) >= 2,
        "at least two questions are marked unique-source",
        checks,
    )
    check(question_config["top_k"] == 5, "top_k is 5", checks)

    retrieval_paths = sorted((RAW_DIR / "retrieval").glob("*/*.json"))
    check(
        len(retrieval_paths) == 15,
        "15 per-question/per-technique retrieval files exist",
        checks,
    )

    seen_pairs = set()
    maximum_score_delta = 0.0
    for path in retrieval_paths:
        with path.open(encoding="utf-8") as file:
            record = json.load(file)

        pair = (record["technique"], record["question_id"])
        seen_pairs.add(pair)
        check(len(record["results"]) == 5, f"{pair} has five results", checks)
        check(
            record["query_vector_shape"] == [384],
            f"{pair} query vector shape is [384]",
            checks,
        )
        check(
            record["document_vectors_shape"] == [5, 384],
            f"{pair} document vector shape is [5, 384]",
            checks,
        )
        check(
            record["embedding_model"] == EMBEDDING_MODEL_NAME,
            f"{pair} uses the configured public embedding model",
            checks,
        )
        check(
            "generated_answer" not in record,
            f"{pair} contains no generated answer",
            checks,
        )

        for result in record["results"]:
            check(
                len(result["chunk_sha256"]) == 64,
                f"{pair} rank {result['rank']} has a chunk hash",
                checks,
            )
            delta = abs(
                result["store_score"] - result["independent_cosine"]
            )
            maximum_score_delta = max(maximum_score_delta, delta)

    expected_pairs = {
        (technique, question_id)
        for technique in EXPECTED_TECHNIQUES
        for question_id in EXPECTED_QUESTION_IDS
    }
    check(
        seen_pairs == expected_pairs,
        "all five questions exist for all three techniques",
        checks,
    )
    check(
        maximum_score_delta < 1e-5,
        "store and independent cosine scores agree within 1e-5",
        checks,
    )

    chunk_summary_path = RAW_DIR / "chunking_summary.json"
    with chunk_summary_path.open(encoding="utf-8") as file:
        chunk_summary = json.load(file)
    chunk_counts = {
        row["technique"]: row["chunks"]
        for row in chunk_summary["techniques"]
    }
    check(
        set(chunk_counts) == EXPECTED_TECHNIQUES,
        "chunk summary contains all three techniques",
        checks,
    )
    check(
        all(count > 0 for count in chunk_counts.values()),
        "every technique produced non-empty chunks",
        checks,
    )

    metrics_path = REPORT_DIR / "METRICS.json"
    with metrics_path.open(encoding="utf-8") as file:
        metrics = json.load(file)
    check(
        len(metrics["aggregate"]) == 3,
        "aggregate metrics contain three techniques",
        checks,
    )
    check(
        len(metrics["per_question"]) == 15,
        "per-question metrics contain 15 rows",
        checks,
    )

    failure_path = RAW_DIR / "retrieval" / "sentence_window" / "q1.json"
    with failure_path.open(encoding="utf-8") as file:
        failure_record = json.load(file)
    failure_sources = {
        result["source_file"] for result in failure_record["results"]
    }
    failure_text = " ".join(
        [
            failure_record["results"][0]["chunk_text"],
            failure_record["results"][0]["window_text"] or "",
        ]
    ).lower()
    check(
        failure_record["expected_source"] not in failure_sources,
        "sentence-window q1 misses its expected source at top 5",
        checks,
    )
    check(
        "5 percent" not in failure_text and "12-month" not in failure_text,
        "sentence-window q1 rank-1 text omits the expected answer",
        checks,
    )

    verification = {
        "sid4": SID4,
        "seed": SEED,
        "domain_id": DOMAIN_ID,
        "all_checks_passed": True,
        "check_count": len(checks),
        "maximum_store_cosine_delta": maximum_score_delta,
        "chunk_counts": chunk_counts,
        "checks": checks,
    }

    output_path = REPORT_DIR / "verification.json"
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(verification, file, indent=2)
        file.write("\n")

    print(
        f"PASS: {len(checks)} checks; "
        f"maximum score delta={maximum_score_delta:.12g}"
    )
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
