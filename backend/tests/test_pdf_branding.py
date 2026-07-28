"""Canonical LegalLink report layout tests."""

from app.services.pdf import brand_report_html, render_html_to_pdf


def test_branding_wraps_report_once_with_logo_and_standard_sections() -> None:
    source = (
        "<!DOCTYPE html><html><head><title>Test</title></head>"
        "<body><h1>Analyse</h1><table><tr><td>Clause</td></tr></table></body></html>"
    )

    branded = brand_report_html(source)
    second_pass = brand_report_html(branded)

    assert 'data-legallink-brand="1"' in branded
    assert branded.count("legallink-report-header") == 2  # CSS selector + element
    assert "legallink-report-content" in branded
    assert "LegalLink" in branded
    assert 'src="data:image/png;base64,' in branded
    assert "<h1>Analyse</h1>" in branded
    assert second_pass == branded


def test_renderer_outputs_pdf_from_unbranded_html() -> None:
    pdf = render_html_to_pdf("<html><body><h1>Rapport</h1></body></html>")

    assert pdf.startswith(b"%PDF")
