import json

def test_health(client): assert client.get('/health').json()['status']=='ok'
def test_builtin_dataset(client):
 r=client.get('/api/datasets');assert r.status_code==200 and r.json()[0]['case_count']>=15

def test_missing_dataset_404(client): assert client.get('/api/datasets/9999').status_code==404

def test_invalid_dataset_schema(client): assert client.post('/api/datasets/import',json={'name':'bad','cases':[{'id':'x'}]}).status_code==422

def test_duplicate_case_ids(client):
 c={'id':'x','question':'q','expected_answer':'a'}
 r=client.post('/api/datasets/import',json={'name':'dupe','cases':[c,c]});assert r.status_code==422

def test_run_persists_and_retrieves(client):
 did=client.get('/api/datasets').json()[0]['id'];r=client.post('/api/evaluations',json={'dataset_id':did});assert r.status_code==201
 rid=r.json()['id'];assert client.get(f'/api/evaluations/{rid}').json()['summary']['total_cases']>=15
 assert any(x['id']==rid for x in client.get('/api/evaluations').json())

def test_missing_run_404(client): assert client.get('/api/evaluations/9999').status_code==404

def test_compare_runs(client):
 did=client.get('/api/datasets').json()[0]['id'];a=client.post('/api/evaluations',json={'dataset_id':did}).json();b=client.post('/api/evaluations',json={'dataset_id':did,'pass_threshold':.8}).json()
 r=client.get('/api/evaluations/compare',params={'baseline_id':a['id'],'candidate_id':b['id']});assert r.status_code==200 and 'newly_failing' in r.json()

def test_compare_missing_run_404(client): assert client.get('/api/evaluations/compare?baseline_id=1&candidate_id=999').status_code==404

def test_json_csv_exports(client):
 did=client.get('/api/datasets').json()[0]['id'];rid=client.post('/api/evaluations',json={'dataset_id':did}).json()['id']
 assert client.get(f'/api/evaluations/{rid}/export?format=json').status_code==200
 csv=client.get(f'/api/evaluations/{rid}/export?format=csv');assert csv.status_code==200 and 'case_id,status,score' in csv.text

def test_bad_upload_extension(client): assert client.post('/api/datasets/import-file',files={'file':('bad.exe',b'x')}).status_code==415

def test_trace_ingest_and_detail(client):
 payload={'trace_id':'trace-test-1','name':'support-agent','spans':[{'span_id':'s1','name':'retrieve','kind':'retrieval','status':'ok','started_at':'2026-01-01T00:00:00Z','ended_at':'2026-01-01T00:00:00.010Z'},{'span_id':'s2','parent_span_id':'s1','name':'answer','kind':'llm','status':'error','error':'mock timeout'}]}
 r=client.post('/api/traces',json=payload); assert r.status_code==201 and r.json()['status']=='error' and r.json()['span_count']==2
 detail=client.get('/api/traces/trace-test-1'); assert detail.status_code==200 and len(detail.json()['spans'])==2
 assert client.get('/api/traces?status=error').json()[0]['trace_id']=='trace-test-1'

def test_trace_duplicate_and_invalid_parent(client):
 p={'trace_id':'dup','spans':[{'span_id':'s1','name':'x'},{'span_id':'s1','name':'y'}]}
 assert client.post('/api/traces',json=p).status_code==422
 p={'trace_id':'bad-parent','spans':[{'span_id':'s1','parent_span_id':'missing','name':'x'}]}
 assert client.post('/api/traces',json=p).status_code==422

def test_trace_missing_404(client): assert client.get('/api/traces/no-such-trace').status_code==404
