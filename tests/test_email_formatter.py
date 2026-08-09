from src.report.email_formatter import markdown_to_email_html


def test_converts_headings():
    html = markdown_to_email_html("# タイトル\n\n## 見出し", title="件名")
    assert "<h1" in html
    assert "タイトル" in html
    assert "<h2" in html
    assert "見出し" in html


def test_converts_tables():
    markdown_text = "| 順位 | コード |\n|---|---|\n| 1 | 7203 |\n"
    html = markdown_to_email_html(markdown_text, title="件名")
    assert "<table" in html
    assert "7203" in html


def test_wraps_in_standalone_html_document():
    html = markdown_to_email_html("本文", title="件名")
    assert html.strip().startswith("<html") or "<html" in html
    assert "件名" in html


def test_uses_inline_friendly_styles_no_external_stylesheet():
    html = markdown_to_email_html("本文", title="件名")
    assert "<link" not in html
    assert "http://" not in html and "https://" not in html
