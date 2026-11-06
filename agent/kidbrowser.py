"""
FleetBrowser - permanent browser toolbar with tabs (no webpage injection).

Install:
    pip install PySide6 PySide6-WebEngine pywebview

Run through FleetPanel:
    from kidbrowser import run_browser
    run_browser(kc.load_session())

Or test directly:
    python kidbrowser.py

This version uses Qt WebEngine for the browser UI because pywebview does not
provide an embeddable multi-tab browser surface. The toolbar and tab strip are
native Python/Qt widgets, outside the website.
"""

import os
import sys
import urllib.parse

import kidcommon as kc

from PySide6.QtCore import QUrl, Qt, QStandardPaths
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QLineEdit,
    QPushButton,
    QLabel,
    QProgressBar,
    QMessageBox,
)
from PySide6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
)
from PySide6.QtWebEngineWidgets import QWebEngineView


HOME_URL = "https://duckduckgo.com/?kp=1"


def host_of(url):
    text = (url or "").strip()
    if not text:
        return ""
    if "://" not in text:
        text = "https://" + text
    return (urllib.parse.urlparse(text).hostname or "").lower()


def normalize_url(text):
    text = (text or "").strip()
    if not text:
        return ""
    if text.startswith(("http://", "https://")):
        return text
    if " " not in text and "." in text:
        return "https://" + text
    return "https://duckduckgo.com/?kp=1&q=" + urllib.parse.quote(text)


def url_allowed(web_mode_value, url):
    host = host_of(url)
    if not host:
        return True
    return kc.is_allowed(web_mode_value, host)


class FleetPage(QWebEnginePage):
    """A page that checks top-level navigation and routes popups into tabs."""

    def __init__(self, profile, browser, view):
        super().__init__(profile, view)
        self.browser = browser

    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        if is_main_frame:
            address = url.toString()
            if address.startswith(("http://", "https://")):
                if not url_allowed(self.browser.web_mode, address):
                    self.browser.show_blocked(address)
                    return False
        return super().acceptNavigationRequest(url, navigation_type, is_main_frame)

    def createWindow(self, window_type):
        # target="_blank", window.open(), and popup links open as a new tab.
        return self.browser.create_tab(make_current=True).page()


class BrowserTab(QWidget):
    def __init__(self, browser):
        super().__init__()
        self.browser = browser
        self.view = QWebEngineView(self)
        self.page = FleetPage(browser.profile, browser, self.view)
        self.view.setPage(self.page)

        settings = self.page.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

        self.page.urlChanged.connect(lambda url: browser.tab_url_changed(self, url))
        self.page.titleChanged.connect(lambda title: browser.tab_title_changed(self, title))
        self.view.loadProgress.connect(browser.set_progress)


