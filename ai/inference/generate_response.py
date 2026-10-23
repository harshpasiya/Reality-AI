"""Final response generation: prompt -> model -> reply text.

Orchestrates the full inference pipeline: builds a structured prompt from
the query, retrieved listings, and conversation history, then generates
a response via the fine-tuned model singleton.
"""

from __future__ import annotations

import logging
import time

import torch

from ai.inference.load_model import get_model
from ai.rag.prompt_templates import build_prompt

logger = logging.getLogger(__name__)

# Generation parameters — chosen for a grounded, conversational assistant
# rather than creative/open-ended generation.
MAX_NEW_TOKENS = 300          # enough for a full answer, caps runaway generation
TEMPERATURE = 0.7             # natural but grounded, not overly random
TOP_P = 0.9
REPETITION_PENALTY = 1.15     # discourage repetitive listing-dumping

_FALLBACK_REPLY = (
    "I'm having trouble responding right now \u2014 could you try rephrasing your question?"
)


def generate_response(query: str, listings: list[dict], history: list[dict] | None) -> str:
    """Generate the assistant's reply to a customer query.

    Matches the signature documented in AGENTS.md exactly — Person 2's
    /chat route calls this directly.

    Args:
        query: The customer's current message.
        listings: Retrieved listings from ai.rag.retriever.search().
        history: Prior conversation turns (oldest first), or None.

    Returns:
        The generated reply text. On any failure, returns a graceful
        fallback string rather than raising — a broken /chat response is
        worse than an apologetic one, and the caller (Person 2's backend)
        shouldn't have to handle a generation exception specially.
    """
    try:
        model, tokenizer = get_model()

        messages = build_prompt(query, listings, history)
        prompt_text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(prompt_text, return_tensors="pt").to(model.device)
        input_length = inputs["input_ids"].shape[1]

        t0 = time.time()
        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                temperature=TEMPERATURE,
                top_p=TOP_P,
                repetition_penalty=REPETITION_PENALTY,
                do_sample=True,
                pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
            )
        elapsed = time.time() - t0

        # Decode only the newly generated tokens, not the echoed prompt.
        new_tokens = output_ids[0][input_length:]
        reply = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

        logger.info(
            "generate_response() took %.2fs (%d new tokens, query=%r)",
            elapsed, len(new_tokens), query[:60],
        )

        if not reply:
            logger.warning("Model returned an empty reply for query=%r", query[:60])
            return _FALLBACK_REPLY

        return reply

    except Exception:
        logger.exception("generate_response() failed for query=%r", query[:60])
        return _FALLBACK_REPLY
