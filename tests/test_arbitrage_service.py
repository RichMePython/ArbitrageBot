from app.services.arbitrage_service import ArbitrageService


def test_arbitrage_service_finds_positive_market_and_stakes():
    structured = {
        "sports": [
            {
                "sport_name": "Football",
                "competitions": [
                    {
                        "competition_name": "Premier League",
                        "events": [
                            {
                                "event_name": "Team A vs Team B",
                                "start_date": "2026-05-04",
                                "start_time": "18:00",
                                "markets": [
                                    {
                                        "market_name": "1X2",
                                        "selections": [
                                            {"selection_name": "Team A", "odds": "2.30"},
                                            {"selection_name": "Draw", "odds": "3.80"},
                                            {"selection_name": "Team B", "odds": "4.20"},
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }

    sections = ArbitrageService().build_sections(structured, total_stake=100)
    analyzed = sections["section_2_arbitrage_analysis"]["analyzed_markets"][0]

    assert analyzed["arbitrage_exists"] is True
    assert analyzed["total_implied_probability_rounded"] == 0.936
    assert analyzed["profit_percentage"] > 6.7
    assert analyzed["recommended_stake_allocation"][0]["stake"] == 46.45
    assert sections["section_3_arbitrage_summary"]["arbitrage_opportunities_found"] == 1
    event_analysis = sections["section_2_arbitrage_analysis"]["event_analyses"][0]
    assert event_analysis["event"] == "Team A vs Team B"
    assert event_analysis["has_arbitrage_opportunity"] is True


def test_arbitrage_service_reports_no_arbitrage_margin():
    structured = {
        "sports": [
            {
                "sport_name": "Football",
                "competitions": [
                    {
                        "competition_name": "Premier League",
                        "events": [
                            {
                                "event_name": "Team C vs Team D",
                                "markets": [
                                    {
                                        "market_name": "1X2",
                                        "selections": [
                                            {"selection_name": "Team C", "odds": "1.80"},
                                            {"selection_name": "Draw", "odds": "3.20"},
                                            {"selection_name": "Team D", "odds": "4.60"},
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }

    sections = ArbitrageService().build_sections(structured, total_stake=100)
    analyzed = sections["section_2_arbitrage_analysis"]["analyzed_markets"][0]

    assert analyzed["arbitrage_exists"] is False
    assert analyzed["total_implied_probability_rounded"] == 1.0854
    assert analyzed["bookmaker_margin_rounded"] == 0.0854
    assert analyzed["bookmaker_margin_percentage"] == 8.54
    event_analysis = sections["section_2_arbitrage_analysis"]["event_analyses"][0]
    assert event_analysis["has_arbitrage_opportunity"] is False
    assert event_analysis["complete_markets_analyzed"] == 1


def test_arbitrage_service_skips_incomplete_1x2_market():
    structured = {
        "sports": [
            {
                "sport_name": "Football",
                "competitions": [
                    {
                        "competition_name": "Premier League",
                        "events": [
                            {
                                "event_name": "Team A vs Team B",
                                "markets": [
                                    {
                                        "market_name": "1X2",
                                        "selections": [
                                            {"selection_name": "Team A", "odds": "2.30"},
                                            {"selection_name": "Team B", "odds": "4.20"},
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }

    sections = ArbitrageService().build_sections(structured, total_stake=100)

    assert sections["section_2_arbitrage_analysis"]["analyzed_markets"] == []
    assert sections["section_2_arbitrage_analysis"]["skipped_markets"][0]["market"] == "1X2"
    assert sections["section_3_arbitrage_summary"]["incomplete_markets_skipped"] == 1
    event_analysis = sections["section_2_arbitrage_analysis"]["event_analyses"][0]
    assert event_analysis["complete_markets_analyzed"] == 0
    assert event_analysis["incomplete_markets_skipped"] == 1
