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
