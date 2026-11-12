"""Initialize the SQLite database.

Usage:
    python scripts/init_db.py
    # or:
    make init-db
"""
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ielts_ai.config import get_settings
from ielts_ai.db.repo import init_db


def main() -> None:
    """Initialize the database."""
    settings = get_settings()
    schema_path = str(Path(__file__).parent.parent / "src" / "ielts_ai" / "db" / "schema.sql")
    init_db(settings.db_path, schema_path)
    print(f"Database initialized at: {settings.db_path}")


if __name__ == "__main__":
    main()
