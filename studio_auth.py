# -*- coding: utf-8 -*-
"""
Shared accounts + permissions for TikTok Studio.

Used by the main app (tiktok_studio.py) and the admin panel (pages/admin.py).

Design notes
------------
* A brand-new account gets an EMPTY permission list on purpose. Until the
  admin grants tools, the user signs in and sees a "waiting for access"
  screen. That is the requested behaviour, not a bug.
* Passwords are PBKDF2-HMAC-SHA256 with a per-user salt. That protects the
  stored file; it is not a substitute for real infrastructure security.
* Everything lives in one JSON file so it can be backed up and restored from
  the admin panel. The file holds password hashes and API keys, so it is
  gitignored and chmod 600.
"""

import json
import os
import hashlib
import hmac
import secrets
import datetime

DB_FILE = os.environ.get("STUDIO_USERS_DB", "studio_users.json")

# The tools the admin can hand out. Keys must match the main app's tab keys.
TOOL_REGISTRY = [
    ("downloader",   "📥 TikTok Downloader"),
    ("variants",     "🎛️ Variant Generator"),
    ("metadata",     "🔄 Refresh Metadata"),
    ("find_similar", "🔍 Find Similar"),
    ("audio",        "🎵 Extract Audio"),
    ("text",         "📝 Extract Text"),
    ("design",       "🎨 Design Studio"),
    ("voice",        "🗣️ Saudi Voice"),
]
TOOL_KEYS = [k for k, _ in TOOL_REGISTRY]
TOOL_LABELS = dict(TOOL_REGISTRY)

# Ready-made bundles so the admin doesn't tick eight boxes every time.
PERMISSION_TEMPLATES = {
    "No access (default)": [],
    "Variants only":       ["variants"],
    "Creator":             ["downloader", "variants", "metadata"],
    "Editor":              ["design", "audio", "text", "voice"],
    "Full access":         list(TOOL_KEYS),
}

_PBKDF2_ROUNDS = 200_000


# ── password hashing ────────────────────────────────────────────────────
def hash_password(password, salt=None):
    """Return (salt_hex, hash_hex) for a password."""
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                             bytes.fromhex(salt), _PBKDF2_ROUNDS)
    return salt, dk.hex()


def verify_password(password, salt, expected_hash):
    if not salt or not expected_hash:
        return False
    _, got = hash_password(password, salt)
    return hmac.compare_digest(got, expected_hash)


# ── storage ─────────────────────────────────────────────────────────────
def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def default_db():
    salt, pw = hash_password("ADMIN")
    return {
        "admin": {"username": "ADMIN", "salt": salt, "hash": pw},
        "users": {},                      # email -> record
        "api": {"groq_api_key": "", "serpapi_key": ""},
        "tools_enabled": {k: True for k in TOOL_KEYS},   # global kill-switch
        "settings": {"allow_signup": True,
                     "signup_message": "Your account has been created. An "
                                       "administrator needs to grant you access "
                                       "to the tools before you can use them."},
    }


def load_db():
    db = default_db()
    try:
        with open(DB_FILE, "r", encoding="utf-8") as fh:
            saved = json.load(fh)
        for section, value in saved.items():
            if isinstance(value, dict) and isinstance(db.get(section), dict):
                db[section].update(value)
            else:
                db[section] = value
    except Exception:
        pass                                   # first run or unreadable -> defaults
    for k in TOOL_KEYS:                        # a tool added later defaults to on
        db["tools_enabled"].setdefault(k, True)
    return db


def save_db(db):
    tmp = DB_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(db, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, DB_FILE)
    try:
        os.chmod(DB_FILE, 0o600)               # it holds hashes and API keys
    except Exception:
        pass


# ── accounts ────────────────────────────────────────────────────────────
def normalise_email(email):
    return (email or "").strip().lower()


def create_user(db, email, name, password, permissions=None):
    """Returns (ok, message). New accounts get no tools unless told otherwise."""
    email = normalise_email(email)
    if not email or "@" not in email:
        return False, "Enter a valid email address."
    if email in db["users"]:
        return False, "An account with that email already exists."
    if len(password or "") < 6:
        return False, "The password must be at least 6 characters."
    salt, pw = hash_password(password)
    db["users"][email] = {
        "name": (name or "").strip() or email.split("@")[0],
        "salt": salt,
        "hash": pw,
        "permissions": list(permissions or []),
        "active": True,
        "created": _now(),
        "last_login": None,
    }
    return True, "Account created."


def set_password(db, email, password):
    email = normalise_email(email)
    if email not in db["users"]:
        return False, "No such account."
    if len(password or "") < 6:
        return False, "The password must be at least 6 characters."
    salt, pw = hash_password(password)
    db["users"][email].update(salt=salt, hash=pw)
    return True, "Password updated."


def authenticate(db, email, password):
    """Returns (ok, record_or_None, message)."""
    email = normalise_email(email)
    rec = db["users"].get(email)
    if not rec:
        return False, None, "Wrong email or password."
    if not verify_password(password, rec.get("salt"), rec.get("hash")):
        return False, None, "Wrong email or password."
    if not rec.get("active", True):
        return False, None, "This account has been suspended. Contact the administrator."
    rec["last_login"] = _now()
    return True, rec, "Signed in."


def authenticate_admin(db, username, password):
    a = db.get("admin", {})
    if (username or "").strip().upper() != str(a.get("username", "ADMIN")).upper():
        return False
    return verify_password(password, a.get("salt"), a.get("hash"))


def allowed_tools(db, email):
    """Tools this account can actually see: granted AND globally enabled."""
    rec = db["users"].get(normalise_email(email))
    if not rec or not rec.get("active", True):
        return []
    granted = set(rec.get("permissions", []))
    return [k for k in TOOL_KEYS if k in granted and db["tools_enabled"].get(k, True)]


# ── API keys ────────────────────────────────────────────────────────────
def api_key(db, name, *env_names):
    """Admin panel value wins, then st.secrets, then the environment."""
    v = db.get("api", {}).get(name, "")
    if v:
        return v, "admin panel"
    try:
        import streamlit as st
        for src in env_names:
            try:
                v = st.secrets.get(src, "")
            except Exception:
                v = ""
            if v:
                return v, "secrets"
    except Exception:
        pass
    for src in env_names:
        v = os.environ.get(src, "")
        if v:
            return v, "environment"
    return "", "none"


# ── sign-in that survives a page refresh ────────────────────────────────
# Streamlit clears session_state on reload, which would sign everyone out on
# every refresh. We hand the browser an opaque token in the URL and keep the
# email server-side, so the URL never carries a password.
_SESSIONS = {}
_SESSION_HOURS = 12


def issue_token(identity):
    tok = secrets.token_urlsafe(24)
    _SESSIONS[tok] = (identity, datetime.datetime.now())
    return tok


def resolve_token(tok):
    entry = _SESSIONS.get(tok or "")
    if not entry:
        return None
    identity, issued = entry
    if (datetime.datetime.now() - issued).total_seconds() > _SESSION_HOURS * 3600:
        _SESSIONS.pop(tok, None)
        return None
    return identity


def revoke_token(tok):
    _SESSIONS.pop(tok or "", None)
