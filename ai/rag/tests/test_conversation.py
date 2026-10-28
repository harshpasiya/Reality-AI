"""Tests for ai.rag.conversation — follow-ups, paging and browsing, no database.

``search_parsed`` is replaced with a fake that filters an in-memory list the
way the SQL does, and records the filters it was asked for.
"""

from __future__ import annotations

import pytest

from ai.nlu import query_parser
from ai.rag import conversation
from ai.rag.retriever import SearchPage

L = 1_00_000

# 30 listings: 2 and 3 BHK flats in Vesu and Adajan at assorted prices, plus plots.
LISTINGS = (
    [{"id": i, "title": f"Vesu 2BHK {i}", "price": (40 + i) * L, "property_type": "flat",
      "bhk": 2, "locality": "Vesu"} for i in range(1, 13)]
    + [{"id": 100 + i, "title": f"Vesu 3BHK {i}", "price": (90 + i) * L, "property_type": "flat",
        "bhk": 3, "locality": "Vesu"} for i in range(1, 6)]
    + [{"id": 200 + i, "title": f"Adajan 2BHK {i}", "price": (50 + i) * L, "property_type": "flat",
        "bhk": 2, "locality": "Adajan"} for i in range(1, 6)]
    + [{"id": 300 + i, "title": f"Vesu plot {i}", "price": (30 + i) * L, "property_type": "house_land",
        "bhk": None, "locality": "Vesu"} for i in range(1, 9)]
)


class FakeSearch:
    def __init__(self):
        self.calls = []

    def __call__(self, pq, embed_text, *, candidate_ids=None, page_size=10, exclude_ids=None,
                 order="relevance"):
        self.calls.append({"pq": pq, "order": order, "exclude": list(exclude_ids or [])})
        rows = [
            l for l in LISTINGS
            if (pq.bhk is None or l["bhk"] == pq.bhk)
            and (pq.locality is None or l["locality"] == pq.locality)
            and (pq.property_type is None or l["property_type"] == pq.property_type)
            and (pq.price_max is None or l["price"] <= pq.price_max)
            and (pq.price_min is None or l["price"] >= pq.price_min)
        ]
        if order == "price_asc":
            rows.sort(key=lambda l: l["price"])
        total = len(rows)
        rows = [dict(l, match_note="exact") for l in rows if l["id"] not in (exclude_ids or [])]
        return SearchPage(rows[:page_size], total, "exact" if total else None)


@pytest.fixture
def fake(monkeypatch) -> FakeSearch:
    monkeypatch.setenv("NLU_BACKEND", "rules")
    query_parser.cache_clear()
    search = FakeSearch()
    monkeypatch.setattr(conversation, "search_parsed", search)
    by_id = {l["id"]: l["price"] for l in LISTINGS}
    monkeypatch.setattr(conversation, "listing_prices", lambda ids: [by_id[i] for i in ids if i in by_id])
    yield search
    query_parser.cache_clear()


class Chat:
    """Plays a conversation the way the backend does: stores `search` on each reply."""

    def __init__(self):
        self.history: list[dict] = []

    def say(self, text: str) -> dict:
        result = conversation.chat_turn(text, self.history)
        self.history += [
            {"role": "user", "content": text},
            {"role": "assistant", "content": result["reply"], "search": result["search"]},
        ]
        return result


def test_first_message_is_parsed_alone(fake) -> None:
    r = Chat().say("2 BHK in Vesu under 50 lakh")
    pq = fake.calls[-1]["pq"]
    assert (pq.bhk, pq.locality, pq.price_max) == (2, "Vesu", 50 * L)
    assert r["total"] == 10 and len(r["listings"]) == 10 and not r["has_more"]
    assert all(l["bhk"] == 2 and l["price"] <= 50 * L for l in r["listings"])


def test_locality_follow_up_keeps_bhk_and_budget(fake) -> None:
    chat = Chat()
    chat.say("2 BHK in Vesu under 80 lakh")
    r = chat.say("what about Adajan?")
    pq = fake.calls[-1]["pq"]
    assert (pq.bhk, pq.locality, pq.price_max) == (2, "Adajan", 80 * L)
    assert {l["locality"] for l in r["listings"]} == {"Adajan"}


def test_cheaper_lowers_the_budget(fake) -> None:
    chat = Chat()
    chat.say("2 BHK in Vesu under 60 lakh")
    r = chat.say("show me cheaper ones")
    pq = fake.calls[-1]["pq"]
    assert pq.price_max == 48 * L and (pq.bhk, pq.locality) == (2, "Vesu")
    assert r["reply"].startswith("Here are cheaper options")
    assert all(l["price"] <= 48 * L for l in r["listings"])


