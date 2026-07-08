from app.services.pdf import matcher


def biz(id_, name, type_, years):
    return {"id": id_, "name": name, "type": type_, "years": years}


def test_word_boundary_avoids_partial_match():
    """'bay' should not falsely match inside an unrelated word — only the
    real business-name token should be picked up."""
    businesses = [
        biz(1, "51 Lakeside Dr", "rental", ["2024"]),
        biz(2, "1632 Bayview Ave", "rental", ["2024"]),
    ]
    result = matcher.match_document("bayview insurance renewal", "scan.pdf", businesses)
    assert result["business_id"] == 2

    result_no_match = matcher.match_document("a day at the bay", "scan.pdf", businesses)
    assert result_no_match["business_id"] is None


def test_year_tie_break_prefers_most_recent():
    """When two years appear equally often, the pick must be deterministic —
    it should prefer the more recent year, not whichever happened to appear
    first in the document text (Counter.most_common ties are insertion-order,
    not recency-order)."""
    businesses = [biz(1, "51 Lakeside Dr", "rental", ["2023", "2024"])]
    text = "invoice dated 2023 reissued 2024"
    result = matcher.match_document(text, "51 lakeside insurance.pdf", businesses)
    assert result["year"] == "2024"


def test_year_prefers_one_business_actually_has():
    businesses = [biz(1, "51 Lakeside Dr", "rental", ["2022"])]
    text = "51 lakeside insurance for 2024, historical note from 2022"
    result = matcher.match_document(text, "scan.pdf", businesses)
    assert result["year"] == "2022"


def test_no_keyword_match_gives_none_confidence():
    businesses = [biz(1, "51 Lakeside Dr", "rental", ["2024"])]
    result = matcher.match_document("completely unrelated text", "scan.pdf", businesses)
    assert result["confidence"] == "none"
    assert result["business_id"] is None


def test_confidence_high_for_single_distinctive_word():
    businesses = [biz(1, "Lakeside", "rental", [])]
    result = matcher.match_document("lakeside insurance bill", "scan.pdf", businesses)
    assert result["confidence"] == "high"


def test_confidence_low_for_numeric_only_match():
    businesses = [biz(1, "51", "rental", [])]
    result = matcher.match_document("51", "scan.pdf", businesses)
    assert result["confidence"] == "low"


def test_car_insurance_routes_to_car_bucket_directly():
    text_l = "lexus rx350 auto insurance policy renewal"
    assert matcher.suggest_bucket(text_l, "consulting") == "6a"


def test_auto_insurance_without_brand_still_routes_to_car_bucket():
    """Exercises the 6c->6a special case: no lexus/corolla/vehicle keyword,
    just 'auto ' plus an insurance term, which would otherwise land in the
    general insurance bucket."""
    text_l = "auto insurance policy premium renewal"
    assert matcher.suggest_bucket(text_l, "consulting") == "6a"


def test_general_insurance_routes_to_insurance_bucket():
    text_l = "home insurance policy renewal premium"
    assert matcher.suggest_bucket(text_l, "rental") == "6c"


def test_bucket_fallback_by_business_type():
    assert matcher.suggest_bucket("nothing relevant here", "real_estate") == "6f"
    assert matcher.suggest_bucket("nothing relevant here", "rental") == "6g"
    assert matcher.suggest_bucket("nothing relevant here", "consulting") == ""
