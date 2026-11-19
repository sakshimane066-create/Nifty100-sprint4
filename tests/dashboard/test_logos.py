from unittest.mock import patch

from src.dashboard.utils import logos


def test_domain_of():
    assert logos.domain_of("https://www.tcs.com/") == "tcs.com"
    assert logos.domain_of("sbi.co.in/about") == "sbi.co.in"
    assert logos.domain_of(None) is None and logos.domain_of(float("nan")) is None


def test_badge_is_deterministic_svg():
    a, b = logos.badge_svg("HDFCBANK"), logos.badge_svg("HDFCBANK")
    assert a == b and a.startswith("<svg") and "HDF" in a
    assert logos.badge_svg("M&M").count("<text") == 1


def test_logo_falls_back_to_badge_when_nothing_loads():
    with patch.object(logos, "fetch_image", return_value=None):
        out = logos.logo_for("SBIN", "https://sbi.co.in", "https://mkt.in/x.png")
    assert isinstance(out, str) and out.startswith("<svg")


def test_logo_prefers_website_favicon_then_source():
    calls = []

    def fake(url):
        calls.append(url)
        return b"x" * 400 if "google.com" in url else None
    with patch.object(logos, "fetch_image", side_effect=fake):
        assert logos.logo_for("TCS", "https://www.tcs.com", "https://src/x.png") == b"x" * 400
    assert "domain=tcs.com" in calls[0] and len(calls) == 1


def test_shared_source_url_is_skipped():
    seen = []
    with patch.object(logos, "fetch_image", side_effect=lambda u: seen.append(u)):
        logos.logo_for("NHPC", None, "https://mkt.in/HEROMOTOCO.png", source_is_unique=False)
    assert seen == []


def test_table_exists_helper(conn):
    from src.dashboard.utils.db import table_exists

    assert table_exists("financial_ratios") and not table_exists("no_such_table")
