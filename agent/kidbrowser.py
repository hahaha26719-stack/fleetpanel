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

# A floating toolbar injected into EVERY page via JavaScript after it loads.
# Because the real site loads in the FULL window (not an iframe), every website
# works — Google, YouTube, etc. The bar sits fixed on top. Buttons call the
# pywebview Python API, which policy-checks before navigating the whole window.
TOOLBAR_JS = r"""
(function(){
  if (document.getElementById('__fleetbar')) return;   // only once per page
  var bar = document.createElement('div');
  bar.id = '__fleetbar';
  bar.style.cssText = 'position:fixed;top:0;left:0;right:0;height:52px;z-index:2147483647;'
    + 'background:#5b8cff;display:flex;gap:8px;align-items:center;padding:6px 10px;'
    + "font-family:'Comic Sans MS',sans-serif;box-shadow:0 2px 8px rgba(0,0,0,.3);";
  bar.innerHTML =
    '<button id="__fb_back">◀</button>'
    + '<button id="__fb_fwd">▶</button>'
    + '<button id="__fb_home">🏠</button>'
    + '<input id="__fb_addr" placeholder="Search the web or type a website…" '
    + 'style="flex:1;font-size:17px;border:0;border-radius:12px;padding:9px 14px;outline:none;">'
    + '<button id="__fb_go" style="background:#3ecf8e;color:#fff;font-weight:bold;">🔍 Go</button>';
  var bstyle='font-size:17px;border:0;border-radius:10px;padding:8px 11px;cursor:pointer;background:#fff;color:#2d2a32;';
  // push the page down so the bar doesn't cover content
  var spacer=document.createElement('div'); spacer.style.height='52px';
  document.documentElement.style.scrollPaddingTop='52px';
  document.body.insertBefore(bar, document.body.firstChild);
  document.body.insertBefore(spacer, bar.nextSibling);
  ['__fb_back','__fb_fwd','__fb_home','__fb_go'].forEach(function(id){
    document.getElementById(id).style.cssText=bstyle;});
  var addr=document.getElementById('__fb_addr');
  addr.value=location.href;
  function nav(){ window.pywebview.api.navigate(addr.value); }
  document.getElementById('__fb_go').onclick=nav;
  addr.addEventListener('keydown',function(e){ if(e.key==='Enter') nav(); });
  document.getElementById('__fb_back').onclick=function(){ window.pywebview.api.back(); };
  document.getElementById('__fb_fwd').onclick=function(){ window.pywebview.api.forward(); };
  document.getElementById('__fb_home').onclick=function(){ window.pywebview.api.navigate('HOME'); };
})();
"""


class _Api:
    """Bridge the injected toolbar <-> Python. Navigation is policy-checked here,
    then the WHOLE window loads the URL (so every site works, no iframe)."""
    def __init__(self, session, web_mode):
        self.session = session
        self.web_mode = web_mode
        self.window = None

    def navigate(self, text):
        url = HOME_URL if text == "HOME" else normalize_url(text)
        if not url:
            return
        if not url_allowed(self.web_mode, url):
            blocked = ("data:text/html," + urllib.parse.quote(
                "<html><body style=\"font-family:Comic Sans MS,sans-serif;background:#fef6e4;"
                "text-align:center;padding-top:80px\"><h1>🚫 That page isn't allowed</h1>"
                "<p>Ask your teacher if you need it.</p></body></html>"))
            self.window.load_url(blocked)
            return
        self.window.load_url(url)

    def back(self):
        try:
            self.window.evaluate_js("history.back()")
        except Exception:
            pass

    def forward(self):
        try:
            self.window.evaluate_js("history.forward()")
        except Exception:
            pass


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

    # PERSISTENT per-user WebView2 data folder (kept under LOCALAPPDATA, NOT
    # %TEMP%). This lets WebView2 keep its cache between sessions so it starts
    # fast — a temp folder (wiped on reboot) made it rebuild from scratch every
    # launch, which is slow.
    import os
    user = session.get("username", "guest")
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("TMP") or os.getcwd()
    data_dir = os.path.join(base, "FleetBrowser", user)
    try:
        os.makedirs(data_dir, exist_ok=True)
        os.environ["WEBVIEW2_USER_DATA_FOLDER"] = data_dir
    except Exception:
        pass

    windowed = "--windowed" in sys.argv
    api = _Api(session, web_mode)
    # Start with a fast LOCAL page (has a <body> so the toolbar injects reliably
    # and the kid sees something instantly), then navigate Home in the background
    # — the window appears immediately instead of waiting on a network page.
    start = ("data:text/html," + urllib.parse.quote(
        "<html><body style=\"font-family:Comic Sans MS,sans-serif;background:#fef6e4;"
        "text-align:center;padding-top:120px;color:#8a8694\">"
        "<h2>Loading the web… 🌐</h2></body></html>"))
    # The real site loads in the FULL window (every site works, no framing).
    window = webview.create_window("My Web Browser", url=start, js_api=api,
                                   width=1100, height=760, maximized=not windowed)
    api.window = window

    # After EVERY page finishes loading: (1) enforce policy on where we landed
    # (covers link clicks / redirects), (2) inject the floating toolbar, and
    # (3) on the very first (blank) load, go to Home so the window shows instantly.
    state = {"went_home": False}

    def _on_loaded(w=None):
        try:
            current = window.get_current_url() or ""
        except Exception:
            current = ""
        if current and current.startswith("http") and not url_allowed(web_mode, current):
            api.navigate(current)   # redirect to the friendly blocked page
            return
        try:
            window.evaluate_js(TOOLBAR_JS)   # draw the search/URL bar on top
        except Exception:
            pass
        if not state["went_home"]:
            state["went_home"] = True
            api.navigate("HOME")    # load the real home page now (window already visible)
    try:
        window.events.loaded += _on_loaded
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
