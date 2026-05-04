from app.services.content_cleaning_service import clean_lines
from app.services.structured_parser import flatten_odds, parse_visible_content, score_extraction


def test_parser_preserves_sport_event_market_selection_odds():
    lines = [
        "Login",
        "Football",
        "Premier League",
        "Team A vs Team B",
        "Today 18:00",
        "1X2",
        "2.10 3.40 3.50",
    ]

    structured = parse_visible_content(lines, "https://betting.co.zw/sportsbook/upcoming")
    odds = flatten_odds(structured)

    assert structured["sports"][0]["sport_name"] == "Football"
    event = structured["sports"][0]["competitions"][0]["events"][0]
    assert event["event_name"] == "Team A vs Team B"
    assert event["start_time"] == "18:00"
    assert odds[0]["selection_name"] == "Team A"
    assert odds[1]["selection_name"] == "Draw"
    assert odds[2]["selection_name"] == "Team B"
    assert odds[2]["odds"] == "3.50"


def test_cleaning_removes_low_value_navigation_but_keeps_duplicate_odds():
    lines = clean_lines(["Login", "Football", "Football", "2.10", "2.10"])
    assert "Login" not in lines
    assert lines.count("Football") == 1
    assert lines.count("2.10") == 1


def test_score_increases_with_structured_content():
    structured = parse_visible_content(
        ["Football", "Premier League", "Team A vs Team B", "1X2", "2.10 3.40 3.50"],
        "https://betting.co.zw/sportsbook/upcoming",
    )
    score = score_extraction("browser_automation", ["x"] * 30, structured, [])
    assert score >= 70

