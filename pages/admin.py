# -*- coding: utf-8 -*-
"""
Admin panel — reachable at /admin (Streamlit serves pages/<name>.py there).

Sign in with the admin credentials, then hand out per-account access to the
individual tools. Accounts start with nothing until they are granted here.
"""

import os
import sys
import json
import datetime

import time

import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import studio_auth as auth
import studio_db

st.set_page_config(page_title="Admin · Ecom Studio", page_icon="⚙️",
                   layout="wide", initial_sidebar_state="collapsed")

# Same soft palette as the main app, plus hiding Streamlit's own page list so
# /admin isn't advertised from the main app's sidebar.
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root{
  --ts-bg:#F6F7F9; --ts-surface:#FFFFFF; --ts-surface2:#F4F6F8;
  --ts-border:#E3E7EC; --ts-border-lit:#C9D2DC;
  --ts-text:#212B36; --ts-muted:#637381;
  --ts-cyan:#5C6AC4; --ts-indigo-dark:#4A57B0; --ts-indigo-soft:#EEF0FB;
  --ts-shadow:0 1px 2px rgba(33,43,54,.07), 0 1px 3px rgba(33,43,54,.05);
}
[data-testid="stSidebarNav"]{display:none;}
.stApp{background:var(--ts-bg);}
html,body,.stApp,[class*="css"]{
  font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif!important;
  color:var(--ts-text);}
[data-testid="stHeader"]{background:transparent;}
.block-container{padding-top:2rem;max-width:1280px;}
h1,h2,h3{letter-spacing:-.018em;font-weight:600;color:var(--ts-text);}
h3{font-size:1rem;padding-left:11px;position:relative;margin-top:1.6rem;}
h3::before{content:"";position:absolute;left:0;top:.25em;bottom:.25em;width:3px;
  border-radius:3px;background:var(--ts-cyan);opacity:.55;}
hr{border-color:var(--ts-border);}
.adm-hero{display:flex;align-items:center;gap:16px;padding:20px 24px;margin-bottom:18px;
  border-radius:14px;background:var(--ts-surface);border:1px solid var(--ts-border);
  box-shadow:var(--ts-shadow);}
