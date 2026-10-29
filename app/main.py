from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from contextlib import asynccontextmanager
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import csv, io, json
from app.core.config import DATABASE_PATH, BASE_DIR
from app.db.database import init_db, db_session
from app.schemas.evaluation import DatasetImport, EvaluationRequest, TraceIngest
from app.services.evaluator import evaluate_cases

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app=FastAPI(title='AgentProof AI',version='1.0.0',description='Repeatable lexical evaluation and regression testing for GenAI applications. Metrics are proxies, not proof of factual correctness.',lifespan=lifespan)
WEB_DIR=BASE_DIR/'web'
app.mount('/static',StaticFiles(directory=str(WEB_DIR)),name='static')

@app.get('/',response_class=HTMLResponse)
def dashboard(): return (WEB_DIR/'index.html').read_text(encoding='utf-8')
@app.get('/health')
def health():
    with db_session() as c: c.execute('SELECT 1').fetchone()
    return {'status':'ok','service':'agentproof-ai','database':'connected'}

@app.get('/api/datasets')
def list_datasets():
    with db_session() as c: rows=c.execute('SELECT id,name,description,created_at,cases_json FROM datasets ORDER BY id DESC').fetchall()
    return [{'id':r['id'],'name':r['name'],'description':r['description'],'created_at':r['created_at'],'case_count':len(json.loads(r['cases_json']))} for r in rows]

@app.post('/api/datasets/import',status_code=201)
def import_dataset(payload: DatasetImport):
    ids=[x.id for x in payload.cases]
    if len(ids)!=len(set(ids)): raise HTTPException(422,'Dataset case IDs must be unique.')
    with db_session() as c:
        cur=c.execute('INSERT INTO datasets(name,description,cases_json) VALUES(?,?,?)',(payload.name,payload.description,json.dumps([x.model_dump() for x in payload.cases])))
        did=cur.lastrowid
    return {'id':did,'name':payload.name,'case_count':len(payload.cases)}

@app.post('/api/datasets/import-file',status_code=201)
async def import_dataset_file(file: UploadFile=File(...), name: str|None=None):
    if not file.filename or Path(file.filename).suffix.lower() not in ('.json','.csv'):
        raise HTTPException(415,'Upload a .json or .csv dataset file.')
    raw=await file.read()
    if len(raw)>2_000_000: raise HTTPException(413,'Dataset file must be smaller than 2 MB.')
    try:
        if file.filename.lower().endswith('.json'):
            parsed=json.loads(raw)
            if isinstance(parsed,list): parsed={'name':name or Path(file.filename).stem,'cases':parsed}
        else:
            rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
            for row in rows:
                for key in ('expected_keywords','expected_citations'):
                    value=row.get(key,'')
                    try: row[key]=json.loads(value) if value.strip().startswith('[') else [x.strip() for x in value.split(';') if x.strip()]
                    except json.JSONDecodeError: raise ValueError(f'CSV field {key} must be a semicolon list or JSON array.')
            parsed={'name':name or Path(file.filename).stem,'cases':rows}
        parsed.setdefault('name',name or Path(file.filename).stem); parsed.setdefault('description','Imported dataset')
        payload=DatasetImport.model_validate(parsed)
    except Exception as e: raise HTTPException(422,f'Invalid dataset file: {e}')
    return import_dataset(payload)

@app.get('/api/datasets/{dataset_id}')
def get_dataset(dataset_id:int):
    with db_session() as c: r=c.execute('SELECT * FROM datasets WHERE id=?',(dataset_id,)).fetchone()
    if not r: raise HTTPException(404,'Dataset not found.')
    return {'id':r['id'],'name':r['name'],'description':r['description'],'created_at':r['created_at'],'cases':json.loads(r['cases_json'])}

