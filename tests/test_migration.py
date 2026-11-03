import json
import os
import sqlite3
import subprocess
import sys

from conftest import SERVER


def test_clean_database_and_v2_rollback(tmp_path):
    database=tmp_path/'fresh.db'
    env={**os.environ,'DATABASE_URL':'sqlite:///'+database.as_posix(),'DEBUG':'false'}
    def migrate(*args):
        result=subprocess.run([sys.executable,'-m','alembic',*args],cwd=SERVER,env=env,capture_output=True,timeout=40)
        assert result.returncode==0,result.stderr.decode(errors='replace')
    migrate('upgrade','head')
    with sqlite3.connect(database) as db:
        db.execute("insert into users(id,nickname) values ('preserved','migration-sample')")
    migrate('downgrade','a8d4e7f9c201')
    with sqlite3.connect(database) as db:
        assert db.execute('select count(*) from users').fetchone()[0]==1
        assert not db.execute("select name from sqlite_master where name='v2_jobs'").fetchall()
    migrate('upgrade','head')
    with sqlite3.connect(database) as db:
        assert db.execute('select count(*) from users').fetchone()[0]==1
        assert db.execute("select name from sqlite_master where name='v2_jobs'").fetchall()
