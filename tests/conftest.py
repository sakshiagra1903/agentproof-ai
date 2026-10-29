import os, tempfile, pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import database

@pytest.fixture()
def client(monkeypatch,tmp_path):
 db=tmp_path/'test.db';monkeypatch.setattr(database,'DATABASE_PATH',str(db));monkeypatch.setattr('app.main.init_db',lambda: database.init_db(str(db)))
 # Route database sessions use configured module-level path; patch config too.
 monkeypatch.setattr('app.db.database.DATABASE_PATH',str(db))
 with TestClient(app) as c: yield c
