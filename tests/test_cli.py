import json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run(*args): return subprocess.run([sys.executable,str(ROOT/'scripts/evaluate_dataset.py'),*map(str,args)],cwd=ROOT,capture_output=True,text=True)
def test_cli_pass_and_report(tmp_path):
 report=tmp_path/'report.json';r=run('--dataset',ROOT/'data/demo_cases.json','--min-pass-rate','0.80','--report',report);assert r.returncode==0,r.stderr;assert report.exists()
def test_cli_fails_threshold():
 r=run('--dataset',ROOT/'data/demo_cases.json','--min-pass-rate','1.0');assert r.returncode==1

def test_cli_invalid_file(tmp_path):
 f=tmp_path/'bad.json';f.write_text('{broken');r=run('--dataset',f);assert r.returncode==2

def test_cli_invalid_threshold(): assert run('--dataset',ROOT/'data/demo_cases.json','--min-pass-rate','2').returncode==2