@app.post('/api/traces', status_code=201)
def ingest_trace(payload: TraceIngest):
    """Ingest an agent execution trace with ordered spans for later debugging."""
    ids=[span.span_id for span in payload.spans]
    if len(ids) != len(set(ids)):
        raise HTTPException(422, 'Span IDs must be unique within a trace.')
    known=set(ids)
    for span in payload.spans:
        if span.parent_span_id and span.parent_span_id not in known:
            raise HTTPException(422, f'Parent span {span.parent_span_id!r} is not present in this trace.')
    durations=[]
    span_times=[]
    from datetime import datetime
    for span in payload.spans:
        if span.started_at and span.ended_at:
            try:
                start=datetime.fromisoformat(span.started_at.replace('Z','+00:00'))
                end=datetime.fromisoformat(span.ended_at.replace('Z','+00:00'))
                if start.tzinfo is None or end.tzinfo is None: raise ValueError('timestamps must include a timezone')
                delta=(end-start).total_seconds()*1000
                if delta < 0: raise ValueError('negative duration')
                durations.append(delta); span_times.extend([start,end])
            except ValueError:
                raise HTTPException(422, f'Invalid timestamps or negative duration for span {span.span_id}.')
    # Wall-clock trace duration avoids double-counting nested child spans.
    duration=(max(span_times)-min(span_times)).total_seconds()*1000 if span_times else None
    status='error' if any(s.status=='error' for s in payload.spans) else 'ok'
    try:
        with db_session() as c:
            cur=c.execute('INSERT INTO traces(trace_id,name,session_id,metadata_json,spans_json,status,duration_ms) VALUES(?,?,?,?,?,?,?)',
                (payload.trace_id,payload.name,payload.session_id,json.dumps(payload.metadata),json.dumps([s.model_dump() for s in payload.spans]),status,duration))
            trace_pk=cur.lastrowid
    except Exception as exc:
        if 'UNIQUE constraint failed' in str(exc): raise HTTPException(409, 'A trace with this trace_id already exists.')
        raise
    return {'id':trace_pk,'trace_id':payload.trace_id,'name':payload.name,'span_count':len(payload.spans),'status':status,'duration_ms':duration}

@app.get('/api/traces')
def list_traces(limit:int=Query(50,ge=1,le=200), status:str|None=Query(None,pattern='^(ok|error)$')):
    sql='SELECT id,trace_id,name,session_id,status,duration_ms,created_at,spans_json FROM traces'
    params=[]
    if status:
        sql+=' WHERE status=?'; params.append(status)
    sql+=' ORDER BY id DESC LIMIT ?'; params.append(limit)
    with db_session() as c: rows=c.execute(sql,params).fetchall()
    return [{'id':r['id'],'trace_id':r['trace_id'],'name':r['name'],'session_id':r['session_id'],'status':r['status'],'duration_ms':r['duration_ms'],'created_at':r['created_at'],'span_count':len(json.loads(r['spans_json']))} for r in rows]

@app.get('/api/traces/{trace_id}')
def get_trace(trace_id:str):
    with db_session() as c: r=c.execute('SELECT * FROM traces WHERE trace_id=?',(trace_id,)).fetchone()
    if not r: raise HTTPException(404,'Trace not found.')
    return {'id':r['id'],'trace_id':r['trace_id'],'name':r['name'],'session_id':r['session_id'],'metadata':json.loads(r['metadata_json']),'status':r['status'],'duration_ms':r['duration_ms'],'created_at':r['created_at'],'spans':json.loads(r['spans_json'])}

@app.post('/api/evaluations',status_code=201)
def create_evaluation(req:EvaluationRequest):
    if req.cases is not None: cases=[x.model_dump() for x in req.cases]; name=req.dataset_name or 'Ad hoc dataset'; did=None
    elif req.dataset_id is not None:
        with db_session() as c: ds=c.execute('SELECT * FROM datasets WHERE id=?',(req.dataset_id,)).fetchone()
        if not ds: raise HTTPException(404,'Dataset not found.')
        cases=json.loads(ds['cases_json']); name=req.dataset_name or ds['name']; did=ds['id']
    else: raise HTTPException(422,'Provide dataset_id or cases.')
    if not cases: raise HTTPException(422,'Evaluation requires at least one case.')
    output=evaluate_cases(cases,req.pass_threshold,req.actual_answers)
    with db_session() as c:
        cur=c.execute('INSERT INTO runs(dataset_id,dataset_name,config_json,results_json,summary_json) VALUES(?,?,?,?,?)',(did,name,json.dumps({'pass_threshold':req.pass_threshold}),json.dumps(output['results']),json.dumps(output['summary'])))
        rid=cur.lastrowid
    return {'id':rid,'dataset_id':did,'dataset_name':name,'created_at':None,'config':{'pass_threshold':req.pass_threshold},**output}

