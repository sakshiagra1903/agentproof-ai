
import re
from collections import Counter
from typing import Any

TOKEN_RE = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)?", re.I)


def tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text or "")]


def lexical_similarity(answer: str, reference: str) -> float | None:
    answer_tokens = tokens(answer)
    reference_tokens = tokens(reference)

    if not answer_tokens or not reference_tokens:
        return None

    answer_counts = Counter(answer_tokens)
    reference_counts = Counter(reference_tokens)
    overlap = sum((answer_counts & reference_counts).values())

    # Lexical similarity only; this does not prove semantic correctness.
    return round(
        2 * overlap / (sum(answer_counts.values()) + sum(reference_counts.values())),
        4,
    )


def keyword_coverage(answer: str, keywords: list[str]) -> float | None:
    if not keywords:
        return None

    normalized_answer = (answer or "").casefold()
    usable_keywords = [keyword for keyword in keywords if keyword.strip()]

    if not usable_keywords:
        return None

    return round(
        sum(
            1
            for keyword in usable_keywords
            if keyword.casefold() in normalized_answer
        )
        / len(usable_keywords),
        4,
    )


def context_overlap(answer: str, context: str) -> float | None:
    answer_tokens = set(tokens(answer))
    context_tokens = set(tokens(context))

    if not answer_tokens or not context_tokens:
        return None

    # A lexical proxy, not proof that the answer is grounded.
    return round(
        len(answer_tokens & context_tokens) / len(answer_tokens),
        4,
    )


def evaluate_case(
    case: dict[str, Any],
    threshold: float = 0.65,
) -> dict[str, Any]:
    answer = (case.get("actual_answer") or "").strip()
    expected = (case.get("expected_answer") or "").strip()
    context = (case.get("reference_context") or "").strip()

    expected_citations = case.get("expected_citations") or []
    actual_citations = case.get("actual_citations") or []
    sources = case.get("source_documents") or []

    source_ids = {
        str(source.get("id", ""))
        for source in sources
        if isinstance(source, dict) and source.get("id")
    }

    expected_tools = case.get("expected_tool_calls") or []
    actual_tools = case.get("actual_tool_calls") or []

    if expected_citations:
        citation_presence = round(
            sum(
                1
                for citation in expected_citations
                if citation in actual_citations
            )
            / len(expected_citations),
            4,
        )
    else:
        citation_presence = None

    if sources and actual_citations:
        citation_source_validity = round(
            sum(
                1
                for citation in actual_citations
                if citation in source_ids
            )
            / len(actual_citations),
            4,
        )
    elif sources and expected_citations and not actual_citations:
        citation_source_validity = 0.0
    else:
        citation_source_validity = None

    if expected_tools:
        tool_call_match = round(
            sum(
                1 for tool in expected_tools if tool in actual_tools
            )
            / len(expected_tools),
            4,
        )
    else:
        tool_call_match = None

    metrics = {
        "keyword_coverage": keyword_coverage(
            answer,
            case.get("expected_keywords") or [],
        ),
        "answer_lexical_similarity": lexical_similarity(answer, expected),
        "context_word_overlap": context_overlap(answer, context),
        "citation_presence": citation_presence,
        "citation_source_validity": citation_source_validity,
        "tool_call_match": tool_call_match,
    }

    reasons = []

    if not answer:
        reasons.append("Answer is empty.")

    if not context:
        reasons.append(
            "Reference context is missing; grounding cannot be assessed."
        )

    if (
        metrics["keyword_coverage"] is not None
        and metrics["keyword_coverage"] < threshold
    ):
        reasons.append(
            f"Expected-keyword coverage "
            f"{metrics['keyword_coverage']:.2f} is below threshold "
            f"{threshold:.2f}."
        )

    if (
        metrics["answer_lexical_similarity"] is not None
        and metrics["answer_lexical_similarity"] < threshold
    ):
        reasons.append(
            f"Answer/reference lexical similarity "
            f"{metrics['answer_lexical_similarity']:.2f} "
            f"is below threshold {threshold:.2f}."
        )

    if (
        metrics["context_word_overlap"] is not None
        and metrics["context_word_overlap"] < threshold
    ):
        reasons.append(
            f"Context-word overlap "
            f"{metrics['context_word_overlap']:.2f} "
            f"is below threshold {threshold:.2f}."
        )

    if (
        metrics["citation_presence"] is not None
        and metrics["citation_presence"] < 1
    ):
        reasons.append(
            "One or more expected citation labels are absent."
        )

    if (
        metrics["citation_source_validity"] is not None
        and metrics["citation_source_validity"] < 1
    ):
        reasons.append(
            "One or more supplied citation IDs do not match "
            "the provided source documents."
        )

    if (
        metrics["tool_call_match"] is not None
        and metrics["tool_call_match"] < 1
    ):
        reasons.append(
            "One or more expected tool calls are missing "
            "from the recorded tool-call list."
        )

    # Citation presence is enforced as a hard failure separately.
    applicable = [
        value
        for key, value in metrics.items()
        if value is not None and key != "citation_presence"
    ]

    if not answer:
        applicable = []

    elif not context:
        applicable = [
            value
            for key, value in metrics.items()
            if key in ("keyword_coverage", "answer_lexical_similarity")
            and value is not None
        ]

    score = (
        round(sum(applicable) / len(applicable), 4)
        if applicable
        else None
    )

    hard_failure = (
        (
            metrics["citation_presence"] is not None
            and metrics["citation_presence"] < 1
        )
        or (
            metrics["citation_source_validity"] is not None
            and metrics["citation_source_validity"] < 1
        )
        or (
            metrics["tool_call_match"] is not None
            and metrics["tool_call_match"] < 1
        )
    )

    if score is None:
        status = "unscored"
    elif score >= threshold and answer and not hard_failure:
        status = "passed"
    else:
        status = "failed"

    if status == "unscored":
        reasons.append(
            "No applicable scoring metrics; case is unscored, "
            "not a perfect score."
        )
    elif status == "passed" and reasons:
        reasons.append(
            "Score meets threshold, but review the warnings above."
        )

    return {
        "case_id": case.get("id", "unknown"),
        "question": case.get("question", ""),
        "expected_answer": expected,
        "actual_answer": answer,
        "reference_context": context,
        "expected_citations": case.get("expected_citations", []),
        "actual_citations": case.get("actual_citations", []),
        "source_documents": sources,
        "expected_tool_calls": expected_tools,
        "actual_tool_calls": actual_tools,
        "metrics": metrics,
        "score": score,
        "status": status,
        "failure_reasons": reasons,
    }


