import json
import sqlite3
import threading
import time
from pathlib import Path
from contextlib import contextmanager


class Database:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self._busy_timeout_ms = 10000
        self.init()

    def conn(self):
        # Every connection gets the same SQLite concurrency policy. WAL lets
        # the dashboard read while the AI/hardware workers write, while the
        # busy timeout prevents transient writer contention from surfacing as
        # HTTP 500 errors.
        c = sqlite3.connect(
            self.path,
            timeout=self._busy_timeout_ms / 1000.0,
            check_same_thread=False,
        )
        c.row_factory = sqlite3.Row
        c.execute(f"PRAGMA busy_timeout={self._busy_timeout_ms}")
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        return c

    @contextmanager
    def write_conn(self):
        # SQLite permits one writer at a time. Serialize writes inside this
        # process so concurrent AI/event/hardware workers never fight over
        # the same database connection. WAL still allows readers concurrently.
        with self.lock:
            c = self.conn()
            try:
                yield c
                c.commit()
            except Exception:
                c.rollback()
                raise
            finally:
                c.close()

    def init(self):
        with self.conn() as c:
            c.execute("PRAGMA foreign_keys=ON")
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS people(
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    identifier TEXT,
                    role TEXT DEFAULT '',
                    access_level TEXT DEFAULT 'STANDARD',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS face_samples(
                    id INTEGER PRIMARY KEY,
                    person_id INTEGER NOT NULL,
                    image BLOB NOT NULL,
                    created_at REAL NOT NULL,
                    FOREIGN KEY(person_id) REFERENCES people(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS events(
                    id INTEGER PRIMARY KEY,
                    ts REAL NOT NULL,
                    person_id INTEGER,
                    identity TEXT,
                    confidence REAL,
                    authorized INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    camera_id TEXT DEFAULT 'CAM-01',
                    camera_name TEXT DEFAULT 'Main Entrance',
                    snapshot_path TEXT,
                    face_snapshot_path TEXT,
                    correlation_id TEXT,
                    details TEXT
                );
                CREATE TABLE IF NOT EXISTS hardware_devices(
                    device_id TEXT PRIMARY KEY,
                    device_type TEXT NOT NULL,
                    driver TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    zone TEXT DEFAULT 'MAIN_ENTRANCE',
                    configuration TEXT DEFAULT '{}',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS hardware_commands(
                    id INTEGER PRIMARY KEY,
                    command_id TEXT UNIQUE NOT NULL,
                    correlation_id TEXT,
                    ts REAL NOT NULL,
                    device_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    requested_state TEXT,
                    actual_state TEXT,
                    result TEXT NOT NULL,
                    error TEXT,
                    details TEXT
                );
                CREATE TABLE IF NOT EXISTS hardware_events(
                    id INTEGER PRIMARY KEY,
                    ts REAL NOT NULL,
                    correlation_id TEXT,
                    device_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    previous_state TEXT,
                    new_state TEXT,
                    details TEXT
                );
                CREATE TABLE IF NOT EXISTS access_events(
                    id INTEGER PRIMARY KEY,
                    ts REAL NOT NULL,
                    correlation_id TEXT,
                    reader_id TEXT,
                    door_id TEXT,
                    person_id INTEGER,
                    identity TEXT,
                    credential_ref TEXT,
                    authorized INTEGER NOT NULL,
                    decision TEXT NOT NULL,
                    details TEXT
                );
                """
            )
            self._add_column(c, "people", "role", "TEXT DEFAULT ''")
            self._add_column(c, "people", "access_level", "TEXT DEFAULT 'STANDARD'")
            self._add_column(c, "events", "camera_id", "TEXT DEFAULT 'CAM-01'")
            self._add_column(c, "events", "camera_name", "TEXT DEFAULT 'Main Entrance'")
            self._add_column(c, "events", "snapshot_path", "TEXT")
            self._add_column(c, "events", "face_snapshot_path", "TEXT")
            self._add_column(c, "events", "correlation_id", "TEXT")

    @staticmethod
    def _add_column(conn, table, column, definition):
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def add_person(self, name, identifier='', role='', access_level='STANDARD'):
        with self.write_conn() as c:
            cur = c.execute(
                'INSERT INTO people(name,identifier,role,access_level,created_at) VALUES(?,?,?,?,?)',
                (name, identifier, role, access_level, time.time()),
            )
            return cur.lastrowid

    def list_people(self):
        with self.conn() as c:
            return [dict(r) for r in c.execute(
                'SELECT id,name,identifier,role,access_level,enabled,created_at FROM people ORDER BY name'
            )]

    def get_person(self, person_id):
        with self.conn() as c:
            row = c.execute('SELECT * FROM people WHERE id=?', (person_id,)).fetchone()
            return dict(row) if row else None

    def set_person_enabled(self, person_id, enabled):
        with self.write_conn() as c:
            c.execute('UPDATE people SET enabled=? WHERE id=?', (int(bool(enabled)), person_id))

    def add_sample(self, pid, img):
        with self.write_conn() as c:
            c.execute(
                'INSERT INTO face_samples(person_id,image,created_at) VALUES(?,?,?)',
                (pid, img, time.time()),
            )

    def samples(self):
        with self.conn() as c:
            return [dict(r) for r in c.execute('SELECT person_id,image FROM face_samples')]

    def event(self, identity, confidence, authorized, event_type='recognition', person_id=None,
              details=None, camera_id='CAM-01', camera_name='Main Entrance',
              snapshot_path=None, face_snapshot_path=None, correlation_id=None):
        with self.write_conn() as c:
            cur = c.execute(
                '''INSERT INTO events(
                    ts,person_id,identity,confidence,authorized,event_type,
                    camera_id,camera_name,snapshot_path,face_snapshot_path,correlation_id,details
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                (
                    time.time(), person_id, identity, confidence, int(authorized), event_type,
                    camera_id, camera_name, snapshot_path, face_snapshot_path, correlation_id,
                    json.dumps(details or {}),
                ),
            )
            return cur.lastrowid

    def upsert_hardware_device(self, device_id, device_type, driver, enabled=True, zone='MAIN_ENTRANCE', configuration=None):
        now = time.time()
        with self.write_conn() as c:
            c.execute(
                '''INSERT INTO hardware_devices(device_id,device_type,driver,enabled,zone,configuration,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(device_id) DO UPDATE SET device_type=excluded.device_type,driver=excluded.driver,enabled=excluded.enabled,zone=excluded.zone,configuration=excluded.configuration,updated_at=excluded.updated_at''',
                (device_id, device_type, driver, int(bool(enabled)), zone, json.dumps(configuration or {}), now, now),
            )

    def hardware_command(self, command_id, correlation_id, device_id, action, requested_state=None, actual_state=None, result='SUCCESS', error=None, details=None, timestamp=None):
        with self.write_conn() as c:
            c.execute(
                'INSERT OR REPLACE INTO hardware_commands(command_id,correlation_id,ts,device_id,action,requested_state,actual_state,result,error,details) VALUES(?,?,?,?,?,?,?,?,?,?)',
                (command_id, correlation_id, timestamp or time.time(), device_id, action, requested_state, actual_state, result, error, json.dumps(details or {})),
            )

    def hardware_event(self, device_id, event_type, previous_state=None, new_state=None, correlation_id=None, details=None):
        with self.write_conn() as c:
            cur = c.execute(
                'INSERT INTO hardware_events(ts,correlation_id,device_id,event_type,previous_state,new_state,details) VALUES(?,?,?,?,?,?,?)',
                (time.time(), correlation_id, device_id, event_type, previous_state, new_state, json.dumps(details or {})),
            )
            return cur.lastrowid

    def hardware_commands(self, limit=100, device_id=None):
        q='SELECT * FROM hardware_commands WHERE 1=1'; params=[]
        if device_id:
            q+=' AND device_id=?'; params.append(device_id)
        q+=' ORDER BY ts DESC LIMIT ?'; params.append(max(1,min(int(limit),1000)))
        with self.conn() as c: rows=[dict(r) for r in c.execute(q,params)]
        for r in rows:
            try:r['details']=json.loads(r.get('details') or '{}')
            except (TypeError,ValueError):r['details']={}
        return rows

    def hardware_events(self, limit=100, device_id=None):
        q='SELECT * FROM hardware_events WHERE 1=1'; params=[]
        if device_id:
            q+=' AND device_id=?'; params.append(device_id)
        q+=' ORDER BY ts DESC LIMIT ?'; params.append(max(1,min(int(limit),1000)))
        with self.conn() as c: rows=[dict(r) for r in c.execute(q,params)]
        for r in rows:
            try:r['details']=json.loads(r.get('details') or '{}')
            except (TypeError,ValueError):r['details']={}
        return rows

    def access_event(self, reader_id, door_id, identity, authorized, decision, person_id=None, credential_ref=None, correlation_id=None, details=None):
        with self.write_conn() as c:
            cur=c.execute(
                'INSERT INTO access_events(ts,correlation_id,reader_id,door_id,person_id,identity,credential_ref,authorized,decision,details) VALUES(?,?,?,?,?,?,?,?,?,?)',
                (time.time(),correlation_id,reader_id,door_id,person_id,identity,credential_ref,int(bool(authorized)),decision,json.dumps(details or {})),
            )
            return cur.lastrowid

    def events(self, limit=100, person=None, camera=None, authorization=None, search=None):
        query = 'SELECT * FROM events WHERE 1=1'
        params = []
        if person:
            query += ' AND identity LIKE ?'
            params.append(f'%{person}%')
        if camera:
            query += ' AND camera_name=?'
            params.append(camera)
        if authorization in ('authorized', 'unauthorized'):
            query += ' AND authorized=?'
            params.append(1 if authorization == 'authorized' else 0)
        if search:
            query += ' AND (identity LIKE ? OR camera_name LIKE ? OR event_type LIKE ?)'
            params.extend([f'%{search}%'] * 3)
        query += ' ORDER BY ts DESC LIMIT ?'
        params.append(max(1, min(int(limit), 1000)))
        with self.conn() as c:
            rows = [dict(r) for r in c.execute(query, params)]
        for row in rows:
            try:
                row['details'] = json.loads(row.get('details') or '{}')
            except (TypeError, ValueError):
                row['details'] = {}
        return rows
