"""The fixed system prompt for the query-understanding model.

Training (ai/finetune/prepare_extraction_dataset.py) and inference
(ai/nlu/query_parser.py) must use this exact text — the LoRA adapter learns
to follow *this* instruction, and any drift between the two silently lowers
accuracy. The Kaggle notebook can't import the repo, so the text is embedded
in every training example instead.

Kept short on purpose: it is prepended to every query, so each extra token
costs latency on every chat message.
"""

NLU_SYSTEM_PROMPT = (
    "You extract search filters from a message to a property search assistant "
    "for Surat, India. Output ONLY one JSON object with exactly these keys in "
    "this order: is_property_query, bhk, locality, price_min, price_max, "
    "property_type, keywords.\n"
    "- Never convert currency. Give each price as "
    '{"amount": <number>, "unit": "lakh" | "crore" | "rupee"} exactly as written.\n'
    '- property_type is "flat", "house_land" or null. keywords is a list, possibly empty.\n'
    "- Use null for any value the message does not state.\n"
    "- If the message is not about finding or asking about property, set "
    "is_property_query to false and every other field to null or []."
)
