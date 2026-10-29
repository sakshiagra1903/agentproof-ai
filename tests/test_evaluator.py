from app.services.evaluator import keyword_coverage,lexical_similarity,context_overlap,evaluate_case,evaluate_cases

def base(**kw):
 d={'id':'t1','question':'q','expected_answer':'Refund within 30 days','reference_context':'Refund within 30 days of purchase','expected_keywords':['refund','30 days'],'expected_citations':['policy.md'],'actual_answer':'Refund within 30 days','actual_citations':['policy.md']};d.update(kw);return d

def test_keyword_coverage(): assert keyword_coverage('Refund in 30 days',['refund','30 days'])==1

def test_keyword_coverage_not_applicable(): assert keyword_coverage('hello',[]) is None

def test_lexical_similarity(): assert lexical_similarity('a b','a b')==1

def test_lexical_empty(): assert lexical_similarity('','ref') is None

def test_context_overlap(): assert context_overlap('refund within 30 days','refund within 30 days purchase')==1

def test_context_overlap_empty(): assert context_overlap('answer','') is None

def test_pass_and_citation_presence(): assert evaluate_case(base())['status']=='passed';assert evaluate_case(base())['metrics']['citation_presence']==1

def test_failing_answer_reasons():
 r=evaluate_case(base(actual_answer='Completely unrelated words',actual_citations=[]));assert r['status']=='failed';assert r['failure_reasons']

def test_empty_answer_is_unscored():
 r=evaluate_case(base(actual_answer=''));assert r['status']=='unscored';assert r['score'] is None

def test_missing_context_does_not_claim_grounding():
 r=evaluate_case(base(reference_context=''));assert r['metrics']['context_word_overlap'] is None;assert any('missing' in x for x in r['failure_reasons'])

def test_threshold_boundary():
 c=base(expected_answer='same words',actual_answer='same words',reference_context='same words',expected_keywords=[])
 assert evaluate_case(c,1.0)['status']=='passed'
 assert evaluate_case(c,1.01)['status']=='failed'

def test_all_unscored_summary_has_no_pass_rate():
 r=evaluate_cases([base(actual_answer='')]);assert r['summary']['pass_rate'] is None

def test_citation_source_validation():
 c=base(source_documents=[{'id':'policy.md','text':'Refund policy'}],actual_citations=['invented.md'])
 r=evaluate_case(c); assert r['metrics']['citation_source_validity']==0.0
 assert any('source documents' in x for x in r['failure_reasons'])

def test_tool_call_match_metric():
 c=base(expected_tool_calls=['calendar.check','booking.create'],actual_tool_calls=['calendar.check'])
 r=evaluate_case(c); assert r['metrics']['tool_call_match']==0.5 and r['status']=='failed'
