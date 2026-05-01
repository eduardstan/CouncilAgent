"""Generate ``tests/calibrate/fixtures/gsm8k_subset.json`` from real
OpenRouter predictions on a small GSM8K subset.

Run manually (never by CI; consumes paid-API quota):

    uv run python experiments/fixtures/gen_gsm8k_calibration.py \\
        [--n-questions 16] [--models <id> ...]

Reads ``OPENROUTER_API_KEY`` from ``.env`` (auto-loaded via
python-dotenv). The output JSON is consumed by
``tests/integration/test_calibration_real_models.py`` to verify the
master-plan-§7-W3 acceptance ("ECE on a held-out GSM8K split drops
below 0.05") on real model outputs. ADR-0018 documents the two-tier
fixture strategy that motivates this script's existence.

The default slate is small *paid* models routed through OpenRouter.
The previously planned free-tier slate (gemma-3-27b-it:free etc.)
was abandoned on 2026-05-01 because two of the three IDs returned
``404`` from OpenRouter and the third did not return logprobs while
also rate-limiting on a 32-question probe.

**Confidence source — hybrid.** Empirically, paid OpenAI models
return token logprobs through OpenRouter while paid Qwen / Gemini
routes do not. We therefore implement a hybrid signal:

  1. Always ask the model for a verbal confidence percentage in the
     prompt (Tian et al. 2023, "Just Ask for Calibration", arXiv
     2305.14975). This costs nothing extra on top of the solution.
  2. If the response carries token logprobs, derive raw_confidence as
     ``mean(exp(logprob))`` over generated tokens (the canonical
     uncertainty signal).
  3. Otherwise fall back to the parsed verbal percentage.

The chosen source is recorded per-sample as ``confidence_source ∈
{"logprob_mean_exp", "verbal_self_reported"}`` so downstream analysis
can stratify by signal type.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "tests" / "calibrate" / "fixtures" / "gsm8k_subset.json"

#: Paid SLM slate; replaces the deprecated free-tier slate (see module
#: docstring + ADR-0018 history).
DEFAULT_MODELS = (
    "openrouter/openai/gpt-4.1-nano",
    "openrouter/qwen/qwen3.5-flash-02-23",
    "openrouter/google/gemini-2.5-flash-lite",
)

PROMPT = (
    "Solve this grade-school math problem step by step. After your "
    "solution, on a new line, write 'The answer is <integer>.'. Then "
    "on the next line, write 'Confidence: <integer>%' where the "
    "integer (0-100) reflects how confident you are that your answer "
    "is correct.\n\nProblem: {q}\n\nSolution:"
)


def _gold(answer_text: str) -> str | None:
    m = re.search(r"####\s*([-+]?[\d,]+)", answer_text)
    return m.group(1).replace(",", "") if m else None


def _predicted(text: str) -> str | None:
    m = re.search(r"answer is[:\s]*([-+]?[\d,]+)", text, re.IGNORECASE)
    return m.group(1).replace(",", "") if m else None


def _verbal_confidence(text: str) -> float | None:
    m = re.search(r"confidence[:\s]*(\d{1,3})\s*%", text, re.IGNORECASE)
    if m is None:
        return None
    pct = int(m.group(1))
    if not 0 <= pct <= 100:
        return None
    return pct / 100.0


def _logprob_confidence(response: Any) -> float | None:
    """mean(exp(logprob)) over generated tokens, or None if not exposed."""
    try:
        choice = response.choices[0]
        lp = getattr(choice, "logprobs", None)
        if lp is None:
            return None
        content = getattr(lp, "content", None)
        if not content:
            return None
        logs = [tok.logprob for tok in content if tok.logprob is not None]
        if not logs:
            return None
        return float(min(1.0, max(0.0, math.exp(sum(logs) / len(logs)))))
    except (AttributeError, IndexError, TypeError):
        return None


def _query_with_retry(
    model: str, question: str, *, max_retries: int = 3
) -> tuple[str, float | None, str]:
    """Returns (text, raw_confidence_or_None, confidence_source)."""
    import litellm

    backoff = 4.0
    last_exc: Exception | None = None
    for _ in range(max_retries):
        try:
            response = litellm.completion(
                model=model,
                messages=[{"role": "user", "content": PROMPT.format(q=question)}],
                temperature=0.0,
                max_tokens=512,
                logprobs=True,
                top_logprobs=1,
            )
            text = response.choices[0].message.content or ""
            lp_conf = _logprob_confidence(response)
            if lp_conf is not None:
                return text, lp_conf, "logprob_mean_exp"
            verbal = _verbal_confidence(text)
            if verbal is not None:
                return text, verbal, "verbal_self_reported"
            return text, None, "none"
        except Exception as exc:
            last_exc = exc
            msg = str(exc)
            if "429" in msg or "RateLimit" in msg:
                time.sleep(backoff)
                backoff *= 2
                continue
            raise
    raise RuntimeError(f"max retries hit for {model}") from last_exc


def _load_questions(n: int, seed: int) -> list[dict[str, str]]:
    from datasets import load_dataset

    ds = load_dataset("gsm8k", "main", split="test")
    shuffled = ds.shuffle(seed=seed)
    return [
        {"id": f"gsm8k:test:{i}", "question": row["question"], "answer": row["answer"]}
        for i, row in enumerate(shuffled.select(range(n)))
    ]


def main() -> int:
    if "OPENROUTER_API_KEY" not in os.environ:
        try:
            from dotenv import load_dotenv

            load_dotenv(REPO_ROOT / ".env")
        except ImportError:
            pass
    if "OPENROUTER_API_KEY" not in os.environ:
        sys.stderr.write("OPENROUTER_API_KEY not set (export or place in .env).\n")
        return 2

    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--n-questions", type=int, default=16)
    p.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    questions = _load_questions(args.n_questions, args.seed)
    samples: list[dict[str, Any]] = []
    skipped_no_conf = 0
    skipped_failure = 0
    for q in questions:
        gold = _gold(q["answer"])
        if gold is None:
            continue
        for model in args.models:
            try:
                text, conf, source = _query_with_retry(model, q["question"])
            except Exception as exc:
                skipped_failure += 1
                print(f"  {model} {q['id']} FAILED: {str(exc)[:80]}", file=sys.stderr)
                continue
            if conf is None:
                skipped_no_conf += 1
                print(
                    f"  {model} {q['id']} skipped (no confidence signal)",
                    file=sys.stderr,
                )
                continue
            pred = _predicted(text)
            correct = int(pred is not None and pred == gold)
            samples.append(
                {
                    "question_id": q["id"],
                    "model": model,
                    "raw_confidence": conf,
                    "gold_correct": correct,
                    "confidence_source": source,
                }
            )
            print(
                f"  {model} {q['id']} src={source} conf={conf:.3f} "
                f"correct={correct}",
                file=sys.stderr,
            )

    payload = {
        "schema_version": 2,
        "generator": "experiments/fixtures/gen_gsm8k_calibration.py",
        "models": list(args.models),
        "n_questions": len(questions),
        "confidence_source": "hybrid: logprob_mean_exp when available, "
                              "else verbal_self_reported (Tian et al. 2023)",
        "samples": samples,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    sys.stderr.write(
        f"\nWrote {len(samples)} samples to {args.output} "
        f"(skipped {skipped_no_conf} no-confidence, {skipped_failure} failures)\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
