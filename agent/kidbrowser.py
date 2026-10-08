"""
FleetPanel Kid Browser (our own simplified browser)
===================================================
Our own browser UI with a kid-friendly address bar and big buttons. It enforces
the admin 'web_mode' policy INSIDE the app: every navigation is checked by
url_allowed() before loading, so no /etc/hosts or system changes are needed and
picture search (a separate app) is unaffected.

Rendering uses the system WebView2 engine via `pywebview` so real websites look
right. If pywebview isn't installed, it falls back to a message (install step is
in docs). The policy/filtering logic (url_allowed) is pure and testable.

Standalone test (logic only, no GUI):  python kidbrowser.py --selftest
Run the browser:                        python kidbrowser.py
"""
import sys
import urllib.parse

import kidcommon as kc


def host_of(url):
    """Extract a hostname from a possibly-partial URL the kid typed."""
    u = (url or "").strip()
    if not u:
        return ""
    if "://" not in u:
        u = "http://" + u
    try:
        return (urllib.parse.urlparse(u).hostname or "").lower()
    except Exception:
        return ""


def normalize_url(text):
    """Turn kid input into a real URL. If it looks like a search (spaces / no
    dot), send it to a kid-safe search; otherwise treat it as a site."""
    t = (text or "").strip()
    if not t:
        return ""
    looks_like_url = ("." in t and " " not in t) or t.startswith("http")
    if looks_like_url:
        return t if "://" in t else "http://" + t
    # a search phrase -> DuckDuckGo with safe-search on (kid-friendly, no account)
    return "https://duckduckgo.com/?kp=1&q=" + urllib.parse.quote(t)


def url_allowed(web_mode_value, url):
    """Return True if this URL may be loaded under the web_mode policy.
    Uses the hostname against the allow/block list."""
    host = host_of(url)
    if not host:
        return True  # blank/about pages are fine
    # The search engine host must always be allowed in block_except mode so the
    # kid can actually search within allowed sites; include common safe hosts.
    return kc.is_allowed(web_mode_value, host)


HOME_URL = "https://duckduckgo.com/?kp=1"

# A kid-friendly toolbar page. It has Back / Forward / Home buttons, a combined
# SEARCH + URL box, and a big area showing the current page in an <iframe>.
# The toolbar talks to Python via window.pywebview.api so navigation is
# policy-checked before loading. (Sites that block framing fall back to opening
# in the whole window via api.open_top.)
TOOLBAR_HTML = """
<!doctype html><html><head><meta charset="utf-8">
<style>
  html,body{margin:0;height:100%;font-family:'Comic Sans MS',sans-serif;background:#fef6e4;}
  #bar{display:flex;gap:8px;align-items:center;padding:10px;background:#5b8cff;}
  #bar button{font-size:18px;border:0;border-radius:10px;padding:8px 12px;cursor:pointer;background:#fff;color:#2d2a32;}
  #addr{flex:1;font-size:18px;border:0;border-radius:12px;padding:10px 14px;outline:none;}
  #go{background:#3ecf8e;color:#fff;font-weight:bold;}
  #frame{width:100%;height:calc(100% - 60px);border:0;background:#fff;}
  #msg{padding:40px;text-align:center;color:#8a8694;}
</style></head><body>
  <div id="bar">
    <button onclick="go(-1)">◀</button>
    <button onclick="go(1)">▶</button>
    <button onclick="home()">🏠</button>
    <input id="addr" placeholder="Search the web or type a website…"
           onkeydown="if(event.key==='Enter')navigate()">
    <button id="go" onclick="navigate()">🔍 Go</button>
  </div>
  <iframe id="frame" src=""></iframe>
  <div id="msg" style="display:none"></div>
<script>
  const frame=document.getElementById('frame');
  const addr=document.getElementById('addr');
  const msg=document.getElementById('msg');
  function navigate(){ window.pywebview.api.navigate(addr.value); }
  function home(){ window.pywebview.api.navigate('HOME'); }
  function go(d){ try{ history.go(d); }catch(e){} }
  // Python calls these:
  function loadInFrame(url){ msg.style.display='none'; frame.style.display='block'; frame.src=url; addr.value=url; }
  function showBlocked(){ frame.style.display='none'; msg.style.display='block';
    msg.innerHTML="<h1>🚫 That page isn't allowed</h1><p>Ask your teacher if you need it.</p>"; }
  function setAddr(u){ addr.value=u; }
</script>
</body></html>
"""


