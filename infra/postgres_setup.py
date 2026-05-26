"""Create the PostgreSQL incidents table used by the API.

Run this once after the PostgreSQL container is up.
"""

from __future__ import annotations

import asyncio
import os

import asyncpg
from dotenv import load_dotenv


load_dotenv()

POSTGRES_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql://postgres:password@localhost:5432/incidentiq",
)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS incidents (
    id VARCHAR(50) PRIMARY KEY,
    service VARCHAR(100) NOT NULL,
    anomaly_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL DEFAULT 'analyzing',
    triggered_by VARCHAR(50) NOT NULL DEFAULT 'manual',
    raw_logs JSONB NOT NULL DEFAULT '[]'::jsonb,
    anomaly_summary TEXT,
    similar_incidents JSONB NOT NULL DEFAULT '[]'::jsonb,
    root_cause TEXT,
    recommended_fix TEXT,
    final_report TEXT,
    agent_trace JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);
"""

CREATE_SERVICE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_incidents_service ON incidents (service);
"""

CREATE_STATUS_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents (status);
"""

CREATE_CREATED_AT_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_incidents_created_at ON incidents (created_at DESC);
"""


async def setup() -> None:
    """Create the incidents table and supporting indexes."""

    connection = await asyncpg.connect(POSTGRES_URL)
    try:
        await connection.execute(CREATE_TABLE_SQL)
        await connection.execute(CREATE_SERVICE_INDEX_SQL)
        await connection.execute(CREATE_STATUS_INDEX_SQL)
        await connection.execute(CREATE_CREATED_AT_INDEX_SQL)
        print("PostgreSQL table 'incidents' ready.")
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(setup())