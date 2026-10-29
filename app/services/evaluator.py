import re
from collections import Counter
from typing import Any

TOKEN_RE = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)?", re.I)

def tokens(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or '')]

def lexical_similarity(answer: str, reference: str) -> float | None:
    a, b = tokens(answer), tokens(reference)
    if not a or not b: return None
    ca, cb = Counter(a), Counter(b)
    overlap = sum((ca & cb).values())
    # Token multiset Dice similarity: lexical only, not semantic equivalence.
    return round(2 * overlap / (sum(ca.values()) + sum(cb.values())), 4)

def keyword_coverage(answer: str, keywords: list[str]) -> float | None:
    if not keywords: return None
    a=(answer or '').casefold()
    return round(sum(1 for k in keywords if k.strip() and k.casefold() in a) / len(keywords), 4)

def context_overlap(answer: str, context: str) -> float | None:
    at=set(tokens(answer)); ct=set(tokens(context))
    if not at or not ct: return None
    # Fraction of answer tokens present in the supplied context; simple proxy only.
    return round(len(at & ct) / len(at), 4)

def evaluate_case(case: dict[str, Any], threshold: float = .65) -> dict[str, Any]:
    answer = (case.get('actual_answer') or '').strip()
    expected = (case.get('expected_answer') or '').strip()
    context = (case.get('reference_context') or '').strip()
    expected_citations = case.get('expected_citations') or []
    actual_citations = case.get('actual_citations') or []
    sources = case.get('source_documents') or []
    source_ids = {str(x.get('id', '')) for x in sources if isinstance(x, dict) and x.get('id')}
    citation_ids_found = [c for c in actual_citations if c in source_ids] if sources else []
    expected_tools = case.get('expected_tool_calls') or []
    actual_tools = case.get('actual_tool_calls') or []
    metrics = {
      'keyword_coverage': keyword_coverage(answer, case.get('expected_keywords') or []),
      'answer_lexical_similarity': lexical_similarity(answer, expected),
      'context_word_overlap': context_overlap(answer, context),
      'citation_presence': (round(sum(1 for c in expected_citations if c in actual_citations) / len(expected_citations), 4) if expected_citations else None),
      'citation_source_validity': (round(sum(1 for c in actual_citations if c in source_ids) / len(actual_citations), 4) if sources and actual_citations else (0.0 if sources and expected_citations and actual_citations else None)),
      'tool_call_match': (round(sum(1 for tool in expected_tools if tool in actual_tools) / len(expected_tools), 4) if expected_tools else None),
    }
    reasons=[]
    if not answer: reasons.append('Answer is empty.')
    if not context: reasons.append('Reference context is missing; grounding cannot be assessed.')
    if metrics['keyword_coverage'] is not None and metrics['keyword_coverage'] < threshold:
        reasons.append(f"Expected-keyword coverage {metrics['keyword_coverage']:.2f} is below threshold {threshold:.2f}.")
    if metrics['answer_lexical_similarity'] is not None and metrics['answer_lexical_similarity'] < threshold:
        reasons.append(f"Answer/reference lexical similarity {metrics['answer_lexical_similarity']:.2f} is below threshold {threshold:.2f}.")
    if metrics['context_word_overlap'] is not None and metrics['context_word_overlap'] < threshold:
        reasons.append(f"Context-word overlap {metrics['context_word_overlap']:.2f} is below threshold {threshold:.2f}.")
    if metrics['citation_presence'] is not None and metrics['citation_presence'] < 1:
        reasons.append('One or more expected citation labels are absent.')
    if metrics['citation_source_validity'] is not None and metrics['citation_source_validity'] < 1:
        reasons.append('One or more supplied citation IDs do not match the provided source documents.')
    if metrics['tool_call_match'] is not None and metrics['tool_call_match'] < 1:
        reasons.append('One or more expected tool calls are missing from the recorded tool-call list.')
    applicable=[v for k,v in metrics.items() if v is not None and k != 'citation_presence']
    if not answer: applicable=[]
    if not context: applicable=[v for k,v in metrics.items() if v is not None and k in ('keyword_coverage','answer_lexical_similarity') and answer]
    score=round(sum(applicable)/len(applicable),4) if applicable else None
    hard_failure = (metrics['citation_source_validity'] is not None and metrics['citation_source_validity'] < 1) or (metrics['tool_call_match'] is not None and metrics['tool_call_match'] < 1)
    status='unscored' if score is None else ('passed' if score >= threshold and answer and not hard_failure else 'failed')
    if status == 'unscored': reasons.append('No applicable scoring metrics; case is unscored, not a perfect score.')
    elif status == 'passed' and reasons: reasons.append('Score meets threshold, but review the warnings above.')
    return {'case_id':case.get('id','unknown'),'question':case.get('question',''),'expected_answer':expected,
      'actual_answer':answer,'reference_context':context,'expected_citations':case.get('expected_citations',[]),
      'actual_citations':case.get('actual_citations',[]),'source_documents':sources,'expected_tool_calls':expected_tools,'actual_tool_calls':actual_tools,'metrics':metrics,'score':score,'status':status,'failure_reasons':reasons}

def evaluate_cases(cases: list[dict[str, Any]], threshold: float=.65, actual_answers: dict[str,str]|None=None) -> dict[str, Any]:
    actual_answers=actual_answers or {}
    results=[]
    for original in cases:
        case=dict(original)
        if case.get('id') in actual_answers: case['actual_answer']=actual_answers[case['id']]
        # Deterministic offline demo response: reference answer is supplied as mock output.
        if case.get('actual_answer') is None: case['actual_answer']=case.get('expected_answer','')
        results.append(evaluate_case(case,threshold))
    scored=[r for r in results if r['score'] is not None]
    passed=sum(r['status']=='passed' for r in results); failed=sum(r['status']=='failed' for r in results); unscored=sum(r['status']=='unscored' for r in results)
    return {'results':results,'summary':{'total_cases':len(results),'scored_cases':len(scored),'passed_cases':passed,'failed_cases':failed,'unscored_cases':unscored,
      'pass_rate':round(passed/len(scored),4) if scored else None,'average_score':round(sum(r['score'] for r in scored)/len(scored),4) if scored else None,'pass_threshold':threshold}}
