"""The MiniLM embedding model used by every technique."""

import numpy as np
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from .config import EMBEDDING_MODEL_NAME


def create_embedding_model() -> HuggingFaceEmbedding:
    return HuggingFaceEmbedding(
        model_name=EMBEDDING_MODEL_NAME,
        device="cpu",
        normalize=True,
    )


def main() -> None:
    embed_model = create_embedding_model()
    test_query = "What protections are available to rental housing tenants?"

    query_vector = np.asarray(
        embed_model.get_query_embedding(test_query),
        dtype=np.float32,
    )

    print(f"Embedding model: {EMBEDDING_MODEL_NAME}")
    print(f"Test query: {test_query}")
    print(f"Query vector shape: {query_vector.shape}")
    print(f"Embedding dimension: {query_vector.size}")
    print(
        "First 8 values:",
        [round(float(value), 6) for value in query_vector[:8]],
    )


if __name__ == "__main__":
    main()