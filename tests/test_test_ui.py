"""Test-only API UI: route headers, static assets, and simple script safety guardrails."""
import re
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "src" / "static" / "test-ui.js"


async def test_test_ui_page_is_served_with_strict_headers(api):
    response = await api.client.get("/test-ui")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    policy = response.headers["content-security-policy"]
    assert "script-src 'self'" in policy
    assert "form-action 'none'" in policy
    assert "unsafe-inline" not in policy
    assert response.headers["cache-control"] == "no-store"
    assert "Premium Food" in response.text
    assert "SMALL BATCH, GOOD FOOD" in response.text
    assert "/static/test-ui.js" in response.text
    assert "/static/test-ui.css" in response.text
    # No inline scripts or inline handlers: everything must load from /static under the CSP.
    assert not re.search(r"<script(?![^>]*\bsrc=)", response.text)
    assert not re.search(r"\son[a-z]+=", response.text)
    # Forms must never fall back to GET, which would put passwords in the URL.
    assert 'method="get"' not in response.text.lower()


async def test_test_ui_assets_are_served(api):
    for path, content_type in (("/static/test-ui.js", "javascript"), ("/static/test-ui.css", "text/css")):
        response = await api.client.get(path)
        assert response.status_code == 200
        assert content_type in response.headers["content-type"]


async def test_catalog_links_to_test_ui(api):
    response = await api.client.get("/")
    assert 'href="http://test/test-ui"' in response.text


async def test_test_ui_does_not_accept_writes(api):
    response = await api.client.post("/test-ui", data={"password": "not-sent"})
    assert response.status_code == 405


def test_script_keeps_token_in_memory_and_writes_text_only():
    source = re.sub(r"//[^\n]*", "", SCRIPT.read_text(encoding="utf-8"))
    for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write",
                      "localStorage", "sessionStorage", "document.cookie", "eval(", "new Function"):
        assert forbidden not in source, forbidden
    assert "textContent" in source
    assert "[숨김]" in source


def test_invalid_token_clears_auth_state():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "response.status === 401 && sendToken" in source
    assert 'path !== "/v1/auth/login"' in source
