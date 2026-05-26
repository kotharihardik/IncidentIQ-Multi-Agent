<<<<<<< HEAD
import os
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

_QDRANT     = os.getenv("QDRANT_HOST", "http://localhost:6333")
_COLLECTION = os.getenv("QDRANT_COLLECTION", "incidents")
_DIM        = int(os.getenv("EMBEDDING_DIM", "384"))


def setup() -> None:
    client = QdrantClient(url=_QDRANT)
    existing = [c.name for c in client.get_collections().collections]

    if _COLLECTION in existing:
        print(f"[qdrant_setup] Collection '{_COLLECTION}' already exists — skipping.")
        return

    client.create_collection(
        collection_name=_COLLECTION,
        vectors_config=VectorParams(size=_DIM, distance=Distance.COSINE),
    )
    print(f"[qdrant_setup] Collection '{_COLLECTION}' created (dim={_DIM}).")


if __name__ == "__main__":
    setup()
=======
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
>>>>>>> d8fc6125ea1b55e2ebb060d35dc138d94da32ffd
