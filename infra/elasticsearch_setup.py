"""Create the Elasticsearch index used for log ingestion.

Run this once after the Elasticsearch container is up.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from elasticsearch import Elasticsearch


load_dotenv()

ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
ES_INDEX = os.getenv("ES_INDEX", "logs")

INDEX_MAPPING = {
	"mappings": {
		"dynamic": True,
		"properties": {
			"service": {"type": "keyword"},
			"level": {"type": "keyword"},
			"message": {"type": "text"},
			"timestamp": {"type": "date"},
			"trace_id": {"type": "keyword"},
			"error_type": {"type": "keyword"},
		},
	},
	"settings": {
		"number_of_shards": 1,
		"number_of_replicas": 0,
	},
}


def create_index() -> None:
	"""Create the logs index if it does not already exist."""

	es = Elasticsearch(ES_HOST)

	if es.indices.exists(index=ES_INDEX):
		print(f"Index '{ES_INDEX}' already exists. Skipping.")
		return

	es.indices.create(
		index=ES_INDEX,
		mappings=INDEX_MAPPING["mappings"],
		settings=INDEX_MAPPING["settings"],
	)
	print(f"Index '{ES_INDEX}' created successfully.")


if __name__ == "__main__":
	create_index()
