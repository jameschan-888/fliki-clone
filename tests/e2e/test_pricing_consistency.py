"""Cross-source consistency: PricingPage.tsx PLANS vs app/index.html Plans preview cards."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRICING_PAGE = ROOT / "app" / "src" / "pages" / "PricingPage.tsx"
INDEX_HTML = ROOT / "app" / "index.html"

RE_ID = re.compile(r'id:\s*"([^"]+)"')
RE_NAME = re.compile(r'name:\s*"([^"]+)"')
RE_PRICE = re.compile(r'price:\s*\{\s*monthly:\s*"([^"]+)",\s*annual:\s*"([^"]+)"')
RE_FEATURED = re.compile(r"featured:\s*true")
RE_PLANS_BLOCK = re.compile(r"const PLANS: Plan\[\] = \[((?:.|\n)*?)\n\];")
RE_TEXT = re.compile(r"\btext:")
RE_PREVIEW_SECTION = re.compile(r'<section class="plans-preview"[\s\S]*?</section>')
RE_CARD = re.compile(r'<article class="pp-card([^"]*)"[\s\S]*?</article>')
RE_PPTier = re.compile(r'<div class="pp-tier">([^<]+)</div>')
RE_PPAnnual = re.compile(r'<span class="pp-amt pp-amt-annual[^"]*">(\$[^<]+)</span>')
RE_PPMonthly = re.compile(r'<span class="pp-amt pp-amt-monthly"\s*>(\$[^<]+)</span>')
RE_PPLi = re.compile(r"<li[^>]*>")


def _parse_plans_tsx():
    src = PRICING_PAGE.read_text(encoding="utf-8")
    m = RE_PLANS_BLOCK.search(src)
    assert m, "const PLANS block not found"
    body = m.group(1)
    parts, depth, cur = [], 0, ""
    for ch in body:
        cur += ch
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                parts.append(cur.strip())
                cur = ""
    out = []
    for entry in parts:
        id_m = RE_ID.search(entry)
        name_m = RE_NAME.search(entry)
        price_m = RE_PRICE.search(entry)
        out.append({
            "id": id_m.group(1) if id_m else None,
            "name": name_m.group(1) if name_m else None,
            "monthly": price_m.group(1) if price_m else None,
            "annual": price_m.group(2) if price_m else None,
            "featured": bool(RE_FEATURED.search(entry)),
            "bullets_count": len(RE_TEXT.findall(entry)),
        })
    return out


def _parse_index_cards():
    html = INDEX_HTML.read_text(encoding="utf-8")
    sec = RE_PREVIEW_SECTION.search(html)
    assert sec, "plans-preview section not found"
    sec_text = sec.group(0)
    cards = []
    for art in RE_CARD.finditer(sec_text):
        cls = art.group(1)
        body = art.group(0)
        tier = RE_PPTier.search(body)
        annual = RE_PPAnnual.search(body)
        monthly = RE_PPMonthly.search(body)
        cards.append({
            "name": tier.group(1) if tier else None,
            "annual": annual.group(1) if annual else None,
            "monthly": monthly.group(1) if monthly else None,
            "featured": "featured" in cls,
            "bullets_count": len(RE_PPLi.findall(body)),
        })
    return cards


def test_three_tiers_in_order():
    plans = _parse_plans_tsx()
    cards = _parse_index_cards()
    assert len(plans) == 3, f"PricingPage 期望 3 plans, got {[p['id'] for p in plans]}"
    assert [p["id"] for p in plans] == ["free", "standard", "premium"]
    assert [c["name"] for c in cards] == ["Free", "Standard", "Premium"]


def test_prices_match():
    plans = {p["id"]: p for p in _parse_plans_tsx()}
    cards = _parse_index_cards()
    pairs = [("free", "Free"), ("standard", "Standard"), ("premium", "Premium")]
    expected = [("$0", "$0"), ("$21", "$28"), ("$66", "$88")]
    for (pid, cname), (exp_a, exp_m) in zip(pairs, expected):
        p = plans[pid]
        card = next(c for c in cards if c["name"] == cname)
        assert p["annual"] == card["annual"], f"{cname} annual: page={p['annual']} card={card['annual']}"
        assert p["monthly"] == card["monthly"], f"{cname} monthly: page={p['monthly']} card={card['monthly']}"
        assert card["annual"] == exp_a, f"{cname} 期望 annual {exp_a}, got {card['annual']}"
        assert card["monthly"] == exp_m, f"{cname} 期望 monthly {exp_m}, got {card['monthly']}"


def test_standard_featured_in_both():
    plans = {p["id"]: p for p in _parse_plans_tsx()}
    cards = {c["name"]: c for c in _parse_index_cards()}
    assert plans["standard"]["featured"] is True
    assert cards["Standard"]["featured"] is True
    assert cards["Free"]["featured"] is False
    assert cards["Premium"]["featured"] is False


def test_bullets_count_within_tolerance():
    """Bullets 数量不强求相等, 但每月/年付 toggle 在两处都该 ≥4 项."""
    plans = _parse_plans_tsx()
    cards = _parse_index_cards()
    for p in plans:
        assert p["bullets_count"] >= 4, f"{p['id']}: bullets {p['bullets_count']} < 4"
    for c in cards:
        assert c["bullets_count"] >= 4, f"{c['name']}: bullets {c['bullets_count']} < 4"