class FleetBrowser(QMainWindow):
    def __init__(self, session):
        super().__init__()
        self.session = session or {}
        self.web_mode = self.session.get("policies", {}).get("web_mode", "")
        self.setWindowTitle("FleetBrowser")
        self.resize(1200, 800)

        # Keep one browser profile so cookies/cache are shared between tabs.
        data_root = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppLocalDataLocation
        )
        profile_dir = os.path.join(data_root or os.path.expanduser("~"), "FleetBrowser")
        os.makedirs(profile_dir, exist_ok=True)
        self.profile = QWebEngineProfile("FleetBrowser", self)
        self.profile.setPersistentStoragePath(profile_dir)
        self.profile.setCachePath(os.path.join(profile_dir, "Cache"))

        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Permanent native toolbar - it is not part of the loaded webpage.
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 8, 8, 8)
        toolbar.setSpacing(6)

        self.back_button = QPushButton("←")
        self.forward_button = QPushButton("→")
        self.home_button = QPushButton("⌂")
        self.refresh_button = QPushButton("↻")
        for button in (self.back_button, self.forward_button,
                       self.home_button, self.refresh_button):
            button.setFixedWidth(42)
            button.setMinimumHeight(36)
            toolbar.addWidget(button)

        self.address = QLineEdit()
        self.address.setPlaceholderText("Search or enter a website")
        self.address.setClearButtonEnabled(True)
        self.address.setMinimumHeight(36)
        toolbar.addWidget(self.address, 1)

        self.go_button = QPushButton("Go")
        self.go_button.setMinimumHeight(36)
        toolbar.addWidget(self.go_button)

        root.addLayout(toolbar)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.current_tab_changed)
        root.addWidget(self.tabs, 1)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(8, 3, 8, 5)
        self.status = QLabel("Ready")
        self.progress = QProgressBar()
        self.progress.setFixedWidth(130)
        self.progress.setFixedHeight(8)
        self.progress.setTextVisible(False)
        bottom.addWidget(self.status, 1)
        bottom.addWidget(self.progress)
        root.addLayout(bottom)

        self.setCentralWidget(central)

        self.back_button.clicked.connect(lambda: self.current_view_action("back"))
        self.forward_button.clicked.connect(lambda: self.current_view_action("forward"))
        self.home_button.clicked.connect(self.go_home)
        self.refresh_button.clicked.connect(lambda: self.current_view_action("reload"))
        self.go_button.clicked.connect(self.navigate_address)
        self.address.returnPressed.connect(self.navigate_address)

        new_tab_action = QAction(self)
        new_tab_action.setShortcut(QKeySequence("Ctrl+T"))
        new_tab_action.triggered.connect(lambda: self.create_tab(make_current=True))
        self.addAction(new_tab_action)

        close_tab_action = QAction(self)
        close_tab_action.setShortcut(QKeySequence("Ctrl+W"))
        close_tab_action.triggered.connect(
            lambda: self.close_tab(self.tabs.currentIndex())
        )
        self.addAction(close_tab_action)

        self.create_tab(make_current=True, url=HOME_URL)

    def create_tab(self, make_current=True, url="about:blank"):
        tab = BrowserTab(self)
        index = self.tabs.addTab(tab, "New tab")
        if make_current:
            self.tabs.setCurrentIndex(index)
        if url and url != "about:blank":
            tab.view.setUrl(QUrl(url))
        return tab

    def current_tab(self):
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, BrowserTab) else None

    def current_view_action(self, action):
        tab = self.current_tab()
        if not tab:
            return
        if action == "back":
            tab.view.back()
        elif action == "forward":
            tab.view.forward()
        elif action == "reload":
            tab.view.reload()

    def navigate_address(self):
        tab = self.current_tab()
        if not tab:
            return
        address = normalize_url(self.address.text())
        if not url_allowed(self.web_mode, address):
            self.show_blocked(address)
            return
        tab.view.setUrl(QUrl(address))

    def go_home(self):
        tab = self.current_tab()
        if tab:
            tab.view.setUrl(QUrl(HOME_URL))

    def show_blocked(self, address):
        host = host_of(address) or address
        html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Website blocked</title></head>
<body style="font-family:Segoe UI,Arial;text-align:center;padding:70px;background:#f5f6fa;color:#222">
<h1>Website blocked</h1>
<p><b>{host}</b> is not on the allowed list.</p>
<p>Please ask your teacher if you need access.</p>
</body></html>"""
        tab = self.current_tab()
        if tab:
            tab.view.setHtml(html, QUrl("https://fleetbrowser.local/"))

    def tab_url_changed(self, tab, url):
        if tab is self.current_tab():
            self.address.setText(url.toString())
            self.back_button.setEnabled(tab.view.history().canGoBack())
            self.forward_button.setEnabled(tab.view.history().canGoForward())

    def tab_title_changed(self, tab, title):
        index = self.tabs.indexOf(tab)
        if index >= 0:
            clean = (title or "New tab").strip()
            self.tabs.setTabText(index, clean[:22] + ("…" if len(clean) > 22 else ""))
            self.tabs.setTabToolTip(index, clean)

    def current_tab_changed(self, index):
        tab = self.current_tab()
        if not tab:
            self.address.clear()
            return
        self.address.setText(tab.view.url().toString())
        self.back_button.setEnabled(tab.view.history().canGoBack())
        self.forward_button.setEnabled(tab.view.history().canGoForward())

    def set_progress(self, value):
        self.progress.setValue(value)
        self.progress.setVisible(value < 100)
        self.status.setText("Loading…" if value < 100 else "Ready")

    def close_tab(self, index):
        if index < 0:
            return
        tab = self.tabs.widget(index)
        self.tabs.removeTab(index)
        if tab:
            tab.deleteLater()
        if self.tabs.count() == 0:
            self.create_tab(make_current=True, url=HOME_URL)


def run_browser(session):
    app = QApplication.instance() or QApplication(sys.argv)
    window = FleetBrowser(session)
    window.show()
    app.exec()


def _selftest():
    assert normalize_url("example.com") == "https://example.com"
    assert normalize_url("https://example.com") == "https://example.com"
    assert normalize_url("cats and dogs").startswith("https://duckduckgo.com/")
    assert host_of("https://example.com/path") == "example.com"
    print("FleetBrowser self-test OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        run_browser(kc.load_session())
