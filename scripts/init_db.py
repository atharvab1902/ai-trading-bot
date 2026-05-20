"""Initialize SQLite schema. Run once after clone."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from executor import db

if __name__ == "__main__":
    db.init_db()
    print(f"DB initialized at {db.DB_PATH}")
