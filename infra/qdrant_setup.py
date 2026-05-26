"""Create the Qdrant collection used for incident embeddings.

Run this once after the Qdrant container is up.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams


load_dotenv()

QDRANT_HOST = os.getenv("QDRANT_HOST", "http://localhost:6333")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "incidents")
VECTOR_DIM = int(os.getenv("EMBEDDING_DIM", "384"))


def create_collection() -> None:
	"""Create the incidents collection if it does not already exist."""

	client = QdrantClient(url=QDRANT_HOST)
	existing_collections = {collection.name for collection in client.get_collections().collections}

	if COLLECTION_NAME in existing_collections:
		print(f"Collection '{COLLECTION_NAME}' already exists. Skipping.")
		return

	client.create_collection(
		collection_name=COLLECTION_NAME,
		vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
	)
	print(f"Collection '{COLLECTION_NAME}' created with dim={VECTOR_DIM}.")


if __name__ == "__main__":
	create_collection()
