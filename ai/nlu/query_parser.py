"""Query understanding entry point: model + rules, validated, merged and cached.

``parse_query(query)`` always returns a ``ParsedQuery`` and never raises.

Backends (env var NLU_BACKEND):
  hybrid (default) — run the rules parser and the fine-tuned model, then merge:
      prices from rules when rules found one (regex arithmetic is exact and
      tested); bhk, locality and property type from the model, falling back
      to rules where the model left a field empty; keywords from both. The
      model's locality is kept only if the query text supports it (fuzzy
      match against the place's names), so an invented place can't silently
      filter results. If the model says "not a property query" while rules
      found two or more property signals, rules win. If the model is
      unavailable or its output is invalid, rules alone.
  rules  — rules parser only (what runs on machines without a GPU).
  model  — the model's validated output as-is, no merge (for fair evaluation);
      still falls back to rules if the model is unavailable or invalid.

Results are cached per (backend, normalized query), so retriever.search() and
generate_response() can both call parse_query() for the same message without
running the model twice.
"""

from __future__ import annotations

import functools
import logging
import os
import threading
import time
from dataclasses import replace
from typing import Any

from rapidfuzz import fuzz

from ai.nlu.gazetteer import surface_forms
from ai.nlu.prompt import NLU_SYSTEM_PROMPT
from ai.nlu.rules import parse_with_rules
from ai.nlu.schema import ParsedQuery, extract_first_json, validate_model_output

logger = logging.getLogger(__name__)

BACKEND_ENV = "NLU_BACKEND"
_BACKENDS = ("hybrid", "rules", "model")
_DEFAULT_BACKEND = "hybrid"

MAX_QUERY_CHARS = 500
MAX_NEW_TOKENS = 160      # the JSON is ~60-90 tokens
_RULES_OVERRIDE_SIGNALS = 2
# rapidfuzz partial_ratio of a place's name/alias against the query. On the eval
# set every correct locality scores >= 86 ("vr mal"); "villas batavo" -> Bhatar
# (a model hallucination) scores 67.
_LOCALITY_GROUNDING_MIN = 80

# One generate() at a time: the backend may call from several worker threads,
# and concurrent generation on one small GPU only adds memory pressure.
_generate_lock = threading.Lock()
_warned_unavailable = False
_model_failed = False     # set after a failed load so we don't retry on every request


def _backend() -> str:
    value = os.getenv(BACKEND_ENV, _DEFAULT_BACKEND).strip().lower()
    if value not in _BACKENDS:
        logger.warning("Unknown %s=%r; using %r.", BACKEND_ENV, value, _DEFAULT_BACKEND)
        return _DEFAULT_BACKEND
    return value


def _warn_unavailable_once(reason: str) -> None:
    global _warned_unavailable
    if not _warned_unavailable:
        logger.warning("NLU model unavailable, using rules-based parsing: %s", reason)
        _warned_unavailable = True


