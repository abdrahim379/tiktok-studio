# -*- coding: utf-8 -*-
"""
/all — every tool, no sign-in.

Streamlit serves pages/<name>.py at /<name>, so this file is the whole route.

It runs the main script rather than duplicating it, passing ECOM_OPEN_ACCESS
through the exec globals. That detail matters: an environment variable or a
module-level global is shared by every session in the process, so a single
visit here would have switched authentication off on / for everyone. Exec
globals are created fresh for each run, so the bypass stays scoped to this
page.

set_page_config is left to the main script — calling it here as well would
raise, since Streamlit only allows it once per run.

Anyone with this link gets every tool, including the ones that spend Groq and
SerpAPI credit. The admin panel can switch it off (System → Open access).
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_MAIN = os.path.join(_ROOT, "tiktok_studio.py")

with open(_MAIN, "r", encoding="utf-8") as _fh:
    _code = compile(_fh.read(), _MAIN, "exec")

_globals = {
    "__name__": "__main__",
    "__file__": _MAIN,
    "ECOM_OPEN_ACCESS": True,
}
exec(_code, _globals)
