import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.schemas.evaluation import DatasetImport
from app.services.evaluator import evaluate_cases

def main():
 p=argparse.ArgumentParser(description='Run AgentProof deterministic dataset evaluation and enforce a pass-rate gate.')
 p.add_argument('--dataset',required=True,help='Path to JSON dataset: {name, cases} or a case array')
 p.add_argument('--min-pass-rate',type=float,default=.80,help='Minimum scored-case pass rate, from 0 to 1')
 p.add_argument('--pass-threshold',type=float,default=.65,help='Per-case metric threshold, from 0 to 1')
 p.add_argument('--report',help='Optional JSON output report path')
 a=p.parse_args()
 if not 0<=a.min_pass_rate<=1 or not 0<=a.pass_threshold<=1: print('Thresholds must be between 0 and 1.',file=sys.stderr);return 2
 try:
  data=json.loads(Path(a.dataset).read_text(encoding='utf-8'))
  if isinstance(data,list): data={'name':Path(a.dataset).stem,'cases':data}
  ds=DatasetImport.model_validate({**data,'name':data.get('name',Path(a.dataset).stem),'description':data.get('description','')})
  ids=[c.id for c in ds.cases]
  if len(ids)!=len(set(ids)): raise ValueError('Case IDs must be unique.')
 except Exception as e: print(f'Invalid dataset: {e}',file=sys.stderr);return 2
 result=evaluate_cases([c.model_dump() for c in ds.cases],a.pass_threshold)
 s=result['summary']
 print(f"Dataset: {ds.name}\nCases: {s['total_cases']} | Scored: {s['scored_cases']} | Passed: {s['passed_cases']} | Failed: {s['failed_cases']} | Unscored: {s['unscored_cases']}\nAverage score: {s['average_score']} | Pass rate: {s['pass_rate']} | Required: {a.min_pass_rate:.2f}")
 if a.report:
  out={'dataset_name':ds.name,'summary':s,'results':result['results']};Path(a.report).parent.mkdir(parents=True,exist_ok=True);Path(a.report).write_text(json.dumps(out,indent=2),encoding='utf-8');print(f'Report written: {a.report}')
 if s['pass_rate'] is None or s['pass_rate']<a.min_pass_rate: print('CI GATE FAILED',file=sys.stderr);return 1
 print('CI GATE PASSED');return 0
if __name__=='__main__':sys.exit(main())
