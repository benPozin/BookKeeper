from app.services.gmail import scan as gscan


def test_parse_label_rental_property_and_year():
    info = gscan.parse_label(
        "rental", "Business/Rental/51 Lakeside Dr/Income2024", "Business/Rental"
    )
    assert info == {"business": "51 Lakeside Dr", "year": 2024, "kind": "income"}


def test_parse_label_expense_typo_explense():
    info = gscan.parse_label(
        "rental", "Business/Rental/51 Lakeside Dr/Explense2015", "Business/Rental"
    )
    assert info["year"] == 2015
    assert info["kind"] == "expense"


def test_parse_label_real_estate_is_fixed_business():
    info = gscan.parse_label(
        "real_estate", "Business/Real Estate/Expenses2023", "Business/Real Estate"
    )
    assert info["business"] == "Real Estate"
    assert info["year"] == 2023


def test_parse_label_no_year_falls_back_to_segment_as_business():
    info = gscan.parse_label("consulting", "Business/Consulting/Misc", "Business/Consulting")
    assert info["year"] is None
    assert info["business"] == "Misc"


def test_year_label_calendar_mode():
    assert gscan.year_label("2024-06-15", "calendar", "12-31") == "2024"


def test_year_label_fiscal_mode_on_or_before_end():
    assert gscan.year_label("2024-06-15", "fiscal", "06-30") == "FY2024"


def test_year_label_fiscal_mode_after_end_rolls_forward():
    assert gscan.year_label("2024-07-15", "fiscal", "06-30") == "FY2025"


def test_year_label_unparseable_date_returns_unknown():
    assert gscan.year_label("not-a-date", "calendar", "12-31") == "unknown"