def _generate(query: str) -> str:
    """Run the fine-tuned model on one query and return its raw text output.

    Raises ModelUnavailableError if the model can't be loaded.
    """
    import torch

    from ai.inference.load_model import get_model

    model, tokenizer = get_model()
    template = tokenizer.chat_template or ""
    kwargs: dict[str, Any] = {"enable_thinking": False} if "enable_thinking" in template else {}
    messages = [{"role": "system", "content": NLU_SYSTEM_PROMPT}, {"role": "user", "content": query}]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, **kwargs)
    inputs = tokenizer(text, return_tensors="pt", add_special_tokens=False).to(model.device)
    with _generate_lock, torch.no_grad():
        output = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False,
                                pad_token_id=tokenizer.pad_token_id)
    return tokenizer.decode(output[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)


def _model_parse(query: str) -> ParsedQuery | None:
    """Validated model output, or None if the model is unavailable or its output is invalid."""
    global _model_failed
    if _model_failed:
        return None

    from ai.inference.load_model import ModelUnavailableError, is_model_available

    if not is_model_available():
        _warn_unavailable_once("no GPU or no adapter (see ai/inference/load_model.py)")
        return None
    try:
        raw = _generate(query)
    except ModelUnavailableError as exc:
        _model_failed = True
        _warn_unavailable_once(str(exc))
        return None
    except Exception:
        logger.exception("NLU generation failed for query=%r; using rules.", query[:80])
        return None

    parsed = validate_model_output(extract_first_json(raw))
    if parsed is None:
        logger.info("Invalid NLU model output for query=%r: %r — using rules.", query[:80], raw[:200])
    return parsed


def _signal_count(pq: ParsedQuery) -> int:
    return sum((
        pq.bhk is not None,
        pq.locality is not None,
        pq.price_min is not None or pq.price_max is not None,
        pq.property_type is not None,
        bool(pq.keywords),
    ))


def _locality_grounded(locality: str, query: str) -> bool:
    """True if some name or alias of *locality* (fuzzily) appears in *query*."""
    text = query.lower()
    return any(fuzz.partial_ratio(surface, text) >= _LOCALITY_GROUNDING_MIN
               for surface in surface_forms(locality))


def merge(rules: ParsedQuery, model: ParsedQuery, query: str = "") -> ParsedQuery:
    """Hybrid merge of a rules parse and a validated model parse (see module docstring)."""
    if not model.is_property_query:
        if _signal_count(rules) >= _RULES_OVERRIDE_SIGNALS:
            logger.warning("Model said not a property query but rules found %d signals; "
                           "trusting rules. query=%r", _signal_count(rules), query[:80])
            return replace(rules, source="hybrid")
        return ParsedQuery(is_property_query=False, source="hybrid")

    locality = model.locality
    if locality is not None and query and locality != rules.locality \
            and not _locality_grounded(locality, query):
        logger.info("Dropping model locality %r: not found in query=%r", locality, query[:80])
        locality = None

    rules_has_price = rules.price_min is not None or rules.price_max is not None
    return ParsedQuery(
        is_property_query=True,
        bhk=model.bhk if model.bhk is not None else rules.bhk,
        locality=locality if locality is not None else rules.locality,
        price_min=rules.price_min if rules_has_price else model.price_min,
        price_max=rules.price_max if rules_has_price else model.price_max,
        property_type=model.property_type or rules.property_type,
        keywords=tuple(dict.fromkeys(model.keywords + rules.keywords)),
        source="hybrid",
    )


def _normalize(query: Any) -> str:
    if not isinstance(query, str):
        return ""
    return query.strip()[:MAX_QUERY_CHARS]


@functools.lru_cache(maxsize=256)
def _parse_cached(query: str, backend: str) -> ParsedQuery:
    t0 = time.perf_counter()
    rules = parse_with_rules(query)
    result = rules
    if backend != "rules":
        model = _model_parse(query)
        if model is not None:
            result = model if backend == "model" else merge(rules, model, query)
    logger.debug("parse_query source=%s %.1fms: %s", result.source,
                 (time.perf_counter() - t0) * 1000, result.describe())
    return result


def parse_query(query: str) -> ParsedQuery:
    """Parse one customer message into structured filters. Never raises.

    Empty input is not a property query. Inputs longer than 500 characters are
    truncated before parsing.
    """
    normalized = _normalize(query)
    if not normalized:
        return ParsedQuery(is_property_query=False, source="rules")
    try:
        return _parse_cached(normalized, _backend())
    except Exception:
        logger.exception("parse_query() failed for query=%r; falling back to rules.", normalized[:80])
        try:
            return parse_with_rules(normalized)
        except Exception:
            return ParsedQuery(is_property_query=False, source="rules")


def cache_clear() -> None:
    """Clear the parse cache and the "model failed" flag (tests, evaluation, reloads)."""
    global _model_failed, _warned_unavailable
    _parse_cached.cache_clear()
    _model_failed = False
    _warned_unavailable = False


# ai/nlu/evaluate.py calls parse_query.cache_clear() between runs.
parse_query.cache_clear = cache_clear  # type: ignore[attr-defined]
