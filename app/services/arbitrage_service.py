from __future__ import annotations

from copy import deepcopy
from typing import Optional

DEFAULT_TOTAL_STAKE = 100.0


class ArbitrageService:
    def build_sections(self, structured_content: dict, total_stake: float = DEFAULT_TOTAL_STAKE) -> dict:
        stake = _positive_float(total_stake, DEFAULT_TOTAL_STAKE)
        available_sports = self._build_available_sports(structured_content)
        analyzed_markets: list[dict] = []
        skipped_markets: list[dict] = []

        for context in iter_markets(available_sports):
            complete, reason = self._market_is_complete(context["market"])
            if not complete:
                skipped_markets.append(self._build_skipped_market(context, reason))
                continue
            analyzed_markets.append(self._analyze_market(context, stake))

        opportunities = sorted(
            [market for market in analyzed_markets if market["arbitrage_exists"]],
            key=lambda market: market["profit_percentage"],
            reverse=True,
        )
        event_analyses = self._build_event_analyses(available_sports, analyzed_markets, skipped_markets)
        summary = self._build_summary(available_sports, analyzed_markets, skipped_markets, opportunities)

        return {
            "total_stake": round_money(stake),
            "section_1_all_available_sporting_events_and_odds": {
                "description": "This section contains all available sporting events and their odds extracted from the website.",
                "sports": available_sports,
            },
            "section_2_arbitrage_analysis": {
                "description": "This section analyzes arbitrage possibility for each complete market.",
                "event_analyses": event_analyses,
                "analyzed_markets": analyzed_markets,
                "arbitrage_opportunities": opportunities,
                "skipped_markets": skipped_markets,
            },
            "section_3_arbitrage_summary": summary,
        }

    def _build_available_sports(self, structured_content: dict) -> list[dict]:
        sports = deepcopy(structured_content.get("sports", []))
        for sport in sports:
            for competition in sport.get("competitions", []):
                for event in competition.get("events", []):
                    for market in event.get("markets", []):
                        market.setdefault("market_status", None)
                        market.setdefault("confidence_score", None)
                        for selection in market.get("selections", []):
                            selection.setdefault("confidence_score", market.get("confidence_score"))
        return sports

    def _market_is_complete(self, market: dict) -> tuple[bool, str]:
        selections = market.get("selections", [])
        valid = [selection for selection in selections if parse_decimal_odds(selection.get("odds")) is not None]
        invalid_count = len(selections) - len(valid)
        market_name = str(market.get("market_name") or "Unspecified market")
        expected = expected_outcome_count(market_name, valid)

        if invalid_count:
            return False, f"{invalid_count} selection odds value could not be parsed."
        if expected is None and len(valid) < 2:
            return False, "At least 2 valid outcomes are required for arbitrage analysis."
        if expected is not None and len(valid) < expected:
            return False, f"{market_name} requires {expected} outcomes, but only {len(valid)} valid outcomes were found."
        if expected is not None and len(valid) > expected:
            return False, f"{market_name} has {len(valid)} outcomes; skipped to avoid combining unrelated markets."
        if expected is None and len(valid) > 3:
            return False, "Market has more than 3 outcomes; skipped to avoid combining unrelated markets."
        return True, ""

    def _analyze_market(self, context: dict, total_stake: float) -> dict:
        market = context["market"]
        selections = []
        for selection in market.get("selections", []):
            decimal_odds = parse_decimal_odds(selection.get("odds"))
            implied_probability = 1 / decimal_odds
            selections.append(
                {
                    "selection_name": selection.get("selection_name"),
                    "odds": selection.get("odds"),
                    "decimal_odds": decimal_odds,
                    "implied_probability": implied_probability,
                    "implied_probability_rounded": round_probability(implied_probability),
                    "confidence_score": selection.get("confidence_score"),
                }
            )

        probability_sum = sum(selection["implied_probability"] for selection in selections)
        arbitrage_exists = probability_sum < 1
        arbitrage_margin = max(0.0, 1 - probability_sum)
        bookmaker_margin = max(0.0, probability_sum - 1)
        stake_allocations = []
        guaranteed_payout: Optional[float] = None
        guaranteed_profit: Optional[float] = None
        profit_percentage = 0.0

        if arbitrage_exists:
            payouts = []
            for selection in selections:
                stake = (total_stake / selection["decimal_odds"]) / probability_sum
                payout = stake * selection["decimal_odds"]
                payouts.append(payout)
                stake_allocations.append(
                    {
                        "selection_name": selection["selection_name"],
                        "odds": selection["odds"],
                        "stake": round_money(stake),
                        "payout": round_money(payout),
                    }
                )
            guaranteed_payout = min(payouts)
            guaranteed_profit = guaranteed_payout - total_stake
            profit_percentage = (guaranteed_profit / total_stake) * 100

        proof = build_calculation_proof(
            selections=selections,
            probability_sum=probability_sum,
            arbitrage_exists=arbitrage_exists,
            arbitrage_margin=arbitrage_margin,
            bookmaker_margin=bookmaker_margin,
            profit_percentage=profit_percentage,
            total_stake=total_stake,
        )

        return {
            "sport": context["sport_name"],
            "competition": context["competition_name"],
            "event": context["event_name"],
            "event_key": context["event_key"],
            "start_date": context["start_date"],
            "start_time": context["start_time"],
            "market": market.get("market_name"),
            "market_status": market.get("market_status"),
            "market_confidence_score": market.get("confidence_score"),
            "number_of_outcomes": len(selections),
            "odds_used": [
                {
                    "selection_name": selection["selection_name"],
                    "odds": selection["odds"],
                    "decimal_odds": selection["decimal_odds"],
                }
                for selection in selections
            ],
            "implied_probabilities": selections,
            "total_implied_probability": probability_sum,
            "total_implied_probability_rounded": round_probability(probability_sum),
            "arbitrage_exists": arbitrage_exists,
            "arbitrage_margin": arbitrage_margin if arbitrage_exists else 0,
            "arbitrage_margin_rounded": round_probability(arbitrage_margin) if arbitrage_exists else 0,
            "bookmaker_margin": bookmaker_margin if not arbitrage_exists else 0,
            "bookmaker_margin_rounded": round_probability(bookmaker_margin) if not arbitrage_exists else 0,
            "bookmaker_margin_percentage": round_percentage(bookmaker_margin * 100) if not arbitrage_exists else 0,
            "expected_profit_percentage": round_percentage((arbitrage_margin / probability_sum) * 100) if arbitrage_exists else 0,
            "profit_percentage": round_percentage(profit_percentage) if arbitrage_exists else 0,
            "recommended_stake_allocation": stake_allocations,
            "guaranteed_payout": round_money(guaranteed_payout) if guaranteed_payout is not None else None,
            "guaranteed_profit": round_money(guaranteed_profit) if guaranteed_profit is not None else None,
            "calculation_proof": proof,
            "result_explanation": build_result_explanation(probability_sum, arbitrage_exists),
        }

    def _build_skipped_market(self, context: dict, reason: str) -> dict:
        market = context["market"]
        return {
            "sport": context["sport_name"],
            "competition": context["competition_name"],
            "event": context["event_name"],
            "event_key": context["event_key"],
            "start_date": context["start_date"],
            "start_time": context["start_time"],
            "market": market.get("market_name"),
            "market_status": market.get("market_status"),
            "number_of_outcomes_found": len(market.get("selections", [])),
            "odds_found": [
                {
                    "selection_name": selection.get("selection_name"),
                    "odds": selection.get("odds"),
                }
                for selection in market.get("selections", [])
            ],
            "skip_reason": reason,
        }

    def _build_event_analyses(
        self,
        sports: list[dict],
        analyzed_markets: list[dict],
        skipped_markets: list[dict],
    ) -> list[dict]:
        events_by_key: dict[str, dict] = {}

        for sport in sports:
            for competition in sport.get("competitions", []):
                for event in competition.get("events", []):
                    key = event_key(
                        sport.get("sport_name"),
                        competition.get("competition_name"),
                        event.get("event_name"),
                        event.get("start_date"),
                        event.get("start_time"),
                    )
                    markets = event.get("markets", [])
                    events_by_key[key] = {
                        "event_key": key,
                        "sport": sport.get("sport_name"),
                        "competition": competition.get("competition_name"),
                        "event": event.get("event_name"),
                        "start_date": event.get("start_date"),
                        "start_time": event.get("start_time"),
                        "markets_found": len(markets),
                        "odds_extracted": sum(len(market.get("selections", [])) for market in markets),
                        "complete_markets_analyzed": 0,
                        "incomplete_markets_skipped": 0,
                        "has_arbitrage_opportunity": False,
                        "best_profit_percentage": 0,
                        "event_result": "No complete markets were analyzed.",
                        "analyzed_markets": [],
                        "skipped_markets": [],
                    }

        for market in analyzed_markets:
            key = market.get("event_key")
            if key not in events_by_key:
                continue
            event_analysis = events_by_key[key]
            event_analysis["analyzed_markets"].append(market)
            event_analysis["complete_markets_analyzed"] += 1
            if market.get("arbitrage_exists"):
                event_analysis["has_arbitrage_opportunity"] = True
                event_analysis["best_profit_percentage"] = max(
                    event_analysis["best_profit_percentage"],
                    market.get("profit_percentage", 0),
                )

        for market in skipped_markets:
            key = market.get("event_key")
            if key not in events_by_key:
                continue
            event_analysis = events_by_key[key]
            event_analysis["skipped_markets"].append(market)
            event_analysis["incomplete_markets_skipped"] += 1

        for event_analysis in events_by_key.values():
            analyzed_count = event_analysis["complete_markets_analyzed"]
            if event_analysis["has_arbitrage_opportunity"]:
                event_analysis["event_result"] = (
                    f"Arbitrage opportunity found in this event. Best profit: "
                    f"{round_percentage(event_analysis['best_profit_percentage']):.2f}%."
                )
            elif analyzed_count:
                event_analysis["event_result"] = "No arbitrage opportunity found in any complete market for this event."
            else:
                event_analysis["event_result"] = "No arbitrage decision was made because all markets for this event were incomplete."

        return list(events_by_key.values())

    def _build_summary(
        self,
        sports: list[dict],
        analyzed_markets: list[dict],
        skipped_markets: list[dict],
        opportunities: list[dict],
    ) -> dict:
        competitions = [
            competition
            for sport in sports
            for competition in sport.get("competitions", [])
        ]
        events = [
            event
            for competition in competitions
            for event in competition.get("events", [])
        ]
        markets = [
            market
            for event in events
            for market in event.get("markets", [])
        ]
        odds = [
            selection
            for market in markets
            for selection in market.get("selections", [])
            if selection.get("odds") is not None
        ]
        best = opportunities[0] if opportunities else None
        return {
            "sports_found": len(sports),
            "competitions_found": len(competitions),
            "events_found": len(events),
            "markets_found": len(markets),
            "odds_extracted": len(odds),
            "complete_markets_analyzed": len(analyzed_markets),
            "incomplete_markets_skipped": len(skipped_markets),
            "arbitrage_opportunities_found": len(opportunities),
            "best_arbitrage_opportunity": best_summary(best) if best else None,
            "best_arbitrage_profit_percentage": best.get("profit_percentage", 0) if best else 0,
            "highest_profit_percentage": best.get("profit_percentage", 0) if best else 0,
        }


