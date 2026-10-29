import json, sqlite3
from contextlib import contextmanager
from pathlib import Path
from app.core.config import DATABASE_PATH, DEFAULT_DATASET_PATH


def connect(db_path=None):
    path = str(db_path or DATABASE_PATH)
    if path != ':memory:':
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db(db_path=None):
    conn = connect(db_path)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS datasets (
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
      cases_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
    );
    CREATE TABLE IF NOT EXISTS runs (
      id INTEGER PRIMARY KEY AUTOINCREMENT, dataset_id INTEGER, dataset_name TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
      config_json TEXT NOT NULL, results_json TEXT NOT NULL, summary_json TEXT NOT NULL,
      FOREIGN KEY(dataset_id) REFERENCES datasets(id) ON DELETE SET NULL
    );
    CREATE TABLE IF NOT EXISTS traces (
      id INTEGER PRIMARY KEY AUTOINCREMENT, trace_id TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
      session_id TEXT, metadata_json TEXT NOT NULL DEFAULT '{}', spans_json TEXT NOT NULL,
      status TEXT NOT NULL, duration_ms REAL, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
    );
    CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at);
    CREATE INDEX IF NOT EXISTS idx_traces_created_at ON traces(created_at);
    """)
    count=conn.execute('SELECT COUNT(*) FROM datasets').fetchone()[0]
    if count == 0:
        data=json.loads(DEFAULT_DATASET_PATH.read_text(encoding='utf-8'))
        conn.execute('INSERT INTO datasets(name,description,cases_json) VALUES(?,?,?)',
                     (data['name'],data.get('description',''),json.dumps(data['cases'])))
    conn.commit(); conn.close()

@contextmanager
def db_session(db_path=None):
    conn=connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally: conn.close()