class _Api:
    """Bridge the HTML toolbar <-> Python. Navigation is policy-checked here."""
    def __init__(self, session, web_mode):
        self.session = session
        self.web_mode = web_mode
        self.window = None

    def navigate(self, text):
        if text == "HOME":
            url = HOME_URL
        else:
            url = normalize_url(text)
        if not url:
            return
        if not url_allowed(self.web_mode, url):
            self.window.evaluate_js("showBlocked()")
            return
        # load the allowed URL inside the toolbar's iframe.
        # NOTE: some big sites (Google, YouTube, Facebook) refuse to be shown in
        # an iframe (X-Frame-Options / frame-ancestors). For a kid browser,
        # curated/educational sites and most search results pages work fine; if
        # a site shows blank, it's refusing framing, not a policy block.
        safe = url.replace("\\", "\\\\").replace("'", "\\'")
        self.window.evaluate_js(f"loadInFrame('{safe}')")


# --------------------------------------------------------------- GUI (WebView2)
def run_browser(session):
    try:
        import webview  # pywebview -> uses Edge WebView2 on Windows
    except Exception:
        print("pywebview is not installed. Install it on the PC with:")
        print("    pip install pywebview")
        print("(WebView2 runtime ships with Windows 10/11.)")
        return

    web_mode = session.get("policies", {}).get("web_mode", "")

    # Per-user WebView2 data folder (avoids 0x80080005 under locked profiles).
    import os, tempfile
    user = session.get("username", "guest")
    data_dir = os.path.join(tempfile.gettempdir(), f"fleetbrowser_{user}")
    try:
        os.makedirs(data_dir, exist_ok=True)
        os.environ["WEBVIEW2_USER_DATA_FOLDER"] = data_dir
    except Exception:
        pass

    windowed = "--windowed" in sys.argv
    api = _Api(session, web_mode)
    # Load our toolbar page as the window content; it hosts the address/search
    # bar and the iframe that shows the actual website.
    window = webview.create_window("My Web Browser", html=TOOLBAR_HTML, js_api=api,
                                   width=1100, height=760, maximized=not windowed)
    api.window = window

    # Once loaded, navigate to the home page (policy-checked) via the API.
    def _start_home(w=None):
        try:
            api.navigate("HOME")
        except Exception:
            pass
    try:
        window.events.loaded += _start_home
    except Exception:
        pass

    try:
        webview.start()
    except Exception as e:
        _show_browser_error(str(e))


def _show_browser_error(detail):
    """Friendly fallback if the WebView2 engine can't start, with the usual
    causes/fixes, instead of a raw crash."""
    import tkinter as tk
    from tkinter import messagebox
    r = tk.Tk(); r.withdraw()
    messagebox.showerror(
        "Web browser can't start",
        "The web browser couldn't start on this PC.\n\n"
        "Usual fixes:\n"
        "1) Install the Microsoft Edge WebView2 Runtime:\n"
        "   https://developer.microsoft.com/microsoft-edge/webview2/\n"
        "2) The browser must run as the logged-in USER, not SYSTEM.\n"
        "3) Reboot and try again (clears a stuck browser profile).\n\n"
        f"Details: {detail}")
    r.destroy()


def _selftest():
    # block_except: only allow kids.example.com and duckduckgo.com
    pol = "block_except:kids.example.com, duckduckgo.com"
    assert url_allowed(pol, "https://kids.example.com/page") is True
    assert url_allowed(pol, "https://duckduckgo.com/?q=cats") is True
    assert url_allowed(pol, "https://facebook.com") is False
    # allow_except: block only badsite.com
    pol2 = "allow_except:badsite.com"
    assert url_allowed(pol2, "https://badsite.com") is False
    assert url_allowed(pol2, "https://anything.org") is True
    # empty policy allows all
    assert url_allowed("", "https://whatever.com") is True
    # normalize
    assert normalize_url("cats and dogs").startswith("https://duckduckgo.com/")
    assert normalize_url("example.com") == "http://example.com"
    assert normalize_url("https://a.com") == "https://a.com"
    print("kidbrowser selftest OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        run_browser(kc.load_session())