def evaluate_cases(
    cases: list[dict[str, Any]],
    threshold: float = 0.65,
    actual_answers: dict[str, str] | None = None,
) -> dict[str, Any]:
    actual_answers = actual_answers or {}
    results = []

    for original in cases:
        case = dict(original)

        # Explicit answer overrides always take precedence.
        if case.get("id") in actual_answers:
            case["actual_answer"] = actual_answers[case["id"]]

        # Deterministic offline demo mode.
        # Reference answers are mock outputs, not real model generations.
        if case.get("actual_answer") is None:
            case["actual_answer"] = case.get("expected_answer", "")

            # Simulate expected citations only for default mock answers.
            # This does NOT validate citations produced by a real model.
            case["actual_citations"] = list(
                case.get("expected_citations") or []
            )

        results.append(evaluate_case(case, threshold))

    scored = [
        result for result in results
        if result["score"] is not None
    ]

    passed = sum(
        result["status"] == "passed" for result in results
    )
    failed = sum(
        result["status"] == "failed" for result in results
    )
    unscored = sum(
        result["status"] == "unscored" for result in results
    )

    return {
        "results": results,
        "summary": {
            "total_cases": len(results),
            "scored_cases": len(scored),
            "passed_cases": passed,
            "failed_cases": failed,
            "unscored_cases": unscored,
            "pass_rate": (
                round(passed / len(scored), 4)
                if scored
                else None
            ),
            "average_score": (
                round(
                    sum(result["score"] for result in scored)
                    / len(scored),
                    4,
                )
                if scored
                else None
            ),
            "pass_threshold": threshold,
        },
    }
