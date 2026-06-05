# tests/test_web_assets.py
from pathlib import Path

WEB = Path("web")
HTML = WEB / "index.html"
JS = WEB / "app.js"
CSS = WEB / "style.css"


def test_html_exists_and_wires_assets():
    assert HTML.exists()
    html = HTML.read_text(encoding="utf-8")
    assert '<script src="/static/app.js"></script>' in html
    assert 'href="/static/style.css"' in html
    for el_id in ("chat", "msg", "chat-form",
                  "card-insights", "card-recs", "card-alerts",
                  "trace", "trace-toggle"):
        assert f'id="{el_id}"' in html, f"missing id={el_id} in index.html"


def test_app_js_posts_to_chat_and_renders_trace():
    assert JS.exists()
    js = JS.read_text(encoding="utf-8")
    assert "/api/chat" in js
    assert "fetch(" in js
    assert "plan_trace" in js
    for el_id in ("card-insights", "card-recs", "card-alerts"):
        assert el_id in js
    assert "web-session" in js


def test_css_non_empty():
    assert CSS.exists()
    assert CSS.read_text(encoding="utf-8").strip()
