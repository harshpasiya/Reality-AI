"""Synthetic training-data generator for the Reality AI property-chat assistant.

Generates JSONL files in the chat format expected by trl's SFTTrainer with
a chat-template-based model (Mistral / Phi-3).  Every example is a list of
messages with roles: system, user, assistant — and optionally multiple turns.

Usage:
    python -m ai.finetune.prepare_dataset --mode debug   # 100 examples
    python -m ai.finetune.prepare_dataset --mode full    # 750 examples
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Reproducibility — callers can override by setting SEED env var
# ---------------------------------------------------------------------------
SEED = int(os.environ.get("SEED", 7))
random.seed(SEED)

# ---------------------------------------------------------------------------
# System prompt (sent as the first message in every training example)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are RealityAI, a helpful and knowledgeable real estate assistant "
    "specialising exclusively in properties in Surat, Gujarat, India. "
    "You help customers find flats and plots that match their budget, location "
    "preferences, and lifestyle needs. "
    "You have access to a database of Surat listings and can answer questions "
    "about price ranges, neighbourhoods, nearby amenities (schools, hospitals, "
    "parks, restaurants, transit), property types, and investment potential. "
    "If a customer asks something unrelated to Surat real estate, politely "
    "redirect them: acknowledge their question, explain your scope, and offer "
    "to help with property-related needs instead. "
    "Always be concise, friendly, and factual. Never invent listing details "
    "that have not been provided to you."
)

# ---------------------------------------------------------------------------
# Surat data — mirrors _test_seed.py so conversations reference real areas
# ---------------------------------------------------------------------------
NEIGHBOURHOODS = [
    {"name": "Adajan",          "tier": "premium"},
    {"name": "Vesu",            "tier": "premium"},
    {"name": "Athwa",           "tier": "premium"},
    {"name": "Piplod",          "tier": "premium"},
    {"name": "Citylight",       "tier": "premium"},
    {"name": "Ghod Dod Road",   "tier": "premium"},
    {"name": "Dumas",           "tier": "premium"},
    {"name": "Pal",             "tier": "mid"},
    {"name": "Althan",          "tier": "mid"},
    {"name": "Bhatar",          "tier": "mid"},
    {"name": "Palanpur",        "tier": "mid"},
    {"name": "Jahangirpura",    "tier": "mid"},
    {"name": "Rander",          "tier": "mid"},
    {"name": "Varachha",        "tier": "budget"},
    {"name": "Katargam",        "tier": "budget"},
    {"name": "Udhna",           "tier": "budget"},
    {"name": "Sarthana",        "tier": "budget"},
    {"name": "Sachin",          "tier": "budget"},
    {"name": "Puna Kumbharia",  "tier": "budget"},
    {"name": "Kapodra",         "tier": "budget"},
]

PRICE_BANDS = {
    "premium": {"flat_low": 3500000,  "flat_high": 45000000,
                "land_low": 4000000,  "land_high": 30000000},
    "mid":     {"flat_low": 2000000,  "flat_high": 12000000,
                "land_low": 2000000,  "land_high": 12000000},
    "budget":  {"flat_low": 1000000,  "flat_high": 6500000,
                "land_low": 800000,   "land_high": 5000000},
}

LANDMARKS = {
    "Adajan": ["VR Mall", "Adajan Patiya"],
    "Vesu": ["Dumas Road", "Iscon-Ambli Road"],
    "Athwa": ["Ghod Dod Road", "Surat Railway Station"],
    "Piplod": ["Piplod Circle", "City Light Road"],
    "Citylight": ["Citylight Cinema", "Tapi River"],
    "Ghod Dod Road": ["Parle Point", "Nirmala Convent"],
    "Dumas": ["Dumas Beach", "Arabian Sea"],
    "Pal": ["Pal Circle", "Surat Airport"],
    "Althan": ["SNS College", "VIP Road"],
    "Bhatar": ["Bhatar Road", "Ring Road"],
    "Palanpur": ["Palanpur Patia", "Surat-Navsari Highway"],
    "Jahangirpura": ["Jahangir Circle", "NH-48"],
    "Rander": ["Rander Road", "Tapi River"],
    "Varachha": ["Varachha Road", "Diamond Market"],
    "Katargam": ["Katargam Gate", "Textile Market"],
    "Udhna": ["Udhna Darwaja", "GIDC"],
    "Sarthana": ["Sarthana Nature Park", "Tapi River"],
    "Sachin": ["Sachin GIDC", "Hazira Road"],
    "Puna Kumbharia": ["Kumbharia Circle", "BRTS"],
    "Kapodra": ["Kapodra Circle", "Surat Ring Road"],
}

AMENITY_TYPES = ["school", "hospital", "park", "metro station", "shopping mall",
                 "restaurant", "gym", "supermarket"]

SOCIETIES = [
    "Shree Residency", "Param Heights", "Shivalay Tower", "Om Shanti Complex",
    "Titanium City Centre", "Aakar Heights", "Sai Elegance", "Silver Arch",
    "Royal Garden", "Nilamber Harmony", "Aura Homes", "Rajhans Montessa",
]

FEATURES = [
    "modular kitchen and covered parking",
    "rooftop terrace and gym access",
    "split ACs in all rooms",
    "Italian marble flooring",
    "swimming pool and clubhouse",
    "24x7 security and CCTV",
    "solar power backup",
    "garden-facing balcony",
]

OFF_TOPIC_QUESTIONS = [
    ("What is the capital of France?",
     "That's a geography question — my expertise is Surat real estate! "
     "I can't help with general knowledge questions, but if you're looking "
     "for a flat or plot in Surat, I'm happy to assist. "
     "What kind of property are you interested in?"),

    ("Can you write me a Python script?",
     "Writing code is outside my area — I specialise in Surat property listings! "
     "If you need help finding a flat or plot in Surat, just let me know your "
     "budget and preferred area and I'll get started."),

    ("Who won the IPL last year?",
     "Cricket scores are beyond my expertise — I'm a Surat real estate assistant! "
     "If you're thinking about investing in property in Surat, though, I'd love "
     "to help. What's your budget range?"),

    ("Can you recommend a good restaurant in Mumbai?",
     "I focus on Surat real estate, so Mumbai dining is a bit outside my scope! "
     "That said, if you're looking for a property near restaurants or markets "
     "in Surat, I can definitely help with that. Interested?"),

    ("What is the best cryptocurrency to buy right now?",
     "Investment advice for crypto is outside what I can help with — "
     "my speciality is Surat real estate. "
     "If you're interested in property investment in Surat, I can tell you "
     "about areas with strong rental yield. Want to know more?"),

    ("Can you translate this text to Hindi?",
     "Translation isn't something I can do — I'm here for Surat property queries! "
     "If you have questions about flats, plots, prices, or neighbourhoods in Surat, "
     "I'm at your service."),

    ("Tell me a joke.",
     "Ha — I'm better at property than punchlines! "
     "If you'd like, I can help you find a great flat in Surat instead. "
     "What area or budget are you working with?"),

    ("What is the weather like in Delhi?",
     "Weather forecasts are outside my scope — I'm a Surat real estate specialist! "
     "If you're relocating to Surat and need help finding a flat, I'd be happy to assist. "
     "What's your budget range?"),

    ("How do I apply for a passport in India?",
     "Passport applications are handled by the Passport Seva Kendra — beyond my area! "
     "I'm here exclusively for Surat property queries. "
     "Are you looking to buy or rent a flat in Surat?"),

    ("What are the best MBA colleges in India?",
     "College rankings are outside my expertise — though I can help you find a flat "
     "near SVNIT or other institutions in Surat if you're planning to study here! "
     "Interested?"),

    ("Can you book a train ticket for me?",
     "Ticket booking is not something I can do — my focus is Surat real estate. "
     "If you're moving to Surat and need to find accommodation, I'm the right assistant! "
     "What kind of property are you looking for?"),

    ("What is 15% of 8500?",
     "I'm a real estate assistant, not a calculator — though the answer is 1275! "
     "More importantly, if you're calculating a down payment or stamp duty for a "
     "Surat property, I can help with that context. Shall I?"),

    ("Can you help me write my resume?",
     "Resume writing is outside my area — I specialise in Surat property! "
     "But if you've just landed a new job in Surat and need a flat near your office, "
     "I'm exactly the right assistant. Which area of the city is your workplace in?"),

    ("What movies are showing in Surat this weekend?",
     "Movie schedules are outside my scope, but I do know Surat's best cinema zones! "
     "If you want a flat near VR Mall or Citylight Cinema, I can help you find one. "
     "Interested in nearby listings?"),
]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _pick_area() -> dict:
    return random.choice(NEIGHBOURHOODS)


def _price(area: dict, ptype: str = "flat") -> int:
    band = PRICE_BANDS[area["tier"]]
    lo = band[f"{ptype}_low"]
    hi = band[f"{ptype}_high"]
    return round(random.randint(lo, hi) / 100000) * 100000


def _fmt_price(p: int) -> str:
    """Format price as 'Rs.X.XX Cr' or 'Rs.XX L'."""
    if p >= 10000000:
        return f"Rs.{p/10000000:.2f} Cr"
    return f"Rs.{p//100000} L"


def _bhk() -> int:
    return random.choices([1, 2, 3, 4], weights=[10, 40, 35, 15])[0]


def _landmark(area: dict) -> str:
    return random.choice(LANDMARKS.get(area["name"], ["Surat Railway Station"]))


def _society() -> str:
    return random.choice(SOCIETIES)


def _feature() -> str:
    return random.choice(FEATURES)


def _amenity() -> str:
    return random.choice(AMENITY_TYPES)


def _floor() -> int:
    return random.randint(1, 14)


def _sqft_land() -> int:
    return random.choice([600, 800, 1000, 1200, 1500, 2000, 2500])


def _two_areas() -> tuple[dict, dict]:
    a, b = random.sample(NEIGHBOURHOODS, 2)
    return a, b


def _budget_range(area: dict) -> tuple[int, int]:
    band = PRICE_BANDS[area["tier"]]
    lo = band["flat_low"]
    hi = band["flat_high"]
    mid = (lo + hi) // 2
    return round(lo / 100000) * 100000, round(mid / 100000) * 100000


# ---------------------------------------------------------------------------
# Template categories
# Each template is a callable that returns a list[dict] of messages
# (excluding the system message, which is always prepended).
# ---------------------------------------------------------------------------

CATEGORY_NAMES = [
    "budget_price",
    "location_proximity",
    "amenity_specific",
    "compare_listings",
    "narrow_search",
    "off_topic",
    "multi_turn_refinement",
    "property_type",
    "investment",
    "viewing_request",
]


def tpl_budget_price() -> tuple[str, list[dict]]:
    area = _pick_area()
    bhk_val = _bhk()
    lo, hi = _budget_range(area)
    p = _price(area)

    variations = [
        (
            f"I'm looking for a {bhk_val}BHK flat in Surat. My budget is between "
            f"{_fmt_price(lo)} and {_fmt_price(hi)}. What options do I have?",
            f"With a budget of {_fmt_price(lo)} to {_fmt_price(hi)}, you have some good options "
            f"for a {bhk_val}BHK flat in Surat. "
            f"{area['name']} is a popular choice in that range — a typical {bhk_val}BHK there "
            f"is priced around {_fmt_price(p)}, featuring {_feature()}. "
            f"Would you like me to focus on {area['name']}, or are you open to nearby areas too?"
        ),
        (
            f"What is the average price for a 2BHK flat in {area['name']}?",
            f"In {area['name']}, a 2BHK flat typically ranges from "
            f"{_fmt_price(PRICE_BANDS[area['tier']]['flat_low'])} to "
            f"{_fmt_price(PRICE_BANDS[area['tier']]['flat_high'])}. "
            f"The price depends on the floor, society amenities, and age of the building. "
            f"Properties near {_landmark(area)} tend to command a slight premium. "
            f"Shall I show you specific listings in that range?"
        ),
        (
            f"I have a budget of {_fmt_price(lo + 500000)}. Is that enough for a flat in Surat?",
            f"Yes, {_fmt_price(lo + 500000)} is a workable budget for a flat in Surat. "
            f"At that price point, you can find a good 1BHK or a compact 2BHK in areas like "
            f"{area['name']}. "
            f"If you're flexible on location, budget-friendly areas like Varachha or Katargam "
            f"offer larger units at that price. What matters more — size or location?"
        ),
    ]
    u, a_msg = random.choice(variations)
    return "budget_price", [{"role": "user", "content": u},
                             {"role": "assistant", "content": a_msg}]


def tpl_location_proximity() -> tuple[str, list[dict]]:
    area = _pick_area()
    bhk_val = _bhk()
    lmark = _landmark(area)
    p = _price(area)

    variations = [
        (
            f"I want a flat close to {lmark} in Surat. What's available?",
            f"Great choice — {lmark} is in {area['name']}, one of Surat's "
            f"{'sought-after' if area['tier'] == 'premium' else 'well-connected'} localities. "
            f"There are several {bhk_val}BHK flats nearby priced around {_fmt_price(p)}, "
            f"featuring {_feature()}. "
            f"Would you like options within walking distance, or is a 10-15 minute drive okay?"
        ),
        (
            f"Which areas in Surat are good for families with kids?",
            f"For families, I'd recommend Adajan, Vesu, or Piplod — they have reputed schools, "
            f"wide roads, and low traffic. {area['name']} is also a solid choice with good "
            f"social infrastructure. "
            f"A 3BHK in Adajan is typically priced between "
            f"{_fmt_price(PRICE_BANDS['premium']['flat_low'])} and "
            f"{_fmt_price(PRICE_BANDS['premium']['flat_high'])}. "
            f"Would you like me to narrow it down by budget?"
        ),
        (
            f"How far is {area['name']} from Surat Railway Station?",
            f"{area['name']} is roughly "
            f"{'5-10' if area['tier'] == 'premium' else '15-25'} minutes by road from "
            f"Surat Railway Station, depending on traffic. "
            f"It's a {'central' if area['tier'] == 'premium' else 'well-connected'} locality "
            f"with good access to arterial roads and BRTS routes. "
            f"Are you looking for a flat here, or is commute time the main concern?"
        ),
    ]
    u, a_msg = random.choice(variations)
    return "location_proximity", [{"role": "user", "content": u},
                                   {"role": "assistant", "content": a_msg}]


def tpl_amenity_specific() -> tuple[str, list[dict]]:
    area = _pick_area()
    amenity = _amenity()
    bhk_val = _bhk()
    p = _price(area)
    p2 = _price(area)
    society = _society()
    lmark = _landmark(area)
    feat = _feature()
    bhk2 = _bhk()

    variations = [
        (
            f"I need a {bhk_val}BHK flat near a good {amenity} in {area['name']}. Any suggestions?",
            f"{area['name']} has good {amenity} options nearby. "
            f"A {bhk_val}BHK in {society} is listed at {_fmt_price(p)}, "
            f"within walking distance of a well-rated {amenity}. "
            f"Features: {feat}. Want more options?"
        ),
        (
            f"Are there flats near a hospital in {area['name']}?",
            f"Yes — {area['name']} has medical facilities close by. "
            f"A {bhk_val}BHK near {lmark} is priced around {_fmt_price(p)}, "
            f"with {feat}. Do you have a budget in mind?"
        ),
        (
            f"My parents need to live near a park in Surat for morning walks. "
            f"Any flats near parks in {area['name']}?",
            f"Sarthana Nature Park and the Tapi riverfront are popular with seniors. "
            f"In {area['name']}, a {bhk_val}BHK near {lmark} is priced at {_fmt_price(p)}, "
            f"with {feat}. Ground-floor options available. Shall I filter further?"
        ),
        (
            f"I want a flat in Surat within 10 minutes of a {amenity}. Which areas work?",
            f"For proximity to a {amenity}, I'd suggest {area['name']} or nearby localities. "
            f"A {bhk_val}BHK in {society}, {area['name']} at {_fmt_price(p)} fits well — "
            f"the nearest {amenity} is under 10 minutes away. Features: {feat}."
        ),
        (
            f"Do any listings in Surat come with a {amenity} inside the society?",
            f"Yes — some societies in {area['name']} include an in-building {amenity}. "
            f"{society} is one such society; a {bhk2}BHK there is priced at {_fmt_price(p2)} "
            f"and includes {feat}. Want me to check availability?"
        ),
        (
            f"We have two school-going kids. Which Surat area has the best schools nearby?",
            f"Adajan, Vesu, and Piplod are known for reputed schools — CBSE and ICSE boards. "
            f"In {area['name']}, a {bhk_val}BHK near {lmark} at {_fmt_price(p)} is close to "
            f"good schools and has {feat}. Budget in mind?"
        ),
    ]
    u, a_msg = random.choice(variations)
    return "amenity_specific", [{"role": "user", "content": u},
                                 {"role": "assistant", "content": a_msg}]


def tpl_compare_listings() -> tuple[str, list[dict]]:
    area1, area2 = _two_areas()
    bhk_val = _bhk()
    p1 = _price(area1)
    p2 = _price(area2)
    f1 = _feature()
    f2 = _feature()

    u = (
        f"I'm torn between a {bhk_val}BHK in {area1['name']} at {_fmt_price(p1)} "
        f"and one in {area2['name']} at {_fmt_price(p2)}. Which is better?"
    )
    if p1 < p2:
        cheaper, pricier = area1['name'], area2['name']
        cheap_p, pricy_p = _fmt_price(p1), _fmt_price(p2)
        cheap_f, pricy_f = f1, f2
    else:
        cheaper, pricier = area2['name'], area1['name']
        cheap_p, pricy_p = _fmt_price(p2), _fmt_price(p1)
        cheap_f, pricy_f = f2, f1

    a_msg = (
        f"Both are solid choices, but they serve different needs. "
        f"The {cheaper} flat at {cheap_p} offers {cheap_f} — it's more affordable and "
        f"{'centrally located' if NEIGHBOURHOODS[[n['name'] for n in NEIGHBOURHOODS].index(cheaper)]['tier'] == 'premium' else 'well-connected to major roads'}. "
        f"The {pricier} flat at {pricy_p} comes with {pricy_f} and is in a "
        f"{'premium' if NEIGHBOURHOODS[[n['name'] for n in NEIGHBOURHOODS].index(pricier)]['tier'] == 'premium' else 'growing'} locality — "
        f"better for long-term appreciation. "
        f"If budget is the priority, go with {cheaper}. If you want the better investment, "
        f"{pricier} has the edge. What matters most to you?"
    )
    return "compare_listings", [{"role": "user", "content": u},
                                  {"role": "assistant", "content": a_msg}]


def tpl_narrow_search() -> tuple[str, list[dict]]:
    area = _pick_area()
    bhk_val = _bhk()
    lo, hi = _budget_range(area)
    p = _price(area)
    floor = _floor()
    society = _society()
    feat = _feature()
    amenity = _amenity()
    lmark = _landmark(area)

    scenario = random.randint(0, 3)
    if scenario == 0:
        messages = [
            {"role": "user",
             "content": f"Show me {bhk_val}BHK flats in Surat under {_fmt_price(hi)}."},
            {"role": "assistant",
             "content": (
                 f"Found several {bhk_val}BHK flats under {_fmt_price(hi)}. "
                 f"{society} in {area['name']} at {_fmt_price(p)} (floor {floor}, {feat}); "
                 f"plus options in Katargam and Varachha from {_fmt_price(lo)}. "
                 f"Narrow by area, floor, or amenity?"
             )},
            {"role": "user",
             "content": f"Only show me ones in {area['name']} with parking."},
            {"role": "assistant",
             "content": (
                 f"In {area['name']} with parking: best fit is a {bhk_val}BHK in {society}, "
                 f"floor {floor}, {_fmt_price(p)}, with covered parking and {_feature()}. "
                 f"Ready to move in. Want to schedule a viewing?"
             )},
        ]
    elif scenario == 1:
        messages = [
            {"role": "user",
             "content": f"I want a flat near {lmark} in Surat, budget {_fmt_price(hi)}."},
            {"role": "assistant",
             "content": (
                 f"Near {lmark}, I have {bhk_val}BHK options in {area['name']} from "
                 f"{_fmt_price(lo)} to {_fmt_price(hi)}. "
                 f"{society} is a top pick at {_fmt_price(p)} with {feat}. "
                 f"Would you like only ready-to-move options?"
             )},
            {"role": "user",
             "content": "Yes, only ready-to-move. Also needs to be above 3rd floor."},
            {"role": "assistant",
             "content": (
                 f"Filtered to ready-to-move above 3rd floor near {lmark} — "
                 f"best match: {bhk_val}BHK in {society}, floor {max(floor, 4)}, "
                 f"{_fmt_price(p)}, with {_feature()}. Shall I arrange a viewing?"
             )},
        ]
    elif scenario == 2:
        messages = [
            {"role": "user",
             "content": f"Show me all 3BHK flats in {area['name']}."},
            {"role": "assistant",
             "content": (
                 f"In {area['name']}, 3BHK flats range from "
                 f"{_fmt_price(PRICE_BANDS[area['tier']]['flat_low'])} to "
                 f"{_fmt_price(PRICE_BANDS[area['tier']]['flat_high'])}. "
                 f"Top picks: {society} at {_fmt_price(p)} ({feat}). "
                 f"Want to filter by budget or floor?"
             )},
            {"role": "user",
             "content": f"Keep only those under {_fmt_price(p + 500000)} with a {amenity} nearby."},
            {"role": "assistant",
             "content": (
                 f"Narrowed down — {society} in {area['name']} at {_fmt_price(p)} fits: "
                 f"3BHK, {feat}, and a {amenity} within 10 minutes. "
                 f"This is one of the better-value options in that range. Interested?"
             )},
        ]
    else:
        messages = [
            {"role": "user",
             "content": f"I need a flat in Surat for my family. Budget is {_fmt_price(hi)}."},
            {"role": "assistant",
             "content": (
                 f"For a family budget of {_fmt_price(hi)}, I have good {bhk_val}BHK options "
                 f"across {area['name']}, Adajan, and Vesu. "
                 f"How many bedrooms do you need, and do you prefer a gated society?"
             )},
            {"role": "user",
             "content": f"We need {bhk_val}BHK and yes, gated society only."},
            {"role": "assistant",
             "content": (
                 f"Filtered to gated societies — {society} in {area['name']} is a great match: "
                 f"{bhk_val}BHK at {_fmt_price(p)}, with {feat}, "
                 f"24x7 security, and {amenity} nearby. Want to know more details?"
             )},
        ]
    return "narrow_search", messages


def tpl_off_topic() -> tuple[str, list[dict]]:
    q, a_msg = random.choice(OFF_TOPIC_QUESTIONS)
    return "off_topic", [{"role": "user", "content": q},
                          {"role": "assistant", "content": a_msg}]


def tpl_multi_turn_refinement() -> tuple[str, list[dict]]:
    area1 = _pick_area()
    area2 = random.choice([n for n in NEIGHBOURHOODS if n["name"] != area1["name"]])
    bhk_val = _bhk()
    p = _price(area2)
    floor = _floor()
    society = _society()
    feature = _feature()

    messages = [
        {"role": "user",
         "content": "I'm looking for a flat in Surat. Can you help?"},
        {"role": "assistant",
         "content": (
             "Of course! To help you find the right property, I have a few quick questions. "
             "What is your budget range? And do you have a preferred area in Surat, "
             "or are you open to suggestions?"
         )},
        {"role": "user",
         "content": f"My budget is around {_fmt_price(_price(area1))}. "
                    f"I prefer somewhere peaceful with good schools nearby."},
        {"role": "assistant",
         "content": (
             f"With that budget and those preferences, I'd suggest looking at {area1['name']} "
             f"or {area2['name']} — both are quieter localities with reputed schools nearby. "
             f"How many bedrooms do you need?"
         )},
        {"role": "user",
         "content": f"We need at least {bhk_val} bedrooms. We also have a car, so parking is a must."},
        {"role": "assistant",
         "content": (
             f"Noted — {bhk_val}BHK with parking. "
             f"I have a strong match: a {bhk_val}BHK in {society}, {area2['name']}, "
             f"priced at {_fmt_price(p)}. "
             f"It's on the {floor}th floor, includes {feature}, and has dedicated covered parking. "
             f"The society is gated with 24x7 security. "
             f"Would you like to book a viewing, or shall I show you other options in {area2['name']}?"
         )},
    ]
    return "multi_turn_refinement", messages


def tpl_property_type() -> tuple[str, list[dict]]:
    area = _pick_area()
    p_flat = _price(area, "flat")
    p_land = _price(area, "land")
    sqft = _sqft_land()
    bhk_val = _bhk()

    variations = [
        (
            f"What is the difference between a flat and a house_land listing in Surat?",
            f"In our listings, 'flat' refers to an apartment unit inside a multi-storey building "
            f"— typically fully built and ready to move in or under construction. "
            f"'House_land' (or plot) refers to a residential or mixed-use land parcel where "
            f"you own the land and can build as per your design (subject to local SUDA bylaws). "
            f"In {area['name']}, flats start around {_fmt_price(p_flat)}, while a "
            f"{sqft} sq ft plot starts at {_fmt_price(p_land)}. "
            f"Are you looking to buy or build?"
        ),
        (
            f"I want to buy a plot in {area['name']} and build my own house. Is that possible?",
            f"Yes, absolutely. {area['name']} has residential plots available for self-construction. "
            f"A {sqft} sq ft plot there is priced around {_fmt_price(p_land)}, "
            f"with SUDA approval and utilities (water, electricity, drainage) connected at the boundary. "
            f"You can typically build up to G+3 floors on residential plots in Surat. "
            f"Want details on available plots, or do you have a specific size in mind?"
        ),
    ]
    u, a_msg = random.choice(variations)
    return "property_type", [{"role": "user", "content": u},
                               {"role": "assistant", "content": a_msg}]


def tpl_investment() -> tuple[str, list[dict]]:
    area = _pick_area()
    bhk_val = _bhk()
    p = _price(area)
    rent_monthly = int(p * random.uniform(0.003, 0.005))
    annual_yield = round(rent_monthly * 12 / p * 100, 1)
    appreciation = random.choice([6, 7, 8, 9, 10, 12])

    variations = [
        (
            f"I want to invest in a property in Surat. Which area gives the best returns?",
            f"For rental yield, areas like Adajan, Vesu, and Citylight are strong performers — "
            f"gross rental yields typically range from 3% to 5% annually. "
            f"A {bhk_val}BHK in {area['name']} priced at {_fmt_price(p)} could fetch around "
            f"Rs.{rent_monthly:,}/month in rent, giving you roughly {annual_yield}% yield. "
            f"For capital appreciation, areas like Althan and Pal are growing fast. "
            f"Is your priority monthly rental income or long-term value growth?"
        ),
        (
            f"Is a flat in {area['name']} a good investment right now?",
            f"{area['name']} has seen around {appreciation}% year-on-year price appreciation recently. "
            f"A {bhk_val}BHK there at {_fmt_price(p)} is a {'solid' if area['tier'] == 'premium' else 'reasonable'} "
            f"investment — especially given its proximity to {_landmark(area)}. "
            f"Rental demand is also healthy, with tenants typically paying around "
            f"Rs.{rent_monthly:,}/month for a well-maintained unit. "
            f"Would you like to compare this with another area?"
        ),
    ]
    u, a_msg = random.choice(variations)
    return "investment", [{"role": "user", "content": u},
                           {"role": "assistant", "content": a_msg}]


def tpl_viewing_request() -> tuple[str, list[dict]]:
    area = _pick_area()
    bhk_val = _bhk()
    p = _price(area)
    society = _society()
    floor = _floor()
    day = random.choice(["Saturday", "Sunday", "Monday", "Wednesday"])
    time_slot = random.choice(["10 AM", "11 AM", "3 PM", "5 PM", "6 PM"])

    messages = [
        {"role": "user",
         "content": f"I'm interested in the {bhk_val}BHK in {society}, {area['name']}. "
                    f"Can I schedule a visit?"},
        {"role": "assistant",
         "content": (
             f"Great choice! The {bhk_val}BHK in {society}, {area['name']} — "
             f"priced at {_fmt_price(p)}, floor {floor} — is available for viewing. "
             f"The broker managing this listing typically schedules visits between 10 AM and 7 PM. "
             f"What day works best for you? Weekends are usually easiest for the seller."
         )},
        {"role": "user",
         "content": f"Can we do {day} at {time_slot}?"},
        {"role": "assistant",
         "content": (
             f"{day} at {time_slot} sounds good. I'll flag your interest and the listing broker "
             f"will reach out to confirm. In the meantime, would you like me to check if there are "
             f"any other similar {bhk_val}BHK listings in {area['name']} as backup options?"
         )},
    ]
    return "viewing_request", messages


# ---------------------------------------------------------------------------
# Master template registry
# ---------------------------------------------------------------------------
TEMPLATES = [
    tpl_budget_price,
    tpl_location_proximity,
    tpl_amenity_specific,
    tpl_compare_listings,
    tpl_narrow_search,
    tpl_off_topic,
    tpl_multi_turn_refinement,
    tpl_property_type,
    tpl_investment,
    tpl_viewing_request,
]

# Weights — slightly upweight the core intents, keep off-topic rare
TEMPLATE_WEIGHTS = [13, 13, 11, 9, 11, 11, 11, 7, 7, 7]


def _build_example() -> tuple[str, dict[str, Any]]:
    """Pick a random template, generate messages, wrap in chat format."""
    tpl_fn = random.choices(TEMPLATES, weights=TEMPLATE_WEIGHTS, k=1)[0]
    category, turn_messages = tpl_fn()
    example = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            *turn_messages,
        ]
    }
    return category, example


def _hash_example(example: dict) -> str:
    """Hash the user turns to detect near-duplicates."""
    user_text = " ".join(
        m["content"] for m in example["messages"] if m["role"] == "user"
    )
    return hashlib.sha256(user_text.encode()).hexdigest()


def _write_dataset(
    output_path: str,
    n_examples: int,
    max_retries: int = 20,
    label: str = "dataset",
) -> None:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    category_counts: dict[str, int] = {c: 0 for c in CATEGORY_NAMES}
    seen_hashes: set[str] = set()
    written = 0
    total_attempts = 0

    with out.open("w", encoding="utf-8") as f:
        while written < n_examples:
            retries = 0
            while retries < max_retries:
                category, example = _build_example()
                h = _hash_example(example)
                total_attempts += 1
                if h not in seen_hashes:
                    seen_hashes.add(h)
                    break
                retries += 1
            else:
                # Exhausted retries — skip and warn (shouldn't happen at scale)
                print(f"  [WARN] Could not generate unique example after "
                      f"{max_retries} retries (written={written}). Skipping.")
                continue

            f.write(json.dumps(example, ensure_ascii=False) + "\n")
            category_counts[category] = category_counts.get(category, 0) + 1
            written += 1

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n[OK] {label}: wrote {written} examples to {output_path}")
    print(f"     Dedup: {total_attempts - written} duplicates dropped")
    print(f"     Category breakdown:")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        bar = "#" * (count * 30 // max(category_counts.values()))
        print(f"       {cat:<25} {count:>4}  {bar}")
    print()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_debug_dataset(
    output_path: str = "ai/finetune/data/debug_dataset.jsonl",
    n_examples: int = 100,
) -> None:
    """Generate a small debug dataset (100 examples) for pipeline smoke-testing.

    Args:
        output_path: Path to write the JSONL file.
        n_examples:  Number of training examples to generate.
    """
    random.seed(SEED)
    _write_dataset(output_path, n_examples, label="debug dataset")


def generate_full_dataset(
    output_path: str = "ai/finetune/data/full_dataset.jsonl",
    n_examples: int = 750,
) -> None:
    """Generate the full training dataset (750 examples) for fine-tuning.

    Includes deduplication: any example whose user turns hash-collide with a
    previously written example is discarded and regenerated (up to 10 retries).

    Args:
        output_path: Path to write the JSONL file.
        n_examples:  Number of training examples to generate.
    """
    random.seed(SEED)
    _write_dataset(output_path, n_examples, max_retries=10, label="full dataset")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate synthetic fine-tuning data for the RealityAI chat assistant."
    )
    parser.add_argument(
        "--mode",
        choices=["debug", "full"],
        required=True,
        help="'debug' generates 100 examples; 'full' generates 750 examples.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Override the output file path (optional).",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=None,
        help="Override the number of examples (optional).",
    )
    args = parser.parse_args()

    if args.mode == "debug":
        kwargs: dict[str, Any] = {}
        if args.output:
            kwargs["output_path"] = args.output
        if args.n:
            kwargs["n_examples"] = args.n
        generate_debug_dataset(**kwargs)
    else:
        kwargs = {}
        if args.output:
            kwargs["output_path"] = args.output
        if args.n:
            kwargs["n_examples"] = args.n
        generate_full_dataset(**kwargs)