def iter_markets(sports: list[dict]):
    for sport in sports:
        for competition in sport.get("competitions", []):
            for event in competition.get("events", []):
                for market in event.get("markets", []):
                    yield {
                        "sport_name": sport.get("sport_name"),
                        "competition_name": competition.get("competition_name"),
                        "event_name": event.get("event_name"),
                        "event_key": event_key(
                            sport.get("sport_name"),
                            competition.get("competition_name"),
                            event.get("event_name"),
                            event.get("start_date"),
                            event.get("start_time"),
                        ),
                        "start_date": event.get("start_date"),
                        "start_time": event.get("start_time"),
                        "market": market,
                    }


def event_key(
    sport_name: object,
    competition_name: object,
    event_name: object,
    start_date: object,
    start_time: object,
) -> str:
    return "|".join(
        [
            str(sport_name or ""),
            str(competition_name or ""),
            str(event_name or ""),
            str(start_date or ""),
            str(start_time or ""),
        ]
    )


def expected_outcome_count(market_name: str, selections: list[dict]) -> Optional[int]:
    normalized = market_name.strip().lower()
    selection_names = [str(selection.get("selection_name") or "").strip().lower() for selection in selections]
    if normalized in {"1x2", "1 x 2"} or "1x2" in normalized:
        return 3
    if "under/over" in normalized or "over/under" in normalized or "total" in normalized:
        return 2
    if any(name == "draw" for name in selection_names):
        return 3
    if "winner" in normalized or "moneyline" in normalized:
        return 2 if len(selection_names) == 2 else 3 if len(selection_names) == 3 else None
    return None


