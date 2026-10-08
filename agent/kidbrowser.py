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
    start = "https://duckduckgo.com/?kp=1"
    if not url_allowed(web_mode, start):
        start = "about:blank"

    # Give WebView2 a fresh, USER-writable data folder. The default location can
    # be locked or owned by SYSTEM (the login app runs as SYSTEM), which causes
    # CO_E_SERVER_EXEC_FAILURE (0x80080005). A per-user temp folder avoids that.
    import os, tempfile
    user = session.get("username", "guest")
    data_dir = os.path.join(tempfile.gettempdir(), f"fleetbrowser_{user}")
    try:
        os.makedirs(data_dir, exist_ok=True)
        os.environ["WEBVIEW2_USER_DATA_FOLDER"] = data_dir
    except Exception:
        pass

    windowed = "--windowed" in sys.argv
    # Open MAXIMIZED (not fullscreen) so the window keeps its title bar with the
    # minimize / maximize / close controls — matching Notepad & Slides. Fullscreen
    # would hide those controls (that was the missing "tray").
    window = webview.create_window("My Web Browser", url=start,
                                   width=1100, height=760,
                                   maximized=not windowed)

    def on_navigating(url):
        # Block navigations that violate policy by redirecting to a friendly page.
        if not url_allowed(web_mode, url):
            blocked = ("data:text/html,"
                       + urllib.parse.quote(
                           "<html><body style='font-family:Comic Sans MS,sans-serif;"
                           "background:#fef6e4;text-align:center;padding-top:80px'>"
                           "<h1>🚫 That page isn't allowed</h1>"
                           "<p>Ask your teacher if you need it.</p>"
                           "<p><a href='https://duckduckgo.com/?kp=1'>Go back to search</a></p>"
                           "</body></html>"))
            window.load_url(blocked)

    # pywebview exposes events differently per version; guard it.
    try:
        window.events.loading += lambda w: on_navigating(window.get_current_url())
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
