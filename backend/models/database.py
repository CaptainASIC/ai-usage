"""
Database initialization and connection management using aiosqlite.
Stores provider configurations and cached balance snapshots.
"""

import aiosqlite
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "tracker.db"


def get_db():
    """Get a database connection as an async context manager."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return aiosqlite.connect(str(DB_PATH))


async def init_db():
    """Initialize database schema."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS provider_configs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                auth_type TEXT NOT NULL,
                credentials TEXT NOT NULL DEFAULT '{}',
                refresh_interval INTEGER NOT NULL DEFAULT 300,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS balance_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_id TEXT NOT NULL,
                balance_usd REAL,
                total_credits REAL,
                used_credits REAL,
                remaining_credits REAL,
                currency TEXT NOT NULL DEFAULT 'USD',
                raw_data TEXT,
                status TEXT NOT NULL DEFAULT 'ok',
                error_message TEXT,
                fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (provider_id) REFERENCES provider_configs(id)
            )
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshots_provider_time
            ON balance_snapshots(provider_id, fetched_at DESC)
        """)

        await db.commit()
        logger.info("Database initialized successfully")