def test_nothing_cheaper_says_so(fake) -> None:
    chat = Chat()
    chat.say("2 BHK in Vesu under 45 lakh")   # cheapest is 41 L; 80% is 36 L
    r = chat.say("cheaper")
    assert r["listings"] == [] and r["reply"].startswith("I couldn't find anything cheaper")


def test_cheaper_without_a_budget_uses_the_prices_shown(fake) -> None:
    chat = Chat()
    chat.say("3 BHK in Vesu")            # shown: 91-95 lakh
    chat.say("cheaper please")
    assert fake.calls[-1]["pq"].price_max == 76 * L   # 80% of 95 L


def test_bigger_and_bhk_change(fake) -> None:
    chat = Chat()
    chat.say("2 BHK in Vesu")
    chat.say("something bigger")
    assert fake.calls[-1]["pq"].bhk == 3
    chat.say("3 bhk instead")
    assert (fake.calls[-1]["pq"].bhk, fake.calls[-1]["pq"].locality) == (3, "Vesu")


def test_switching_to_plots_drops_the_bhk(fake) -> None:
    chat = Chat()
    chat.say("2 BHK in Vesu")
    r = chat.say("show plots instead")
    pq = fake.calls[-1]["pq"]
    assert (pq.property_type, pq.bhk, pq.locality) == ("house_land", None, "Vesu")
    assert all(l["property_type"] == "house_land" for l in r["listings"])


def test_show_more_pages_without_repeats(fake) -> None:
    chat = Chat()
    first = chat.say("flats in Vesu")      # 17 flats
    assert len(first["listings"]) == 10 and first["has_more"] and "show more" in first["reply"]
    second = chat.say("show more")
    ids1 = {l["id"] for l in first["listings"]}
    ids2 = {l["id"] for l in second["listings"]}
    assert len(ids2) == 7 and not ids1 & ids2 and not second["has_more"]
    assert second["reply"].startswith("Here are 7 more (11–17 of 17)")
    third = chat.say("more")
    assert third["listings"] == [] and third["reply"].startswith("That's all 17")


@pytest.mark.parametrize("text", ["show more", "more", "Show me more listings", "next",
                                  "aur dikhao", "more please"])
def test_more_phrases(text) -> None:
    assert conversation._MORE_RE.match(text)


@pytest.mark.parametrize("text", ["show me more flats in Adajan", "more than 2 bhk",
                                  "anything with more parking"])
def test_not_more_phrases(text) -> None:
    assert not conversation._MORE_RE.match(text)


def test_browse_all_is_newest_first_with_total(fake) -> None:
    r = Chat().say("show me all the listings in surat")
    assert fake.calls[-1]["order"] == "newest" and fake.calls[-1]["pq"].is_empty()
    assert r["total"] == len(LISTINGS) and len(r["listings"]) == 10 and r["has_more"]
    assert r["reply"].startswith(f"There are {len(LISTINGS)} properties available in Surat")


def test_cheapest_sorts_by_price(fake) -> None:
    r = Chat().say("cheapest flats in Vesu")
    assert fake.calls[-1]["order"] == "price_asc"
    prices = [l["price"] for l in r["listings"]]
    assert prices == sorted(prices)


def test_new_search_forgets(fake) -> None:
    chat = Chat()
    chat.say("2 BHK in Vesu under 50 lakh")
    chat.say("new search: plots")
    pq = fake.calls[-1]["pq"]
    assert (pq.bhk, pq.locality, pq.price_max, pq.property_type) == (None, None, None, "house_land")


def test_thanks_keeps_memory_without_searching(fake) -> None:
    chat = Chat()
    chat.say("2 BHK in Vesu")
    calls = len(fake.calls)
    r = chat.say("thanks!")
    assert len(fake.calls) == calls and r["listings"] == [] and r["reply"].startswith("You're welcome")
    chat.say("what about Adajan")
    assert (fake.calls[-1]["pq"].bhk, fake.calls[-1]["pq"].locality) == (2, "Adajan")


def test_off_topic_first_message_is_redirected(fake) -> None:
    r = Chat().say("what's the weather today?")
    assert r["listings"] == [] and fake.calls == [] and r["search"] is None


def test_empty_message_rejected(fake) -> None:
    with pytest.raises(ValueError):
        conversation.chat_turn("   ", [])
