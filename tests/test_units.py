import random
from decimal import Decimal

from ifs_migration.datagen import catalog
from ifs_migration.itemspec import item_key, key_complete, parse_item_description, standard_description
from ifs_migration.money import cents_str, ext_cents, money, parse_decimal, to_cents
from ifs_migration.textnorm import normalize_company_name, normalize_taxid, parse_date


def test_money_is_exact_and_rounds_half_up():
    assert parse_decimal("$1,234.5") == Decimal("1234.5")
    assert parse_decimal("(5.00)") == Decimal("-5.00")
    assert parse_decimal("abc") is None and parse_decimal("") is None
    assert to_cents(Decimal("12.345")) == 1235           # half-up, never banker's rounding
    assert ext_cents(Decimal("3"), Decimal("0.3333")) == 100
    assert cents_str(-5) == "-0.05" and money(123456789) == "$1,234,567.89"


def test_item_parser_roundtrips_every_rendering_style():
    """Contract between generator renderers and the Silver regex parser: attributes survive both BU styles."""
    rng = random.Random(3)
    universe = catalog.build_universe(rng, 1500)
    for attrs in universe:
        for bu in ("BU1", "BU2"):
            for _ in range(3):
                parsed = parse_item_description(attrs["category"], catalog.render_description(attrs, bu, rng))
                assert item_key(parsed) == item_key(attrs)


def test_similar_descriptions_with_different_grade_never_share_identity():
    a = parse_item_description("PLATE", "PLATE 0.5IN 48X96 SA-516 Gr 70")
    b = parse_item_description("PLATE", "PLATE 0.5IN 48X96 SA-516 Gr 60")
    assert key_complete(a) and item_key(a) != item_key(b)
    assert standard_description(a) == "PLATE, 0.5 IN, 48X96, A516-70"


def test_name_normalisation_collapses_formatting_noise_only():
    assert normalize_company_name("Apex Piping & Supply LLC") == normalize_company_name("APEX PIPING AND SUPPLY, Inc.")
    assert normalize_company_name("Apex Piping Mfg Co") == normalize_company_name("The Apex Piping Manufacturing Company")
    assert normalize_taxid("12-3456789") == normalize_taxid("123456789") == "123456789"
    assert parse_date("11/22/2026") == "2026-11-22" and parse_date("2026-02-31") is None and parse_date("00/00/0000") is None
