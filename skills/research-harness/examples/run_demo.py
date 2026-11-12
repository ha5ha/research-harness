#!/usr/bin/env python3
"""Demonstrate a fictional research ledger in a fresh temporary local directory.

No scientific experiment runs. Outputs are SIMULATED for validating the CLI loop.
"""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
import tempfile

TOOL=Path(__file__).resolve().parents[1]/'scripts'/'rh.py'

def main():
    with tempfile.TemporaryDirectory(prefix='rh-demo-') as tmp:
        root=Path(tmp)
        def invoke(*cmd):
            proc=subprocess.run([sys.executable,str(TOOL),'--project-root',str(root),*cmd],
                                capture_output=True,text=True,check=False)
            result=json.loads(proc.stdout)
            if proc.returncode:
                raise RuntimeError(f'{cmd}: {result}')
            return result
        invoke('init','--title','SIMULATED algorithm robustness')
        parent=invoke('question','add','--title','Why is A unstable?')['id']
        child=invoke('question','add','--parent',parent,'--title','Does seed sensitivity matter?')['id']
        ex=invoke('experiment','create','--question',child,'--title','SIMULATED seed test')['id']
        exp_path=Path(invoke('show','--id',ex)['path'])
        data=json.loads((root/exp_path).read_text())
        data.update(research_question='Is the behavior seed-dependent?',method='synthetic toy comparison',
                    inputs=['synthetic-fixture'],outputs=['results/synthetic.csv'],stopping_rule='one toy batch',
                    metrics=['paired toy error'],statistical_unit='synthetic row',randomness='deterministic toy table',
                    data_access='fabricated demonstration data only',budget='no model or remote compute',
                    implementation_ref='bundled demo',environment_ref='Python standard library')
        (root/exp_path).write_text(json.dumps(data),encoding='utf-8')
        invoke('experiment','freeze','--experiment',ex)
        # Prepare only, NEVER runs a shell command.
        attempt=invoke('attempt','prepare','--experiment',ex,'--command','NOT EXECUTED: demo',
                       '--authorization-ref','DEMO-ONLY (not genuine permission)')['id']
        invoke('attempt','update','--attempt',attempt,'--status','failed',
               '--note','DEMO: no actual compute is performed')
        (root/'results').mkdir()
        (root/'results/synthetic.csv').write_text('seed,error_A,error_B\n1,3,4\n2,8,5\n',encoding='utf-8')
        evid=invoke('evidence','add','--question',child,'--file','results/synthetic.csv',
                    '--role','output','--snapshot')['id']
        fid=invoke('finding','add','--question',child,'--kind','observation',
                   '--statement','SIMULATED: direction reverses across the two toy seeds',
                   '--scope','synthetic demonstration only','--evidence',evid)['id']
        # A demo review-source string illustrates the workflow, not a real human sign-off.
        invoke('finding','review','--finding',fid,'--status','accepted',
               '--review-ref','DEMO-only fixture review')
        (root/'reports').mkdir()
        (root/'reports/child.md').write_text('# Synthetic child report\nOne toy seed improved; one reversed. No scientific claim.\n',encoding='utf-8')
        syn=invoke('synthesis','add','--question',child,'--file','reports/child.md','--findings',fid)['id']
        invoke('synthesis','review','--synthesis',syn,'--status','reviewed',
               '--review-ref','DEMO-only fixture review')
        invoke('question','update','--question',child,'--status','resolved')
        # Parent can cite its child's accepted finding.
        (root/'reports/parent.md').write_text('# Synthetic parent report\nThe toy evidence does not establish general robustness.\n',encoding='utf-8')
        ps=invoke('synthesis','add','--question',parent,'--file','reports/parent.md','--findings',fid)['id']
        invoke('synthesis','review','--synthesis',ps,'--status','reviewed',
               '--review-ref','DEMO-only fixture review')
        invoke('question','update','--question',parent,'--status','resolved')
        outcome=invoke('check')
        assert outcome['ok']
        print(json.dumps({'demo':'passed','question_id':parent,'child_question_id':child,
                          'experiment_id':ex,'attempt_id':attempt,'evidence_id':evid,
                          'finding_id':fid,'child_synthesis_id':syn,'parent_synthesis_id':ps,
                          'check':outcome,'note':'All data and reviews were synthetic; no experiment ran'},
                         ensure_ascii=False,indent=2))

if __name__=='__main__':main()
