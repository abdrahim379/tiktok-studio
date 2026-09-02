# -*- coding: utf-8 -*-
"""
Shared accounts + permissions for Ecom Studio.

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

import studio_db

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
                     "open_access_enabled": True,
                     "signup_message": "Your account has been created. An "
                                       "administrator needs to grant you access "
                                       "to the tools before you can use them."},
    }


def load_db():
    """Whole config, from whichever backend studio_db selected."""
    cfg = default_db()
    saved = studio_db.load_state()
    if saved:
        for section, value in saved.items():
            if isinstance(value, dict) and isinstance(cfg.get(section), dict):
                cfg[section].update(value)
            else:
                cfg[section] = value
    for k in TOOL_KEYS:                        # a tool added later defaults to on
        cfg["tools_enabled"].setdefault(k, True)
    return cfg


def save_db(db):
    studio_db.save_state(db)


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


# ── staying signed in ───────────────────────────────────────────────────
# Tokens are SIGNED, not stored. An earlier version kept them in a JSON file,
# which fails on hosts that recycle the filesystem: Streamlit Cloud hands back
# a fresh container after the app sleeps, the file vanishes, and every token
# stops resolving — i.e. everyone gets logged out.
#
# A signed token carries its own identity and expiry and is verified with an
# HMAC, so validating it needs no disk at all. Keep AUTH_SECRET in
# st.secrets (those survive redeploys) and sessions survive refresh, restart,
# sleep/wake and redeploy alike.
#
# Trade-off, stated plainly: without a store there is no perfect revocation.
# Revoked tokens are remembered best-effort in a small file, so if that file
# is wiped a revoked token works again until it expires. Expiry is the real
# backstop, which is why it is days rather than months.
import base64

SESSION_FILE = os.environ.get("STUDIO_SESSIONS_DB", "studio_sessions.json")
SESSION_DAYS = 30
_SECRET_CACHE = []


def auth_secret():
    """Stable signing key. st.secrets first — that is what survives redeploys."""
    if _SECRET_CACHE:
        return _SECRET_CACHE[0]
    val = ""
    try:
        import streamlit as st
        val = st.secrets.get("AUTH_SECRET", "") or ""
    except Exception:
        val = ""
    val = val or os.environ.get("AUTH_SECRET", "")
    if not val:
        # fall back to one persisted alongside the accounts, then to a random
        # per-process key (which means sign-outs on restart — the admin panel
        # flags this so it can be fixed by setting AUTH_SECRET).
        try:
            db = load_db()
            val = db.get("settings", {}).get("auth_secret", "")
            if not val:
                val = secrets.token_urlsafe(32)
                db.setdefault("settings", {})["auth_secret"] = val
                save_db(db)
        except Exception:
            val = secrets.token_urlsafe(32)
    _SECRET_CACHE.append(val)
    return val


def secret_is_persistent():
    """True when AUTH_SECRET comes from somewhere that survives a redeploy."""
    try:
        import streamlit as st
        if st.secrets.get("AUTH_SECRET", ""):
            return True
    except Exception:
        pass
    return bool(os.environ.get("AUTH_SECRET", ""))


def _b64e(raw):
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(txt):
    return base64.urlsafe_b64decode(txt + "=" * (-len(txt) % 4))


def _sign(payload_b64):
    return _b64e(hmac.new(auth_secret().encode(), payload_b64.encode(),
                          hashlib.sha256).digest())


def issue_token(identity, epoch=None):
    """`epoch` stamps the account's revocation counter into the token so a
    later suspension invalidates it without needing any stored session."""
    if epoch is None:
        try:
            rec = load_db()["users"].get(normalise_email(identity), {})
            epoch = rec.get("token_epoch", 0)
        except Exception:
            epoch = 0
    exp = (datetime.datetime.now() +
           datetime.timedelta(days=SESSION_DAYS)).timestamp()
    body = _b64e(json.dumps({"i": identity, "e": int(exp), "ep": int(epoch),
                             "n": secrets.token_hex(6)}).encode())
    return f"{body}.{_sign(body)}"


def resolve_token(tok):
    if not tok or "." not in tok:
        return None
    body, sig = tok.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sign(body)):
        return None                                  # forged or wrong secret
    try:
        data = json.loads(_b64d(body))
    except Exception:
        return None
    if datetime.datetime.now().timestamp() > float(data.get("e", 0)):
        return None
    if data.get("n") in _revoked():
        return None
    return data.get("i")


def _revoked():
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as fh:
            return set(json.load(fh).get("revoked", []))
    except Exception:
        return set()


def _write_revoked(nonces):
    try:
        tmp = SESSION_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"revoked": sorted(nonces)[-5000:]}, fh)
        os.replace(tmp, SESSION_FILE)
        os.chmod(SESSION_FILE, 0o600)
    except Exception:
        pass


def revoke_token(tok):
    if not tok or "." not in tok:
        return
    try:
        data = json.loads(_b64d(tok.rsplit(".", 1)[0]))
    except Exception:
        return
    n = data.get("n")
    if n:
        _write_revoked(_revoked() | {n})


def revoke_all_for(identity):
    """Suspension/deletion: bump the account's epoch so its tokens stop working."""
    db = load_db()
    rec = db["users"].get(normalise_email(identity))
    if rec is None:
        return 0
    rec["token_epoch"] = rec.get("token_epoch", 0) + 1
    save_db(db)
    return 1


def token_still_good(db, identity, tok):
    """Second check the app makes: the account exists, is active, and its
    epoch hasn't moved since this token was handed out."""
    rec = db["users"].get(normalise_email(identity))
    if not rec or not rec.get("active", True):
        return False
    try:
        issued_epoch = json.loads(_b64d(tok.rsplit(".", 1)[0])).get("ep", 0)
    except Exception:
        issued_epoch = 0
    return issued_epoch >= rec.get("token_epoch", 0)
