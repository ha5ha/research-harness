"""Real CLI tests against isolated local projects. No network or experiment execution."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import tempfile
import unittest
import io
import contextlib
import importlib.util
import os

SCRIPT=Path(os.environ.get('RH_TEST_SCRIPT',Path(__file__).resolve().parents[1]/'scripts'/'rh.py'))
SPEC=importlib.util.spec_from_file_location('research_harness_cli',SCRIPT)
rh=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rh)

class HarnessCLITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='rh-v2-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.run_cli('init','--title','Test research')

    def call_cli(self,*args):
        buffer=io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code=rh.main(['--project-root',str(self.root),*args])
        try: obj=json.loads(buffer.getvalue())
        except json.JSONDecodeError:
            raise AssertionError(f'Invalid CLI JSON output: {buffer.getvalue()!r}')
        return code,obj

    def run_cli(self,*args):
        code,obj=self.call_cli(*args)
        self.assertEqual(code,0,f'{args}: {obj}')
        self.assertTrue(obj['ok'])
        return obj

    def fail_cli(self,*args):
        code,obj=self.call_cli(*args)
        self.assertNotEqual(code,0,f'expected rejection for {args}')
        self.assertFalse(obj['ok'])
        return obj

    def question(self,title='Q',parent=None):
        args=['question','add','--title',title]
        if parent:args+=['--parent',parent]
        return self.run_cli(*args)['id']

    def doc(self, path, data):
        f=self.root/path
        f.parent.mkdir(parents=True,exist_ok=True)
        f.write_text(data if isinstance(data,str) else json.dumps(data,ensure_ascii=False),encoding='utf-8')
        return f

    def contract(self,qid,mode='exploratory'):
        c=self.run_cli('experiment','create','--question',qid,'--title','Repeat study','--mode',mode)
        f=self.root/c['contract']
        d=json.loads(f.read_text())
        d.update(research_question='Does A beat B?',method='matched comparison',
                 inputs=['data/train.csv'],outputs=['results/metrics.csv'],stopping_rule='one batch',
                 metrics=['paired error'],statistical_unit='sample',randomness='fixed seed 1',
                 data_access='synthetic fixture only',budget='no compute; local record test',
                 implementation_ref='fixture-code-v1',environment_ref='Python standard library')
        if mode=='confirmatory':
            d.update(hypotheses=['H1'],falsifying_outcomes=['no improvement'],controls=['B'],
                metrics=['error'],statistical_unit='sample',selection_rule='frozen',
                missingness_rule='report all missing',decision_rule='effect+interval',
                randomness='fixed seed',data_access='train-only',budget='1 GPU hour',
                implementation_ref='code-commit',environment_ref='environment-lock')
        f.write_text(json.dumps(d),encoding='utf-8')
        return c['id'],f

    def reviewed_finding(self,qid, evidence_id):
        fid=self.run_cli('finding','add','--question',qid,'--kind','scoped_claim',
            '--statement','Observed gain on held-out sample','--scope','small fixture',
            '--evidence',evidence_id)['id']
        self.run_cli('finding','review','--finding',fid,'--status','accepted','--review-ref','human-review-note-1')
        return fid

    def test_init_valid_structure_and_no_clobber(self):
        self.assertTrue((self.root/'research/PROJECT.json').is_file())
        self.assertEqual(self.run_cli('check')['counts']['questions'],0)
        self.assertFalse((self.root/'research/FOCUS.json').read_text().find('question_id')<0)
        self.fail_cli('init','--title','overwrite')

    def test_nested_questions_are_registered_and_recoverable(self):
        root=self.question('What causes a failure?')
        sub=self.question('Is seed sensitivity responsible?',root)
        subsub=self.question('Does data order explain it?',sub)
        self.run_cli('focus','--question',subsub,'--next-action','Inspect partial traces')
        self.assertEqual(self.run_cli('status')['questions'][0]['id'], subsub)
        tree=self.run_cli('status','--question',root)['questions']
        self.assertEqual(tree[0]['id'],root)
        self.assertEqual(tree[0]['children'][0]['id'],sub)
        self.assertEqual(tree[0]['children'][0]['children'][0]['id'],subsub)
        self.assertEqual(self.run_cli('show','--id',subsub)['record']['parent_id'],sub)
        self.assertTrue(self.run_cli('check')['ok'])

    def test_freeze_and_change_detection(self):
        q=self.question()
        xid,f=self.contract(q)
        self.fail_cli('attempt','prepare','--experiment',xid,'--command','none','--authorization-ref','current')
        frozen=self.run_cli('experiment','freeze','--experiment',xid)
        self.assertRegex(frozen['snapshot_sha256'],r'^[0-9a-f]{64}$')
        self.fail_cli('experiment','freeze','--experiment',xid)
        d=json.loads(f.read_text());d['method']='post-hoc update';f.write_text(json.dumps(d))
        self.fail_cli('attempt','prepare','--experiment',xid,'--command','none','--authorization-ref','current')
        self.assertFalse(self.call_cli('check')[1]['ok'])

    def test_confirmatory_freeze_requires_more_fields(self):
        q=self.question()
        c=self.run_cli('experiment','create','--question',q,'--title','confirmation','--mode','confirmatory')
        self.assertIn('incomplete',str(self.fail_cli('experiment','freeze','--experiment',c['id'])))
        xid,_=self.contract(q,'confirmatory')
        self.run_cli('experiment','freeze','--experiment',xid)
        self.assertTrue(self.run_cli('check')['ok'])

    def test_attempts_are_independent_and_receipted(self):
        q=self.question();xid,_=self.contract(q)
        self.run_cli('experiment','freeze','--experiment',xid)
        a1=self.run_cli('attempt','prepare','--experiment',xid,'--command','run v1','--authorization-ref','permission-1')['id']
        a2=self.run_cli('attempt','prepare','--experiment',xid,'--command','run v1','--authorization-ref','permission-1')['id']
        self.assertNotEqual(a1,a2)
        self.fail_cli('attempt','update','--attempt',a1,'--status','completed')
        self.run_cli('attempt','update','--attempt',a1,'--status','submitted','--receipt-ref','scheduler/001')
        self.run_cli('attempt','update','--attempt',a1,'--status','submission_unknown','--note','Connection lost')
        self.run_cli('attempt','update','--attempt',a1,'--status','completed','--receipt-ref','scheduler/001')
        self.fail_cli('attempt','update','--attempt',a1,'--status','running','--receipt-ref','outdated')
        self.run_cli('attempt','update','--attempt',a2,'--status','failed','--note','Run was not launched')
        self.assertTrue(self.run_cli('check')['ok'])

    def test_evidence_snapshot_and_tamper_detection(self):
        q=self.question()
        f=self.doc('results/data.csv','sample,error\na,2\n')
        eid=self.run_cli('evidence','add','--question',q,'--file','results/data.csv','--snapshot')['id']
        self.assertTrue(self.run_cli('check')['ok'])
        obj=self.run_cli('show','--id',eid)['record']
        self.assertTrue((self.root/obj['archived_path']).exists())
        f.write_text('sample,error\na,999\n')
        errs=self.call_cli('check')[1]['errors']
        self.assertTrue(any('source_path hash/size mismatch' in x for x in errs),errs)

    def test_reviewed_child_and_parent_synthesis_close_tree(self):
        parent=self.question('Root question');child=self.question('Child',parent)
        self.doc('results/child.csv','id,metric\na,4\n')
        e=self.run_cli('evidence','add','--question',child,'--file','results/child.csv','--snapshot')['id']
        fid=self.reviewed_finding(child,e)
        self.doc('reports/child.md','# Child conclusion\nEvidence E. Limitations: small data.\n')
        child_s=self.run_cli('synthesis','add','--question',child,'--file','reports/child.md','--findings',fid)['id']
        self.run_cli('synthesis','review','--synthesis',child_s,'--status','reviewed','--review-ref','child-review')
        self.run_cli('question','update','--question',child,'--status','resolved')
        parent_fid=self.reviewed_finding(parent,e)
        self.doc('reports/parent.md','# Parent conclusion\nEvidence supports scoped statement.\n')
        parent_s=self.run_cli('synthesis','add','--question',parent,'--file','reports/parent.md','--findings',parent_fid, fid)['id']
        r=self.run_cli('synthesis','review','--synthesis',parent_s,'--status','reviewed','--review-ref','parent-review')
        self.assertEqual(r['coverage'],'complete')
        self.run_cli('question','update','--question',parent,'--status','resolved')
        self.assertTrue(self.run_cli('check')['ok'])
        self.fail_cli('question','add','--title','New child under closed parent','--parent',parent)

    def test_incomplete_child_prevents_parent_resolution(self):
        parent=self.question('Root');child=self.question('Still unresolved',parent)
        self.doc('data/obs.txt','observed metric 5')
        e=self.run_cli('evidence','add','--question',parent,'--file','data/obs.txt')['id']
        f=self.reviewed_finding(parent,e)
        self.doc('report.md','# Parent interim report\nIncomplete: child remains open\n')
        sid=self.run_cli('synthesis','add','--question',parent,'--file','report.md','--findings',f,'--limitations','Child is open')['id']
        self.fail_cli('synthesis','review','--synthesis',sid,'--status','reviewed','--review-ref','review-1')
        reviewed=self.run_cli('synthesis','review','--synthesis',sid,'--status','reviewed','--review-ref','review-1','--allow-partial')
        self.assertEqual(reviewed['coverage'],'partial')
        self.fail_cli('question','update','--question',parent,'--status','resolved')
        self.assertTrue(self.run_cli('check')['ok'])

    def test_cross_branch_findings_are_rejected(self):
        a=self.question('A');b=self.question('B')
        self.doc('data/e.txt','observation')
        e=self.run_cli('evidence','add','--question',a,'--file','data/e.txt')['id']
        self.fail_cli('finding','add','--question',b,'--kind','observation','--statement','wrong use','--evidence',e)
        f=self.reviewed_finding(a,e)
        self.doc('report.md','# Report')
        self.fail_cli('synthesis','add','--question',b,'--file','report.md','--findings',f)

    def test_hypothesis_cannot_be_accepted(self):
        q=self.question()
        f=self.run_cli('finding','add','--question',q,'--kind','hypothesis','--statement','Maybe a mechanism')['id']
        self.fail_cli('finding','review','--finding',f,'--status','accepted','--review-ref','human')
        self.assertTrue(self.run_cli('check')['ok'])

    def test_sensitive_paths_and_escape_are_rejected(self):
        q=self.question()
        self.doc('.env','SECRET=a')
        self.doc('safe.txt','safe')
        self.fail_cli('evidence','add','--question',q,'--file','.env')
        self.fail_cli('evidence','add','--question',q,'--file','../outside.txt')
        self.fail_cli('evidence','add','--question',q,'--file','/etc/hosts')

    def test_symlink_escape_is_rejected(self):
        q=self.question()
        with tempfile.TemporaryDirectory(prefix='rh-external-') as other:
            external=Path(other)/'evidence.txt';external.write_text('outside',encoding='utf-8')
            try:(self.root/'outside-link.txt').symlink_to(external)
            except (OSError,NotImplementedError) as error:self.skipTest('symlink unavailable: '+str(error))
            self.fail_cli('evidence','add','--question',q,'--file','outside-link.txt')

    def report(self,qid,fids,name='report.md'):
        self.doc(name,'# Scoped fixture report\nSynthetic evidence only; no scientific conclusion.\n')
        sid=self.run_cli('synthesis','add','--question',qid,'--file',name,'--findings',*fids)['id']
        self.run_cli('synthesis','review','--synthesis',sid,'--status','reviewed','--review-ref','fixture review')
        return sid

    def fixture_evidence(self,qid):
        self.doc('data/metric.csv','sample,source,method\na,2,1\nb,3,5\n')
        return self.run_cli('evidence','add','--question',qid,'--file','data/metric.csv')['id']

    def correction(self,qid,eid,old,status='accepted'):
        f=self.run_cli('finding','add','--question',qid,'--kind','scoped_claim','--statement',
                       'Corrected: benefit is not consistent','--scope','fixture only','--evidence',eid,'--supersedes',old)['id']
        if status:self.run_cli('finding','review','--finding',f,'--status',status,'--review-ref','fixture correction review')
        return f

    def test_correction_invalidates_leaf_and_parent_without_deleting_history(self):
        parent=self.question('Parent');child=self.question('Child',parent)
        e=self.fixture_evidence(child);f1=self.reviewed_finding(child,e)
        sc=self.report(child,[f1],'child.md')
        self.run_cli('question','update','--question',child,'--status','resolved')
        sp=self.report(parent,[f1],'parent.md')
        self.run_cli('question','update','--question',parent,'--status','resolved')
        old_report=self.run_cli('show','--id',sp)['record']
        f2=self.correction(child,e,f1)
        checked=self.run_cli('check')
        self.assertEqual(set(checked['needs_review_question_ids']),{parent,child})
        status=self.run_cli('status','--question',parent)
        self.assertEqual(status['questions'][0]['status'],'needs_review')
        self.assertEqual(status['questions'][0]['recorded_status'],'resolved')
        self.assertEqual(self.run_cli('show','--id',sp)['record'],old_report)
        self.assertFalse(self.run_cli('show','--id',sc)['interpretation']['current'])
        self.assertEqual(self.run_cli('show','--id',f1)['interpretation']['superseded_by'],[f2])
        self.fail_cli('question','update','--question',parent,'--status','resolved')
        self.fail_cli('question','update','--question',child,'--status','resolved')
        bad=self.run_cli('synthesis','add','--question',child,'--file','child.md','--findings',f1)['id']
        self.fail_cli('synthesis','review','--synthesis',bad,'--status','reviewed','--review-ref','fixture')
        self.report(child,[f2],'child-corrected.md')
        self.run_cli('question','update','--question',child,'--status','resolved')
        self.report(parent,[f2],'parent-corrected.md')
        self.run_cli('question','update','--question',parent,'--status','resolved')
        self.assertEqual(self.run_cli('check')['needs_review_question_ids'],[])

    def test_proposed_and_rejected_corrections_do_not_replace_accepted_finding(self):
        q=self.question();e=self.fixture_evidence(q);f1=self.reviewed_finding(q,e)
        self.correction(q,e,f1,None)
        self.correction(q,e,f1,'rejected')
        self.assertTrue(self.run_cli('show','--id',f1)['interpretation']['current'])
        self.report(q,[f1]);self.run_cli('question','update','--question',q,'--status','resolved')

    def test_correction_chain_keeps_old_findings_historical(self):
        q=self.question();e=self.fixture_evidence(q);f1=self.reviewed_finding(q,e)
        f2=self.correction(q,e,f1);f3=self.correction(q,e,f2)
        self.assertFalse(self.run_cli('show','--id',f1)['interpretation']['current'])
        self.assertFalse(self.run_cli('show','--id',f2)['interpretation']['current'])
        self.assertTrue(self.run_cli('show','--id',f3)['interpretation']['current'])

    def test_focus_has_one_authoritative_next_action(self):
        q=self.question()
        self.run_cli('focus','--question',q,'--next-action','Review the correction')
        self.run_cli('question','update','--question',q,'--next-action','Audit the matched observations')
        status=self.run_cli('status')
        self.assertEqual(status['focus']['next_action'],status['questions'][0]['next_action'])
        self.assertNotIn('next_action',json.loads((self.root/'research/FOCUS.json').read_text()))
        self.assertTrue(self.run_cli('check')['ok'])

    def test_legacy_focus_conflict_is_detected_and_explicitly_repaired(self):
        q=self.question();self.run_cli('focus','--question',q,'--next-action','Current action')
        self.doc('research/FOCUS.json',{'question_id':q,'next_action':'Old action','updated_at':'fixture'})
        error=self.fail_cli('check')
        self.assertIn('conflicts',str(error))
        self.run_cli('focus','--question',q)
        self.assertTrue(self.run_cli('check')['ok'])
        self.assertEqual(self.run_cli('status')['focus']['next_action'],'Current action')

    def test_exploration_also_requires_budget_and_reproducibility(self):
        q=self.question();x,path=self.contract(q)
        data=json.loads(path.read_text());data['budget']='';path.write_text(json.dumps(data))
        self.assertIn('budget',str(self.fail_cli('experiment','freeze','--experiment',x)))
        data['budget']='local synthetic data only';data['inputs']=[None];path.write_text(json.dumps(data))
        self.fail_cli('experiment','freeze','--experiment',x)

    def test_protocol_inspection_does_not_mutate_native_records(self):
        with tempfile.TemporaryDirectory(prefix='rh-native-') as native:
            p=Path(native);(p/'research').mkdir()
            original=b'active_task: native\nnext_action: inspect_results\n'
            f=p/'research/CURRENT_STATE.yaml';f.write_bytes(original)
            buffer=io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code=rh.main(['--project-root',str(p),'inspect'])
            result=json.loads(buffer.getvalue())
            self.assertEqual(code,0)
            self.assertEqual(result['protocol'],'existing_native_or_unsupported')
            self.assertEqual(f.read_bytes(),original)
            self.assertFalse((p/'research/PROJECT.json').exists())

    def test_incomplete_legacy_freeze_remains_readable_but_cannot_prepare(self):
        q=self.question();x,path=self.contract(q)
        self.run_cli('experiment','freeze','--experiment',x)
        data=json.loads(path.read_text());data['budget']=''
        # Represent a genuine old-format freeze, not a damaged hash.
        path.write_bytes(rh.json_bytes(data))
        snapshot=path.parent/'contract.frozen.json';snapshot.write_bytes(rh.json_bytes(data))
        frozen=path.parent/'frozen.json';manifest=json.loads(frozen.read_text())
        manifest.update(draft_sha256=rh.file_hash(path)[0],snapshot_sha256=rh.file_hash(snapshot)[0])
        frozen.write_bytes(rh.json_bytes(manifest))
        before={p.name:p.read_bytes() for p in path.parent.iterdir()}
        self.assertTrue(self.run_cli('check')['ok'])
        self.assertIn('budget',str(self.fail_cli('attempt','prepare','--experiment',x,
                      '--command','not executed','--authorization-ref','fixture')))
        self.assertEqual(before,{p.name:p.read_bytes() for p in path.parent.iterdir()})
        self.assertEqual(self.run_cli('check')['counts']['attempts'],0)

    def test_unknown_submission_blocks_new_attempt_preparation(self):
        q=self.question();x,_=self.contract(q);self.run_cli('experiment','freeze','--experiment',x)
        a=self.run_cli('attempt','prepare','--experiment',x,'--command','not executed','--authorization-ref','fixture')['id']
        self.run_cli('attempt','update','--attempt',a,'--status','submission_unknown')
        self.fail_cli('attempt','prepare','--experiment',x,'--command','not executed','--authorization-ref','fixture')
        self.assertEqual(self.run_cli('check')['counts']['attempts'],1)

    def test_explicit_cross_branch_reuse_preserves_origin(self):
        a=self.question('A');b=self.question('B');e=self.fixture_evidence(a)
        linked=self.run_cli('evidence','link','--question',b,'--evidence',e,'--reason','Shared baseline; same observations')
        self.assertTrue(linked['reuse_not_independent'])
        self.assertEqual(linked['origin_evidence_id'],e)
        self.reviewed_finding(b,linked['id'])
        self.assertTrue(self.run_cli('check')['ok'])
        self.fail_cli('evidence','link','--question',b,'--evidence',e,'--reason',' ')

    def test_snapshot_has_no_temporary_links_and_reuses_verified_object(self):
        q=self.question();self.doc('data/e.txt','snapshot bytes')
        a=self.run_cli('evidence','add','--question',q,'--file','data/e.txt','--snapshot')
        b=self.run_cli('evidence','add','--question',q,'--file','data/e.txt','--snapshot')
        self.assertEqual(a['sha256'],b['sha256'])
        self.assertEqual(list((self.root/'research/objects').rglob('._obj_*')),[])
        self.assertTrue(self.run_cli('check')['ok'])

    def test_corrupt_existing_snapshot_is_not_reused(self):
        q=self.question();self.doc('data/e.txt','snapshot bytes')
        e=self.run_cli('evidence','add','--question',q,'--file','data/e.txt','--snapshot')['id']
        record=self.run_cli('show','--id',e)['record'];obj=self.root/record['archived_path']
        obj.chmod(0o644);obj.write_text('corrupt',encoding='utf-8')
        self.fail_cli('evidence','add','--question',q,'--file','data/e.txt','--snapshot')
        self.assertEqual(obj.read_text(),'corrupt')

    def test_orphan_parent_and_correction_cycle_have_structured_errors(self):
        q=self.question();path=self.root/self.run_cli('show','--id',q)['path']
        data=json.loads(path.read_text());data['parent_id']='Q-missing';path.write_text(json.dumps(data))
        self.assertIn('unknown parent',str(self.fail_cli('check')))
        data['parent_id']=None;path.write_text(json.dumps(data))
        e=self.fixture_evidence(q);f1=self.reviewed_finding(q,e);f2=self.correction(q,e,f1,None)
        fpath=self.root/self.run_cli('show','--id',f1)['path'];f=json.loads(fpath.read_text());f['supersedes_id']=f2;fpath.write_text(json.dumps(f))
        self.assertIn('correction cycle',str(self.fail_cli('check')))

    def test_legacy_report_without_dependency_snapshot_requires_review(self):
        q=self.question();e=self.fixture_evidence(q);f=self.reviewed_finding(q,e)
        s=self.report(q,[f]);path=self.root/self.run_cli('show','--id',s)['path']
        record=json.loads(path.read_text());del record['finding_state_snapshot'];path.write_text(json.dumps(record))
        self.assertTrue(self.run_cli('check')['warnings'])
        self.fail_cli('question','update','--question',q,'--status','resolved')

    def test_abandonment_requires_reason(self):
        parent=self.question();child=self.question('Cannot access dataset',parent)
        self.fail_cli('question','update','--question',child,'--status','abandoned')
        self.run_cli('question','update','--question',child,'--status','abandoned','--reason','dataset unavailable')
        self.assertTrue(self.run_cli('check')['ok'])

    def test_resolution_is_blocked_by_active_or_uncertain_attempt(self):
        q=self.question('Ongoing question');x,_=self.contract(q)
        self.run_cli('experiment','freeze','--experiment',x)
        at=self.run_cli('attempt','prepare','--experiment',x,'--command','not executed',
                        '--authorization-ref','fixture current permission')['id']
        self.doc('data/result.txt','fixture data')
        e=self.run_cli('evidence','add','--question',q,'--file','data/result.txt')['id']
        f=self.reviewed_finding(q,e)
        self.doc('report.md','# Report\nLimited finding, ongoing task.\n')
        sy=self.run_cli('synthesis','add','--question',q,'--file','report.md','--findings',f)['id']
        self.run_cli('synthesis','review','--synthesis',sy,'--status','reviewed',
                     '--review-ref','human fixture note')
        self.fail_cli('question','update','--question',q,'--status','resolved')
        self.run_cli('attempt','update','--attempt',at,'--status','cancelled','--note','cancelled before launch')
        self.run_cli('question','update','--question',q,'--status','resolved')
        self.assertTrue(self.run_cli('check')['ok'])

    def test_old_parent_synthesis_is_historical_when_child_reopens(self):
        parent=self.question('Root');child=self.question('Child',parent)
        self.doc('data/obs.csv','one,2')
        e=self.run_cli('evidence','add','--question',child,'--file','data/obs.csv')['id']
        f=self.reviewed_finding(child,e)
        self.doc('child.md','# Child report\nScoped result.\n')
        sc=self.run_cli('synthesis','add','--question',child,'--file','child.md','--findings',f)['id']
        self.run_cli('synthesis','review','--synthesis',sc,'--status','reviewed','--review-ref','review-1')
        self.run_cli('question','update','--question',child,'--status','resolved')
        self.doc('parent.md','# Parent report\nCites child scoped result.\n')
        sp=self.run_cli('synthesis','add','--question',parent,'--file','parent.md','--findings',f)['id']
        self.run_cli('synthesis','review','--synthesis',sp,'--status','reviewed','--review-ref','review-2')
        self.run_cli('question','update','--question',parent,'--status','resolved')
        self.run_cli('question','update','--question',parent,'--status','open')
        self.run_cli('question','update','--question',child,'--status','open')
        check=self.run_cli('check')
        self.assertTrue(any('historical reviewed synthesis' in x for x in check['warnings']))
        self.fail_cli('question','update','--question',parent,'--status','resolved')

    def test_reviewer_cannot_accept_tampered_source(self):
        q=self.question()
        file=self.doc('data/result.txt','first observation')
        eid=self.run_cli('evidence','add','--question',q,'--file','data/result.txt')['id']
        fid=self.run_cli('finding','add','--question',q,'--kind','observation',
                         '--statement','Reported observation','--evidence',eid)['id']
        file.write_text('changed observation',encoding='utf-8')
        self.fail_cli('finding','review','--finding',fid,'--status','accepted',
                      '--review-ref','fixture reviewer')

    def test_no_execution_side_effect_and_local_lock(self):
        q=self.question();x,_=self.contract(q)
        self.run_cli('experiment','freeze','--experiment',x)
        cmd='touch '+str(self.root/'NEVER_EXECUTE')
        self.run_cli('attempt','prepare','--experiment',x,'--command',cmd,'--authorization-ref','reference-only')
        self.assertFalse((self.root/'NEVER_EXECUTE').exists())
        lock=self.root/'research/.write.lock';lock.write_text('simulated writer')
        self.fail_cli('question','add','--title','Concurrent writer')
        lock.unlink()
        self.assertTrue(self.run_cli('check')['ok'])

if __name__=='__main__':unittest.main()