def parse_decimal_odds(value: object) -> Optional[float]:
    try:
        decimal = float(str(value))
    except (TypeError, ValueError):
        return None
    if decimal <= 1:
        return None
    return decimal


def build_calculation_proof(
    *,
    selections: list[dict],
    probability_sum: float,
    arbitrage_exists: bool,
    arbitrage_margin: float,
    bookmaker_margin: float,
    profit_percentage: float,
    total_stake: float,
) -> list[str]:
    terms = []
    proof = []
    for selection in selections:
        odds = selection["decimal_odds"]
        probability = selection["implied_probability"]
        terms.append(f"{round_probability(probability):.4f}")
        proof.append(f"1/{odds:g} = {round_probability(probability):.4f}")
    proof.append(f"Total implied probability: {' + '.join(terms)} = {round_probability(probability_sum):.4f}")
    if arbitrage_exists:
        proof.append(f"Arbitrage check: {round_probability(probability_sum):.4f} < 1")
        proof.append(f"Arbitrage margin: 1 - {round_probability(probability_sum):.4f} = {round_probability(arbitrage_margin):.4f}")
        proof.append(
            f"Expected profit percentage: {round_probability(arbitrage_margin):.4f} / "
            f"{round_probability(probability_sum):.4f} x 100 = {round_percentage((arbitrage_margin / probability_sum) * 100):.2f}%"
        )
        proof.append(f"Guaranteed profit uses total stake {round_money(total_stake):.2f}: {round_percentage(profit_percentage):.2f}%")
    else:
        proof.append(f"No arbitrage exists because {round_probability(probability_sum):.4f} is greater than or equal to 1.")
        proof.append(f"Bookmaker margin: {round_probability(probability_sum):.4f} - 1 = {round_probability(bookmaker_margin):.4f}")
        proof.append(f"Bookmaker margin percentage: {round_probability(bookmaker_margin):.4f} x 100 = {round_percentage(bookmaker_margin * 100):.2f}%")
    return proof


def build_result_explanation(probability_sum: float, arbitrage_exists: bool) -> str:
    rounded_sum = f"{round_probability(probability_sum):.4f}"
    if arbitrage_exists:
        return f"Arbitrage opportunity exists because the total implied probability {rounded_sum} is less than 1."
    return f"No arbitrage exists because the total implied probability {rounded_sum} is greater than or equal to 1."


def best_summary(market: dict) -> dict:
    return {
        "sport": market.get("sport"),
        "competition": market.get("competition"),
        "event": market.get("event"),
        "market": market.get("market"),
        "profit_percentage": market.get("profit_percentage"),
        "guaranteed_profit": market.get("guaranteed_profit"),
        "guaranteed_payout": market.get("guaranteed_payout"),
    }


def round_money(value: float) -> float:
    return round(float(value), 2)


def round_probability(value: float) -> float:
    return round(float(value), 4)


def round_percentage(value: float) -> float:
    return round(float(value), 2)


def _positive_float(value: object, fallback: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback
