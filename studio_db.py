# -*- coding: utf-8 -*-
"""
Where Ecom Studio keeps its accounts.

The problem this solves
-----------------------
Accounts used to live in studio_users.json inside the container. Streamlit
Cloud hands back a fresh container whenever the app sleeps or redeploys, so
that file — every account, permission and API key — disappeared. This module
puts the same data somewhere that outlives the container.

Backends, chosen automatically:
  * postgres  — when DATABASE_URL is set (Supabase, Neon, Railway…). This is
                the one that actually survives; use it in production.
  * sqlite    — when DATABASE_URL is a sqlite:// url. Real file, real SQL,
                fine for a machine you control.
  * file      — plain JSON. The local default, and the fallback if a database
                is configured but unreachable, so the app never hard-fails on
                a connection blip.

The whole state is one JSON document in one row. At the scale this app runs
at — tens of accounts — that is far simpler than a normalised schema and
keeps writes atomic. Last write wins; there is no row-level merging.
"""

import os
import json
import datetime

_TABLE = "studio_state"
_ROW_ID = 1


# ── which backend ───────────────────────────────────────────────────────
def _url():
    """DATABASE_URL from Streamlit secrets, then the environment."""
    try:
        import streamlit as st
        v = st.secrets.get("DATABASE_URL", "") or ""
        if v:
            return v.strip()
    except Exception:
        pass
    return (os.environ.get("DATABASE_URL", "") or "").strip()


def backend():
    u = _url()
    if not u:
        return "file"
    if u.startswith("sqlite:"):
        return "sqlite"
    if u.startswith(("postgres://", "postgresql://")):
        return "postgres"
    return "file"


def describe():
    """(backend, human explanation) for the admin panel."""
    b = backend()
    if b == "postgres":
        host = _url().split("@")[-1].split("/")[0] if "@" in _url() else "configured"
        return b, f"PostgreSQL at {host} — accounts survive restarts and redeploys."
    if b == "sqlite":
        return b, f"SQLite file at {_sqlite_path()} — survives restarts on this machine."
    return b, ("Local JSON file. Fine on your own computer, but on Streamlit "
               "Cloud the filesystem is wiped on every redeploy and whenever "
               "the app sleeps, so accounts will not survive.")


def _sqlite_path():
    u = _url()
    return u.replace("sqlite:///", "").replace("sqlite://", "") or "studio.db"


# ── connections ─────────────────────────────────────────────────────────
def _connect():
    """Returns (connection, paramstyle_placeholder) or raises."""
    b = backend()
    if b == "postgres":
        import psycopg2
        return psycopg2.connect(_url(), connect_timeout=10), "%s"
    if b == "sqlite":
        import sqlite3
        return sqlite3.connect(_sqlite_path(), timeout=10), "?"
    raise RuntimeError("no database configured")


def _ensure_table(cur):
    # Plain TEXT rather than JSONB so the identical statement works on both
    # Postgres and SQLite — which is what lets the SQL path be tested locally.
    cur.execute(
        f"CREATE TABLE IF NOT EXISTS {_TABLE} ("
        f"  id INTEGER PRIMARY KEY,"
        f"  data TEXT NOT NULL,"
        f"  updated_at TEXT NOT NULL)"
    )


def healthy():
    """Can we actually reach the configured database right now?"""
    if backend() == "file":
        return False, "no database configured"
    try:
        conn, _ = _connect()
        try:
            cur = conn.cursor()
            _ensure_table(cur)
            conn.commit()
            return True, "connected"
        finally:
            conn.close()
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:160]}"


# ── the two operations the app needs ────────────────────────────────────
FILE_PATH = os.environ.get("STUDIO_USERS_DB", "studio_users.json")


def _file_load():
    try:
        with open(FILE_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _file_save(state):
    tmp = FILE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, FILE_PATH)
    try:
        os.chmod(FILE_PATH, 0o600)
    except Exception:
        pass


def load_state():
    """Whole state dict, or None when nothing has been stored yet."""
    if backend() == "file":
        return _file_load()
    try:
        conn, _ph = _connect()
        try:
            cur = conn.cursor()
            _ensure_table(cur)
            cur.execute(f"SELECT data FROM {_TABLE} WHERE id = {_ROW_ID}")
            row = cur.fetchone()
            conn.commit()
            if row and row[0]:
                return json.loads(row[0])
            # first run against an empty database — adopt whatever the local
            # file has so an existing setup carries over instead of resetting
            seeded = _file_load()
            if seeded:
                save_state(seeded)
                return seeded
            return None
        finally:
            conn.close()
    except Exception:
        return _file_load()      # unreachable database must not take the app down


def save_state(state):
    """Persist, and mirror to the local file as a cheap always-there backup."""
    if backend() != "file":
        try:
            conn, ph = _connect()
            try:
                cur = conn.cursor()
                _ensure_table(cur)
                payload = json.dumps(state, ensure_ascii=False)
                now = datetime.datetime.now().isoformat()
                if backend() == "postgres":
                    cur.execute(
                        f"INSERT INTO {_TABLE} (id, data, updated_at) "
                        f"VALUES ({ph}, {ph}, {ph}) "
                        f"ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data, "
                        f"updated_at = EXCLUDED.updated_at",
                        (_ROW_ID, payload, now))
                else:
                    cur.execute(
                        f"INSERT INTO {_TABLE} (id, data, updated_at) "
                        f"VALUES ({ph}, {ph}, {ph}) "
                        f"ON CONFLICT(id) DO UPDATE SET data = excluded.data, "
                        f"updated_at = excluded.updated_at",
                        (_ROW_ID, payload, now))
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass                 # fall through to the file so nothing is lost
    try:
        _file_save(state)
    except Exception:
        pass
