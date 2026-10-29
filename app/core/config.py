import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "agentproof.db"))
DEFAULT_DATASET_PATH = BASE_DIR / "data" / "demo_cases.json"