.adm-mark{width:44px;height:44px;flex:0 0 44px;border-radius:12px;display:grid;
  place-items:center;font-size:21px;background:var(--ts-indigo-soft);border:1px solid #DFE3F7;}
.adm-title{font-size:1.4rem;font-weight:700;margin:0;letter-spacing:-.02em;}
.adm-sub{margin:2px 0 0;color:var(--ts-muted);font-size:.88rem;}
.adm-badge{margin-left:auto;padding:6px 13px;border-radius:999px;font-size:.72rem;
  font-weight:600;letter-spacing:.06em;background:var(--ts-indigo-soft);
  color:var(--ts-cyan);border:1px solid #DFE3F7;}
.stButton>button,.stDownloadButton>button{border-radius:8px;font-weight:500;font-size:.875rem;
  background:var(--ts-surface);color:var(--ts-text);border:1px solid var(--ts-border-lit);
  box-shadow:var(--ts-shadow);}
.stButton>button:hover,.stDownloadButton>button:hover{background:var(--ts-surface2);
  border-color:#AEB9C6;}
.stButton>button[kind="primary"]{background:var(--ts-cyan);color:#fff;
  border:1px solid var(--ts-indigo-dark);font-weight:600;}
.stButton>button[kind="primary"]:hover{background:var(--ts-indigo-dark);color:#fff;}
.stTextInput input,.stTextArea textarea,[data-baseweb="select"]>div{
  background:#fff!important;border:1px solid var(--ts-border-lit)!important;
  border-radius:8px!important;color:var(--ts-text)!important;}
.stTextInput input:focus{border-color:var(--ts-cyan)!important;
  box-shadow:0 0 0 3px rgba(92,106,196,.14)!important;}
[data-testid="stAlert"]{border-radius:10px;border:1px solid var(--ts-border);
  border-left:3px solid var(--ts-cyan);background:#fff;box-shadow:var(--ts-shadow);}
[data-testid="stExpander"]{border:1px solid var(--ts-border);border-radius:10px;
  background:#fff;box-shadow:var(--ts-shadow);}
[data-testid="stMetric"]{background:#fff;border:1px solid var(--ts-border);
  border-radius:10px;padding:12px 15px;box-shadow:var(--ts-shadow);}
[data-testid="stMetricValue"]{color:var(--ts-cyan);font-weight:700;}
code{background:var(--ts-surface2)!important;color:#B4468A!important;
  border:1px solid var(--ts-border);border-radius:5px;padding:1px 5px;font-size:.85em;}
</style>
""", unsafe_allow_html=True)


# ── sign-in gate ────────────────────────────────────────────────────────
db = auth.load_db()

# Same cookie approach as the main app: the component iframe is sandboxed
# without allow-top-navigation, so a redirect can't be used to restore a
# session — a cookie read back via st.context.cookies can.
_ADM_COOKIE = "ecom_studio_admin"


def _adm_cookie():
    try:
        return st.context.cookies.get(_ADM_COOKIE) or ""
    except Exception:
        return ""


def _adm_remember(tok):
    components.html(
        f"<script>try{{window.parent.document.cookie='{_ADM_COOKIE}=' + {tok!r} + "
        f"';path=/;max-age={auth.SESSION_DAYS * 86400};samesite=Lax';}}catch(e){{}}</script>",
        height=0)


def _adm_forget():
    components.html(
        f"<script>try{{window.parent.document.cookie='{_ADM_COOKIE}=;path=/;"
        f"max-age=0;samesite=Lax';}}catch(e){{}}</script>", height=0)


if not st.session_state.get("is_admin"):
    _at = _adm_cookie() or st.query_params.get("admin_token") or ""
    if _at and auth.resolve_token(_at) == "__admin__":
        st.session_state.is_admin = True
        st.session_state.admin_token = _at
        _adm_remember(_at)
        if "admin_token" in st.query_params:
            del st.query_params["admin_token"]
    elif _at:
        auth.revoke_token(_at)
        _adm_forget()
        if "admin_token" in st.query_params:
            del st.query_params["admin_token"]


if not st.session_state.get("is_admin"):
    st.markdown(
        '<div class="adm-hero"><div class="adm-mark">⚙️</div><div>'
        '<h1 class="adm-title">Admin Panel</h1>'
        '<p class="adm-sub">Sign in to manage accounts and tool access.</p>'
        '</div></div>', unsafe_allow_html=True)
    _l, _r = st.columns([1, 1])
    with _l:
        u = st.text_input("Username", key="adm_u")
        p = st.text_input("Password", type="password", key="adm_p")
        if st.button("Sign in", type="primary", key="adm_go", use_container_width=True):
            if auth.authenticate_admin(db, u, p):
                st.session_state.is_admin = True
                _tk = auth.issue_token("__admin__")
                st.session_state.admin_token = _tk
                _adm_remember(_tk)
                time.sleep(0.4)
                st.rerun()
            else:
                st.error("Wrong username or password.")
    with _r:
        st.info(
            "This panel controls who can use the app and which tools they get. "
            "It is application-level access control — it keeps ordinary users out "
            "of each other's tools, but anyone who can reach the server's "
            "filesystem can still read the account file."
        )
    st.stop()


# ── header ──────────────────────────────────────────────────────────────
users = db["users"]
n_total = len(users)
n_active = sum(1 for r in users.values() if r.get("active", True))
n_waiting = sum(1 for r in users.values() if not r.get("permissions"))

st.markdown(
    f'<div class="adm-hero"><div class="adm-mark">⚙️</div><div>'
    f'<h1 class="adm-title">Admin Panel</h1>'
    f'<p class="adm-sub">Signed in as <b>{db["admin"]["username"]}</b> · '
    f'managing {n_total} account(s)</p></div>'
    f'<div class="adm-badge">ADMIN</div></div>', unsafe_allow_html=True)

_m1, _m2, _m3, _m4 = st.columns(4)
_m1.metric("Accounts", n_total)
_m2.metric("Active", n_active)
_m3.metric("Awaiting access", n_waiting)
_m4.metric("Tools", len(auth.TOOL_KEYS))
if n_waiting:
    st.warning(f"⏳ {n_waiting} account(s) have signed up but can't see any tools yet — "
               f"grant them access below.")

_top1, _top2 = st.columns([5, 1])
with _top2:
    if st.button("Sign out", key="adm_out", use_container_width=True):
        auth.revoke_token(st.session_state.get("admin_token")
                          or st.query_params.get("admin_token"))
        st.session_state.is_admin = False
        st.session_state.pop("admin_token", None)
        st.query_params.clear()
        _adm_forget()
        time.sleep(0.4)
        st.rerun()

tab_users, tab_new, tab_bulk, tab_keys, tab_sys = st.tabs(
    ["👥 Accounts & Access", "➕ New Account", "⚡ Bulk Actions", "🔑 API Keys", "🛠️ System"]
)


# ── accounts ────────────────────────────────────────────────────────────
with tab_users:
    if not users:
        st.info("No accounts yet. Create one in **New Account**, or let people sign "
                "up from the main app — they'll appear here with no access until "
                "you grant it.")
    else:
        q = st.text_input("Search by name or email", key="adm_q", placeholder="Type to filter…")
        listing = sorted(users.items())
        if q:
            ql = q.lower()
            listing = [(e, r) for e, r in listing if ql in e or ql in r.get("name", "").lower()]
            st.caption(f"{len(listing)} match(es)")

        for email, rec in listing:
            granted = [k for k in auth.TOOL_KEYS if k in rec.get("permissions", [])]
            state = ("🚫 suspended" if not rec.get("active", True)
                     else ("⏳ no access yet" if not granted
                           else f"✅ {len(granted)} tool(s)"))
            with st.expander(f"**{rec.get('name','—')}** · {email} — {state}", expanded=False):
                st.caption(
                    f"Created {rec.get('created','—')} · "
                    f"last sign-in {rec.get('last_login') or 'never'}"
                )

                tpl = st.selectbox(
                    "Apply a template", ["— keep current —"] + list(auth.PERMISSION_TEMPLATES),
                    key=f"tpl_{email}",
                )
                base = (auth.PERMISSION_TEMPLATES[tpl]
                        if tpl in auth.PERMISSION_TEMPLATES else rec.get("permissions", []))

                st.markdown("**Tools this account can use**")
                cols = st.columns(4)
                picked = []
                for i, key in enumerate(auth.TOOL_KEYS):
                    with cols[i % 4]:
                        on = st.checkbox(auth.TOOL_LABELS[key], value=key in base,
                                         key=f"perm_{email}_{key}")
                        if on:
                            picked.append(key)
                        if not db["tools_enabled"].get(key, True):
                            st.caption("⚠️ off globally")

                a1, a2, a3, a4 = st.columns(4)
                if a1.button("💾 Save access", key=f"save_{email}",
                             type="primary", use_container_width=True):
                    db["users"][email]["permissions"] = picked
                    auth.save_db(db)
                    st.success(f"{rec.get('name')} now has {len(picked)} tool(s).")
                    st.rerun()

                if a2.button("🚫 Suspend" if rec.get("active", True) else "✅ Reactivate",
                             key=f"act_{email}", use_container_width=True):
                    db["users"][email]["active"] = not rec.get("active", True)
                    auth.save_db(db)
                    if not db["users"][email]["active"]:
                        auth.revoke_all_for(email)     # kick them out now
                    st.rerun()

                with a3.popover("🔑 Reset password", use_container_width=True):
                    npw = st.text_input("New password", type="password", key=f"pw_{email}")
                    if st.button("Set it", key=f"pwgo_{email}"):
                        ok, msg = auth.set_password(db, email, npw)
                        if ok:
                            auth.save_db(db)
                            n = auth.revoke_all_for(email)
                            st.success(msg + (f" Signed out {n} device(s)." if n else ""))
                        else:
                            st.error(msg)

                with a4.popover("🗑️ Delete", use_container_width=True):
                    st.warning(f"Permanently delete **{email}**?")
                    if st.button("Yes, delete", key=f"del_{email}"):
                        db["users"].pop(email, None)
                        auth.save_db(db)
                        auth.revoke_all_for(email)
                        st.rerun()


# ── new account ─────────────────────────────────────────────────────────
with tab_new:
    st.markdown("### Create an account manually")
    c1, c2 = st.columns(2)
    n_name = c1.text_input("Full name", key="new_name")
    n_mail = c2.text_input("Email", key="new_mail", placeholder="person@example.com")
    c3, c4 = st.columns(2)
    n_pw = c3.text_input("Password", type="password", key="new_pw")
    n_tpl = c4.selectbox("Starting access", list(auth.PERMISSION_TEMPLATES), index=0,
                         key="new_tpl",
                         help="Default is no access — you can grant tools right after.")

    st.markdown("**Or pick the tools directly**")
    _c = st.columns(4)
    chosen = []
    for i, key in enumerate(auth.TOOL_KEYS):
        with _c[i % 4]:
            if st.checkbox(auth.TOOL_LABELS[key],
                           value=key in auth.PERMISSION_TEMPLATES[n_tpl],
                           key=f"new_perm_{key}"):
                chosen.append(key)

    if st.button("➕ Create account", type="primary", key="new_go", use_container_width=True):
        ok, msg = auth.create_user(db, n_mail, n_name, n_pw, chosen)
        if ok:
            auth.save_db(db)
            st.success(f"{msg} {n_mail} can sign in now with "
                       f"{len(chosen)} tool(s) available.")
        else:
            st.error(msg)


# ── bulk ────────────────────────────────────────────────────────────────
with tab_bulk:
    if not users:
        st.info("No accounts yet.")
    else:
        st.markdown("### Grant or revoke a tool for several accounts at once")
        b1, b2 = st.columns(2)
        who = b1.multiselect("Accounts", sorted(users),
                             format_func=lambda e: f"{users[e].get('name','—')} ({e})",
                             key="bulk_who")
        what = b2.multiselect("Tools", auth.TOOL_KEYS,
                              format_func=lambda k: auth.TOOL_LABELS[k], key="bulk_what")
        g1, g2 = st.columns(2)
        if g1.button("✅ Grant to selected", type="primary",
                     key="bulk_grant", use_container_width=True,
                     disabled=not (who and what)):
            for e in who:
                perms = set(users[e].get("permissions", [])) | set(what)
                db["users"][e]["permissions"] = [k for k in auth.TOOL_KEYS if k in perms]
            auth.save_db(db)
            st.success(f"Granted {len(what)} tool(s) to {len(who)} account(s).")
            st.rerun()
        if g2.button("🚫 Revoke from selected", key="bulk_revoke",
                     use_container_width=True, disabled=not (who and what)):
            for e in who:
                perms = set(users[e].get("permissions", [])) - set(what)
                db["users"][e]["permissions"] = [k for k in auth.TOOL_KEYS if k in perms]
            auth.save_db(db)
            st.success(f"Revoked {len(what)} tool(s) from {len(who)} account(s).")
            st.rerun()


# ── API keys ────────────────────────────────────────────────────────────
with tab_keys:
    st.markdown("### Keys the tools run on")
    st.caption("Stored in the account file on this machine — never committed to git. "
               "On Streamlit Cloud the filesystem resets on redeploy, so there use "
               "**Settings → Secrets** instead.")
    k1, k2 = st.columns(2)
    groq = k1.text_input("Groq API key — 🗣️ Saudi Voice", type="password",
                         value=db["api"].get("groq_api_key", ""), key="k_groq")
    serp = k2.text_input("SerpAPI key — 🔍 Find Similar", type="password",
                         value=db["api"].get("serpapi_key", ""), key="k_serp")
    lg, sg = auth.api_key(db, "groq_api_key", "GROQ_API_KEY")
    ls, ss = auth.api_key(db, "serpapi_key", "SERPAPI_KEY")
    st.caption(f"Groq: {'✅ active via ' + sg if lg else '❌ not set'} · "
               f"SerpAPI: {'✅ active via ' + ss if ls else '❌ not set'}")
    if st.button("💾 Save keys", type="primary", key="k_save"):
        db["api"]["groq_api_key"] = groq.strip()
        db["api"]["serpapi_key"] = serp.strip()
        auth.save_db(db)
        st.success("Saved.")
        st.rerun()


# ── system ──────────────────────────────────────────────────────────────
with tab_sys:
    st.markdown("### Tools available app-wide")
    st.caption("A tool switched off here disappears for everyone, whatever their "
               "individual access says.")
    _c = st.columns(4)
    newly = {}
    for i, key in enumerate(auth.TOOL_KEYS):
        with _c[i % 4]:
            newly[key] = st.checkbox(auth.TOOL_LABELS[key],
                                     value=db["tools_enabled"].get(key, True),
                                     key=f"glob_{key}")
    if st.button("💾 Save", type="primary", key="glob_save"):
        db["tools_enabled"] = newly
        auth.save_db(db)
        st.success("Saved.")
        st.rerun()

    st.markdown("### Open access (/all)")
    _oa = db["settings"].get("open_access_enabled", True)
    st.warning(
        "**/all lets anyone use every tool with no sign-in.** Whoever has the "
        "link can spend your Groq and SerpAPI credit, and permissions do not "
        "apply there. Only share it with people you would have given full "
        "access to anyway."
    ) if _oa else st.info("/all is currently switched off.")
    _oa_new = st.toggle("Enable /all", value=_oa, key="oa_on")
    if st.button("💾 Save open access", type="primary", key="oa_save"):
        db["settings"]["open_access_enabled"] = _oa_new
        auth.save_db(db)
        st.success("Saved.")
        st.rerun()

    st.markdown("### Sign-ups")
    allow = st.toggle("Let people create their own account from the main app",
                      value=db["settings"].get("allow_signup", True), key="sg_allow")
    msg = st.text_area("What a new account sees before you grant access",
                       value=db["settings"].get("signup_message", ""), key="sg_msg", height=90)
    if st.button("💾 Save sign-up settings", type="primary", key="sg_save"):
        db["settings"]["allow_signup"] = allow
        db["settings"]["signup_message"] = msg
        auth.save_db(db)
        st.success("Saved.")
        st.rerun()

    st.markdown("### Admin credentials")
    a1, a2, a3 = st.columns(3)
    au = a1.text_input("Username", value=db["admin"]["username"], key="ad_u")
    ap = a2.text_input("New password", type="password", key="ad_p")
    ap2 = a3.text_input("Confirm", type="password", key="ad_p2")
    if st.button("💾 Update admin login", key="ad_save"):
        if not au.strip():
            st.error("The username can't be empty.")
        elif ap and ap != ap2:
            st.error("The two passwords don't match.")
        else:
            db["admin"]["username"] = au.strip()
            if ap:
                salt, h = auth.hash_password(ap)
                db["admin"].update(salt=salt, hash=h)
            auth.save_db(db)
            st.success("Updated." + ("" if ap else " (password unchanged)"))
            st.rerun()

    st.markdown("### Where accounts are stored")
    _be, _why = studio_db.describe()
    if _be == "file":
        st.error(
            "⚠️ **No database connected.** " + _why + "  \n"
            "This is why the accounts disappeared — they were only ever in a file "
            "inside the container."
        )
        with st.expander("Connect a free permanent database (5 minutes)", expanded=True):
            st.markdown(
                "1. Create a free project at **[neon.tech](https://neon.tech)** or "
                "**[supabase.com](https://supabase.com)** — both have a free tier "
                "that is plenty for this.\n"
                "2. Copy the **connection string** they give you. It looks like "
                "`postgresql://user:password@host/dbname`.\n"
                "3. On Streamlit Cloud open your app → **Settings → Secrets** and "
                "add the line below, then save. The app restarts and the accounts "
                "live in the database from then on — surviving sleeps, restarts "
                "and redeploys."
            )
            st.code('DATABASE_URL = "postgresql://user:password@host/dbname"',
                    language="toml")
            st.caption("Whatever accounts exist when you connect it are copied into "
                       "the database automatically on the first load.")
    else:
        _ok, _msg = studio_db.healthy()
        if _ok:
            st.success(f"✅ **{_be}** — {_why}")
        else:
            st.error(f"❌ **{_be}** configured but unreachable: {_msg}  \n"
                     f"The app is running on the local file until it comes back, "
                     f"so nothing is lost right now — but fix this before relying on it.")

    st.markdown("### Snapshot into Secrets (no signup needed)")
    st.caption(
        "Streamlit Secrets survive redeploys, so pasting your accounts there "
        "makes them come back automatically whenever the container is rebuilt. "
        "It is read-only, so re-paste after adding people — or connect "
        "DATABASE_URL above and it happens by itself."
    )
    _snap = json.dumps(db, ensure_ascii=False, separators=(",", ":"))
    _seeded = bool(studio_db.seed_from_secrets())
    st.caption("ACCOUNTS_JSON currently in Secrets: "
               + ("yes" if _seeded else "no")
               + f" · snapshot is {len(_snap)/1024:.1f} KB, "
                 f"{len(db['users'])} account(s)")
    with st.expander("Show the line to paste into Settings → Secrets"):
        _q = "'''"
        st.code("ACCOUNTS_JSON = " + _q + _snap + _q, language="toml")
        st.caption("Copy the whole block including the triple quotes. It holds "
                   "password hashes and API keys — treat it like a password.")

    st.markdown("### Staying signed in")
    if auth.secret_is_persistent():
        st.success("✅ `AUTH_SECRET` is configured — sign-ins survive restarts and redeploys.")
    else:
        st.warning(
            "⚠️ No `AUTH_SECRET` set, so the signing key is regenerated whenever the "
            "app restarts — everyone gets signed out. Fix it by adding a line like "
            "this under **Settings → Secrets** on Streamlit Cloud (any long random "
            "string works):"
        )
        st.code(f'AUTH_SECRET = "{__import__("secrets").token_urlsafe(32)}"', language="toml")
        st.caption("Locally you can export it instead: "
                   "`export AUTH_SECRET=\"...\"` before running the app.")

    st.markdown("### Backup & restore")
    st.download_button(
        "⬇️ Download backup (contains hashes and keys — keep it private)",
        data=json.dumps(db, indent=2, ensure_ascii=False).encode("utf-8"),
        file_name=f"studio_users_{datetime.datetime.now():%Y%m%d_%H%M}.json",
        mime="application/json", key="bk_dl", use_container_width=True,
    )
    up = st.file_uploader("Restore from a backup", type=["json"], key="bk_up")
    if up and st.button("♻️ Restore", key="bk_go"):
        try:
            auth.save_db(json.loads(up.getvalue().decode("utf-8")))
            st.success("Restored.")
            st.rerun()
        except Exception as e:
            st.error(f"Couldn't read that file: {e}")
