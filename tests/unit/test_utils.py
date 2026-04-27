import os
import tempfile
import pytest
from app.controller.utils import load_html_template


class TestLoadHtmlTemplate:
    def test_loads_existing_template(self, tmp_path):
        t = tmp_path / "page.html"
        t.write_text("<h1>Hello</h1>")
        assert load_html_template(str(t)) == "<h1>Hello</h1>"

    def test_applies_replacements(self, tmp_path):
        t = tmp_path / "page.html"
        t.write_text("<p>{{NAME}}</p>")
        result = load_html_template(str(t), replacements={"NAME": "World"})
        assert result == "<p>World</p>"

    def test_uses_fallback_when_primary_missing(self, tmp_path):
        fallback = tmp_path / "fallback.html"
        fallback.write_text("<p>fallback</p>")
        result = load_html_template("/nonexistent/path.html", fallback_path=str(fallback))
        assert result == "<p>fallback</p>"

    def test_returns_error_message_when_both_missing(self):
        result = load_html_template("/nonexistent/a.html", fallback_path="/nonexistent/b.html")
        assert "Template not found" in result

    def test_returns_error_message_when_no_fallback_given(self):
        result = load_html_template("/nonexistent/path.html")
        assert "Template not found" in result

    def test_multiple_replacements(self, tmp_path):
        t = tmp_path / "page.html"
        t.write_text("{{A}} and {{B}}")
        result = load_html_template(str(t), replacements={"A": "foo", "B": "bar"})
        assert result == "foo and bar"