@app.get('/api/evaluations')
def list_evaluations(limit:int=Query(20,ge=1,le=100)):
    with db_session() as c: rows=c.execute('SELECT id,dataset_name,created_at,summary_json,config_json FROM runs ORDER BY id DESC LIMIT ?',(limit,)).fetchall()
    return [{'id':r['id'],'dataset_name':r['dataset_name'],'created_at':r['created_at'],'summary':json.loads(r['summary_json']),'config':json.loads(r['config_json'])} for r in rows]

@app.get('/api/evaluations/compare')
def compare_evaluations(baseline_id:int,candidate_id:int):
    with db_session() as c:
        a=c.execute('SELECT * FROM runs WHERE id=?',(baseline_id,)).fetchone(); b=c.execute('SELECT * FROM runs WHERE id=?',(candidate_id,)).fetchone()
    if not a or not b: raise HTTPException(404,'Baseline or candidate evaluation run not found.')
    ar={x['case_id']:x for x in json.loads(a['results_json'])}; br={x['case_id']:x for x in json.loads(b['results_json'])}
    newly_failing=sorted(k for k in ar.keys()&br.keys() if ar[k]['status']=='passed' and br[k]['status']=='failed')
    newly_passing=sorted(k for k in ar.keys()&br.keys() if ar[k]['status']=='failed' and br[k]['status']=='passed')
    changes=[{'case_id':k,'baseline_score':ar[k]['score'],'candidate_score':br[k]['score'],'delta':round(br[k]['score']-ar[k]['score'],4) if ar[k]['score'] is not None and br[k]['score'] is not None else None,'baseline_status':ar[k]['status'],'candidate_status':br[k]['status']} for k in sorted(ar.keys()&br.keys())]
    sa=json.loads(a['summary_json']); sb=json.loads(b['summary_json'])
    return {'baseline_id':baseline_id,'candidate_id':candidate_id,'score_delta':round(sb['average_score']-sa['average_score'],4) if sa['average_score'] is not None and sb['average_score'] is not None else None,'pass_rate_delta':round(sb['pass_rate']-sa['pass_rate'],4) if sa['pass_rate'] is not None and sb['pass_rate'] is not None else None,'newly_failing':newly_failing,'newly_passing':newly_passing,'common_case_score_changes':changes}

@app.get('/api/evaluations/{run_id}/export')
def export_evaluation(run_id:int,format:str=Query('json',pattern='^(json|csv)$')):
    with db_session() as c: r=c.execute('SELECT * FROM runs WHERE id=?',(run_id,)).fetchone()
    if not r: raise HTTPException(404,'Evaluation run not found.')
    results=json.loads(r['results_json']); summary=json.loads(r['summary_json'])
    if format=='json': return JSONResponse({'id':r['id'],'dataset_name':r['dataset_name'],'created_at':r['created_at'],'summary':summary,'results':results},headers={'Content-Disposition':f'attachment; filename=agentproof-run-{run_id}.json'})
    out=io.StringIO(); fields=['case_id','status','score','question','expected_answer','actual_answer','failure_reasons','metrics']; writer=csv.DictWriter(out,fieldnames=fields); writer.writeheader()
    for item in results:
        row={k:item.get(k) for k in fields}; row['failure_reasons']=' | '.join(item.get('failure_reasons',[])); row['metrics']=json.dumps(item.get('metrics',{})); writer.writerow(row)
    return Response(out.getvalue(),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename=agentproof-run-{run_id}.csv'})

@app.get('/api/evaluations/{run_id}')
def get_evaluation(run_id:int):
    with db_session() as c: r=c.execute('SELECT * FROM runs WHERE id=?',(run_id,)).fetchone()
    if not r: raise HTTPException(404,'Evaluation run not found.')
    return {'id':r['id'],'dataset_id':r['dataset_id'],'dataset_name':r['dataset_name'],'created_at':r['created_at'],'config':json.loads(r['config_json']),'summary':json.loads(r['summary_json']),'results':json.loads(r['results_json'])}
