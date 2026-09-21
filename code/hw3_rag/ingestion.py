"""Check the corpus files and load the PDFs."""

import hashlib
import json
from pathlib import Path

from llama_index.core import SimpleDirectoryReader

from .config import CORPUS_DIR, MANIFEST_PATH


MIN_CORPUS_BYTES = 200 * 1024


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file_handle:
        for block in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def validate_corpus() -> list[Path]:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Manifest not found: {MANIFEST_PATH}")

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    expected_entries = {
        entry["filename"]: entry for entry in manifest["files"]
    }

    actual_files = {
        path.name: path for path in CORPUS_DIR.glob("*.pdf")
    }

    expected_names = set(expected_entries)
    actual_names = set(actual_files)

    missing = sorted(expected_names - actual_names)
    unexpected = sorted(actual_names - expected_names)

    if missing:
        raise ValueError(f"Missing corpus files: {missing}")

    if unexpected:
        raise ValueError(f"Unexpected corpus files: {unexpected}")

    total_bytes = 0
    validated_paths = []

    for filename in sorted(expected_names):
        path = actual_files[filename]
        expected = expected_entries[filename]
        actual_size = path.stat().st_size
        actual_hash = calculate_sha256(path)

        if actual_size != expected["byte_size"]:
            raise ValueError(
                f"Size mismatch for {filename}: "
                f"expected {expected['byte_size']}, got {actual_size}"
            )

        if actual_hash != expected["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {filename}")

        total_bytes += actual_size
        validated_paths.append(path)

    if total_bytes < MIN_CORPUS_BYTES:
        raise ValueError(
            f"Corpus is too small: {total_bytes} bytes; "
            f"minimum is {MIN_CORPUS_BYTES} bytes"
        )

    if total_bytes != manifest["total_bytes"]:
        raise ValueError(
            f"Manifest total is {manifest['total_bytes']}, "
            f"but files total {total_bytes}"
        )

    return validated_paths


def file_metadata(filename: str) -> dict[str, str]:
    return {"source_file": Path(filename).name}


def load_corpus_documents():
    pdf_paths = validate_corpus()

    reader = SimpleDirectoryReader(
        input_files=[str(path) for path in pdf_paths],
        file_metadata=file_metadata,
    )

    documents = [
        document
        for document in reader.load_data()
        if document.text.strip()
    ]

    if not documents:
        raise ValueError("No extractable corpus text was loaded")

    expected_sources = {path.name for path in pdf_paths}
    loaded_sources = {
        document.metadata.get("source_file")
        for document in documents
    }

    missing_sources = sorted(expected_sources - loaded_sources)

    if missing_sources:
        raise ValueError(
            f"Ingestion skipped corpus sources: {missing_sources}"
        )

    return documents


def main() -> None:
    pdf_paths = validate_corpus()
    documents = load_corpus_documents()

    total_bytes = sum(path.stat().st_size for path in pdf_paths)
    total_characters = sum(len(document.text) for document in documents)

    print(f"Validated corpus files: {len(pdf_paths)}")
    print(f"Validated corpus bytes: {total_bytes}")
    print(f"Loaded non-empty documents/pages: {len(documents)}")
    print(f"Extracted characters: {total_characters}")

    for path in pdf_paths:
        print(f"- {path.name}: {path.stat().st_size} bytes")


if __name__ == "__main__":
    main()