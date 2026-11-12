#!/usr/bin/env python3
"""Research Harness: local, file-first research-question and evidence ledger.

Python 3.10+ stdlib only. This program never executes an experiment, submits a job,
contacts a network service, or authenticates a human authorization.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import sys
import tempfile
from typing import Any
from uuid import uuid4

VERSION = '0.2.1'
SCHEMA = 2
RECORDS = {
    'Q': 'question.json',
    'X': 'contract.json',
    'AT': None,
    'E': None,
    'F': None,
    'S': 'record.json',
}
STATUS_QUESTION = {'open', 'investigating', 'blocked', 'resolved', 'abandoned'}
STATUS_ATTEMPT = {'prepared', 'submitted', 'running', 'submission_unknown', 'completed', 'failed', 'cancelled'}
TRANSITIONS = {
    'prepared': {'submitted', 'running', 'submission_unknown', 'failed', 'cancelled'},
    'submitted': {'running', 'submission_unknown', 'completed', 'failed', 'cancelled'},
    'running': {'completed', 'failed', 'submission_unknown', 'cancelled'},
    'submission_unknown': {'submitted', 'running', 'completed', 'failed', 'cancelled'},
    'completed': set(), 'failed': set(), 'cancelled': set(),
}
SENSITIVE = {'.env', 'id_rsa', 'id_ed25519', 'credentials.json', 'token.json', 'tokens.json'}
SENSITIVE_SUFFIXES = {'.pem', '.key', '.p12', '.pfx'}

class RHError(Exception):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def project_root(value: str) -> Path:
    p = Path(value).expanduser().resolve(strict=True)
    if not p.is_dir():
        raise RHError('project root must be an existing directory')
    return p


def ledger(root: Path) -> Path:
    p = root / 'research'
    if p.is_symlink():
        raise RHError('research/ must be a real directory, not a symlink')
    if not (p / 'PROJECT.json').is_file():
        raise RHError('no Research Harness v2 project found; run init in an empty research/ location')
    data = load_json(p / 'PROJECT.json')
    if data.get('schema_version') != SCHEMA:
        raise RHError('unsupported research protocol version; this build does not migrate old projects')
    return p


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(p: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    n = 0
    with p.open('rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''):
            h.update(part)
            n += len(part)
    return h.hexdigest(), n


def load_json(p: Path) -> dict[str, Any]:
    def unique(pairs):
        obj = {}
        for k,v in pairs:
            if k in obj:
                raise RHError(f'duplicate JSON key in {p}: {k}')
            obj[k]=v
        return obj
    try:
        with p.open('r', encoding='utf-8') as f:
            d = json.load(f, object_pairs_hook=unique, parse_constant=lambda s: (_ for _ in ()).throw(RHError(f'invalid constant {s} in {p}')))
    except (ValueError, OSError) as e:
        raise RHError(f'cannot load {p}: {e}') from e
    if not isinstance(d, dict):
        raise RHError(f'{p} must contain a JSON object')
    return d


def json_bytes(obj: dict) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')


def write_json(p: Path, obj: dict, *, new: bool = False) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='._rh_', dir=p.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(json_bytes(obj))
            f.flush()
            os.fsync(f.fileno())
        if new:
            try:
                os.link(name, p)
            except FileExistsError as e:
                raise RHError(f'will not overwrite existing record: {p}') from e
        else:
            if not p.exists():
                raise RHError(f'record to update is missing: {p}')
            os.replace(name, p)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def slugify(s: str) -> str:
    x = re.sub(r'[^a-z0-9\u4e00-\u9fff]+', '-', s.lower()).strip('-')[:40]
    return x or 'question'


def new_id(prefix: str) -> str:
    return prefix + '-' + uuid4().hex[:12]


def relative_file(root: Path, arg: str) -> tuple[Path, str]:
    if not arg or not isinstance(arg, str):
        raise RHError('path must be a non-empty project-relative path')
    norm = arg.replace('\\','/')
    parts = PurePosixPath(norm)
    if parts.is_absolute() or PureWindowsPath(arg).drive or '..' in parts.parts or any(':' in x for x in parts.parts):
        raise RHError('file path must stay inside project root')
    p = (root / Path(*parts.parts)).resolve(strict=True)
    try:
        rel = p.relative_to(root).as_posix()
    except ValueError as e:
        raise RHError('file path escapes project root (including symlink)') from e
    if not p.is_file():
        raise RHError('file is missing or not a regular file')
    name = p.name.lower()
    if name in SENSITIVE or name.startswith('.env.') or p.suffix.lower() in SENSITIVE_SUFFIXES:
        raise RHError('refusing to register a credential-like file')
    return p, rel


@contextmanager
def single_writer(p: Path):
    """Fail-closed local single-writer guard; not a distributed lock."""
    lock = p / '.write.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as e:
        raise RHError('another writer or a stale .write.lock exists; inspect before manually removing') from e
    try:
        with os.fdopen(fd,'w', encoding='utf-8') as f:
            f.write(f'pid={os.getpid()} at={now()}\n')
        yield
    finally:
        lock.unlink(missing_ok=True)


def safe_destination(research: Path, path: Path) -> None:
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(research.resolve(strict=True))
    except ValueError as exc:
        raise RHError(f'record destination escapes research directory: {path}') from exc


def scan(root: Path, k: str) -> dict[str,tuple[Path,dict]]:
    p = ledger(root)
    patterns = {
        'Q':'questions/**/question.json',
        'X':'questions/**/experiments/X-*/contract.json',
        'AT':'questions/**/attempts/AT-*.json',
        'E':'questions/**/evidence/E-*.json',
        'F':'questions/**/findings/F-*.json',
        'S':'questions/**/syntheses/S-*/record.json',
    }
    found = {}
    for path in p.glob(patterns[k]):
        if path.is_symlink():raise RHError(f'symlink record is not allowed: {path}')
        safe_destination(p,path)
        d=load_json(path)
        rid=d.get('id')
        if not isinstance(rid,str) or not rid.startswith(k+'-'):
            raise RHError(f'missing/invalid {k} ID at {path}')
        if rid in found:
            raise RHError(f'duplicate {k} ID {rid}')
        found[rid]=(path,d)
    return found


def lookup(root: Path, rid: str) -> tuple[Path,dict]:
    k=rid.split('-',1)[0]
    if k not in RECORDS:
        raise RHError('unknown record type; expected Q, X, AT, E, F or S')
    records=scan(root,k)
    if rid not in records:
        raise RHError(f'unknown record ID: {rid}')
    return records[rid]


def qdir(root: Path, qid: str) -> Path:
    return lookup(root,qid)[0].parent


def ancestry(qs: dict, child: str, ancestor: str) -> bool:
    seen=set()
    current=child
    while current is not None:
        if current==ancestor:
            return True
        if current in seen or current not in qs:
            return False
        seen.add(current)
        current=qs[current][1].get('parent_id')
    return False


def conclusion_state(root: Path, qs=None, fs=None, ss=None, ats=None) -> dict:
    """Derive current applicability without overwriting historical decisions."""
    qs = scan(root, 'Q') if qs is None else qs
    fs = scan(root, 'F') if fs is None else fs
    ss = scan(root, 'S') if ss is None else ss
    ats = scan(root, 'AT') if ats is None else ats
    replacements = {fid: [] for fid in fs}
    for fid, (_, record) in fs.items():
        previous = record.get('supersedes_id')
        if record.get('status') == 'accepted' and previous in replacements:
            replacements[previous].append(fid)
    finding_views = {
        fid: {'current': f.get('status') == 'accepted' and not replacements[fid],
              'currency': ('superseded' if replacements[fid] else
                           'current' if f.get('status') == 'accepted' else 'unreviewed'),
              'superseded_by': sorted(replacements[fid])}
        for fid, (_, f) in fs.items()
    }
    questions, reports, visiting = {}, {}, set()

    def visit(qid):
        if qid in questions:
            return questions[qid]
        if qid in visiting:
            return {'status': 'needs_review', 'latest_complete_synthesis_id': None}
        visiting.add(qid)
        record = qs[qid][1]
        children = sorted(cid for cid, (_, c) in qs.items() if c.get('parent_id') == qid)
        child_views = {cid: visit(cid) for cid in children}
        snapshot = [{'question_id': cid, 'status': child_views[cid]['status'],
                     'latest_complete_synthesis_id': child_views[cid]['latest_complete_synthesis_id']}
                    for cid in children]
        incomplete = [cid for cid in children
                      if child_views[cid]['status'] not in {'resolved', 'abandoned'}]
        coverage = 'partial' if incomplete else 'complete'
        complete = []
        for sid, (_, report) in ss.items():
            if report.get('question_id') != qid:
                continue
            reasons = []
            fids = report.get('finding_ids', [])
            if not fids:
                reasons.append('no supporting findings')
            for fid in fids:
                if not finding_views.get(fid, {}).get('current'):
                    reasons.append('finding is missing, unaccepted, or superseded: ' + str(fid))
            expected = report.get('finding_state_snapshot')
            current = {fid: content_hash(json_bytes(fs[fid][1])) for fid in fids if fid in fs}
            if expected is None:
                reasons.append('legacy report lacks dependency snapshot; create a new reviewed synthesis')
            elif expected != current:
                reasons.append('cited finding revisions changed')
            if sorted(report.get('direct_child_question_ids', [])) != children:
                reasons.append('direct child list changed')
            if report.get('child_status_snapshot', []) != snapshot:
                reasons.append('child status or current conclusion changed')
            if report.get('coverage') != coverage:
                reasons.append('child coverage changed')
            current_report = report.get('status') == 'reviewed' and not reasons
            reports[sid] = {'current': current_report,
                            'currency': ('current' if current_report else
                                         'needs_review' if report.get('status') == 'reviewed' else 'unreviewed'),
                            'reasons': reasons, 'effective_coverage': coverage}
            if current_report and coverage == 'complete':
                complete.append((report.get('reviewed_at') or '', sid))
        latest = max(complete)[1] if complete else None
        active = sorted(aid for aid, (_, a) in ats.items()
                        if a.get('question_id') in qs and ancestry(qs, a['question_id'], qid)
                        and a.get('status') in {'prepared', 'submitted', 'running', 'submission_unknown'})
        effective = record.get('status')
        reasons = []
        if effective == 'resolved':
            if not latest:
                reasons.append('no current complete reviewed synthesis')
            if incomplete:
                reasons.append('unresolved direct children')
            if active:
                reasons.append('active or uncertain attempts in subtree')
            if reasons:
                effective = 'needs_review'
        questions[qid] = {'status': effective, 'recorded_status': record.get('status'),
                          'resolution_reasons': reasons, 'latest_complete_synthesis_id': latest,
                          'child_status_snapshot': snapshot, 'coverage': coverage,
                          'incomplete_child_question_ids': incomplete, 'active_attempt_ids': active}
        visiting.remove(qid)
        return questions[qid]

    for qid in qs:
        visit(qid)
    return {'findings': finding_views, 'syntheses': reports, 'questions': questions}


def resolved_focus(root: Path, qs: dict) -> dict:
    """FOCUS selects a question; that question owns its next action."""
    focus = load_json(ledger(root) / 'FOCUS.json')
    qid = focus.get('question_id')
    if qid is not None and qid not in qs:
        raise RHError('focus question does not exist')
    return {'question_id': qid,
            'next_action': qs[qid][1].get('next_action') if qid else 'Define a bounded research question',
            'next_action_source': 'question.json' if qid else 'uninitialized focus',
            'updated_at': focus.get('updated_at')}


def do_inspect(args):
    """Read-only protocol discovery; does not parse or migrate native ledgers."""
    root = project_root(args.project_root)
    research = root / 'research'
    if not research.exists() and not research.is_symlink():
        return {'ok': True, 'protocol': 'none', 'next_action': 'Read project instructions; init only for an authorized new project'}
    if research.is_symlink():
        return {'ok': True, 'protocol': 'external_or_symlink', 'next_action': 'Use the existing project workflow; do not initialize v2'}
    if (research / 'PROJECT.json').is_file():
        try:
            version = load_json(research / 'PROJECT.json').get('schema_version')
        except RHError as error:
            return {'ok': False, 'protocol': 'unreadable_project_record', 'errors': [str(error)]}
        if version == SCHEMA:
            return {'ok': True, 'protocol': 'research-harness-v2', 'next_action': 'Run status and check; read the referenced current records'}
    markers = [p.name for p in research.iterdir() if p.name in
               {'CURRENT_STATE.yaml', 'CURRENT_STATE.json', 'PROJECT.json', 'PROJECT_SCOPE.md', 'facts.yaml'}]
    return {'ok': True, 'protocol': 'existing_native_or_unsupported', 'observed_markers': sorted(markers),
            'scientific_state': 'not_assessed',
            'next_action': 'Read existing project instructions and canonical records; use native validators; do not initialize or fabricate a second ledger'}


def do_init(args):
    root=project_root(args.project_root)
    research=root/'research'
    if research.exists() or research.is_symlink():
        raise RHError('research/ already exists; refusing to replace or import it')
    research.mkdir()
    (research/'questions').mkdir()
    (research/'objects').mkdir()
    # Local snapshots can contain sensitive data: do not add them to Git by default.
    (research/'objects'/'.gitignore').write_text('*\n!.gitignore\n', encoding='utf-8')
    try:
        write_json(research/'PROJECT.json', {
            'schema_version':SCHEMA,'title':args.title,'objective':args.objective or '',
            'created_at':now(),'execution_policy':'Human/host-authorized only; no CLI command runs experiments',
        },new=True)
        write_json(research/'FOCUS.json', {'question_id':None,'updated_at':now()},new=True)
    except Exception:
        # Keep an incomplete project visible for inspection rather than deleting possible concurrent work.
        raise
    return {'ok':True,'operation':'init','root':str(research),'next':'question add'}


def do_question_add(args):
    root=project_root(args.project_root); p=ledger(root)
    if args.parent:
        parent_path,parent=lookup(root,args.parent)
        if not args.parent.startswith('Q-'):
            raise RHError('parent must be a question ID')
        if parent.get('status') in {'resolved','abandoned'}:
            raise RHError('cannot attach a new subquestion to a closed parent; reopen it first')
        base=parent_path.parent/'subquestions'
    else:
        base=p/'questions'
    qid=new_id('Q')
    with single_writer(p):
        if args.parent:
            _, parent = lookup(root, args.parent)
            if parent.get('status') in {'resolved', 'abandoned'}:
                raise RHError('parent was closed; reopen it before adding a child')
        dest=base/(qid+'--'+slugify(args.title))
        safe_destination(p,dest)
        dest.mkdir(parents=True,exist_ok=False)
        write_json(dest/'question.json', {
            'schema_version':SCHEMA,'id':qid,'parent_id':args.parent,'title':args.title,
            'research_uncertainty':args.uncertainty or args.title,'why_it_matters':args.why or '',
            'status':'open','mode':args.mode,'created_at':now(),
            'next_action':'Clarify hypotheses, available evidence, and testable outcomes',
            'constraints':[],
        },new=True)
    return {'ok':True,'id':qid,'parent_id':args.parent,'path':(dest/'question.json').relative_to(root).as_posix()}


def do_question_update(args):
    root=project_root(args.project_root); p=ledger(root)
    path,d=lookup(root,args.question)
    if not args.question.startswith('Q-'):
        raise RHError('expected question ID')
    with single_writer(p):
        d=load_json(path)
        if args.status=='resolved':
            checked=do_check(args)
            if not checked['ok']:
                raise RHError('cannot resolve question while integrity check fails: '+ '; '.join(checked['errors'][:3]))
            current=conclusion_state(root)['questions'][args.question]
            if not current['latest_complete_synthesis_id']:
                raise RHError('cannot resolve question without a complete, reviewed synthesis')
            qs=scan(root,'Q')
            pending=[aid for aid,(_,a) in scan(root,'AT').items()
                     if a.get('question_id') in qs and ancestry(qs,a['question_id'],args.question)
                     and a.get('status') in {'prepared','submitted','running','submission_unknown'}]
            if pending:
                raise RHError('cannot resolve question while attempts remain active or uncertain: '+', '.join(pending))
            children=[v for _,v in scan(root,'Q').values() if v.get('parent_id')==args.question]
            if current['incomplete_child_question_ids']:
                raise RHError('cannot resolve question with unfinished direct subquestions')
        if args.status=='abandoned' and not (args.reason or '').strip():
            raise RHError('abandoning a question requires --reason')
        if args.status:d['status']=args.status
        if args.next_action:d['next_action']=args.next_action
        if args.reason:d['status_reason']=args.reason
        d['updated_at']=now()
        write_json(path,d)
    return {'ok':True,'id':args.question,'status':d['status'],'next_action':d['next_action']}


def do_focus(args):
    root=project_root(args.project_root); p=ledger(root)
    lookup(root,args.question)
    if not args.question.startswith('Q-'):
        raise RHError('focus must be a question')
    path=p/'FOCUS.json'
    with single_writer(p):
        qpath, question = lookup(root,args.question)
        if args.next_action is not None:
            if not args.next_action.strip():
                raise RHError('next action must not be empty')
            question['next_action'] = args.next_action
            question['updated_at'] = now()
            write_json(qpath, question)
        write_json(path, {'question_id':args.question,'updated_at':now()})
    return {'ok':True,'focus_question_id':args.question,'next_action':question['next_action'],
            'next_action_source':'question.json'}


def empty_contract(qid: str, xid: str, title: str, mode: str) -> dict:
    return {
        'schema_version':SCHEMA,'id':xid,'question_id':qid,'title':title,'mode':mode,
        'research_question':'','hypotheses':[],'falsifying_outcomes':[],
        'method':'','inputs':[],'outputs':[],
        'controls':[],'metrics':[],'statistical_unit':'','selection_rule':'',
        'missingness_rule':'','decision_rule':'','randomness':'',
        'data_access':'','budget':'','stopping_rule':'','risk_notes':[],
        'implementation_ref':'','environment_ref':'','created_at':now(),
    }


def do_experiment_create(args):
    root=project_root(args.project_root); p=ledger(root)
    qpath,q=lookup(root,args.question)
    if not args.question.startswith('Q-'):raise RHError('experiment needs a question ID')
    if q.get('status') in {'resolved','abandoned'}:raise RHError('question is closed; reopen it before designing a new experiment')
    xid=new_id('X')
    base=qpath.parent/'experiments'/xid
    with single_writer(p):
        safe_destination(p,base)
        base.mkdir(parents=True, exist_ok=False)
        write_json(base/'contract.json',empty_contract(args.question,xid,args.title,args.mode),new=True)
    return {'ok':True,'id':xid,'contract':(base/'contract.json').relative_to(root).as_posix(), 'next':'edit this contract, then experiment freeze'}


def ensure_frozen(root: Path, x_path: Path, c: dict) -> dict:
    frozen=x_path.parent/'frozen.json'
    snapshot=x_path.parent/'contract.frozen.json'
    if not frozen.is_file() or not snapshot.is_file():
        raise RHError('experiment not frozen: run experiment freeze before preparing an attempt')
    f=load_json(frozen)
    fresh_hash=file_hash(x_path)[0]
    if f.get('draft_sha256')!=fresh_hash:
        raise RHError('contract.json changed after freeze; create a new experiment/revision')
    if f.get('snapshot_sha256') != file_hash(snapshot)[0]:
        raise RHError('frozen contract changed')
    if load_json(snapshot)!=c:
        raise RHError('frozen contract differs from draft')
    return f


def filled(v: Any) -> bool:
    if isinstance(v,str):return bool(v.strip())
    if isinstance(v,list):return bool(v) and all(filled(item) for item in v)
    if isinstance(v,dict):return bool(v) and all(filled(item) for item in v.values())
    return v is not None


def require_complete_contract(c: dict) -> None:
    if c.get('mode') not in {'exploratory', 'confirmatory'}:
        raise RHError('contract mode must be exploratory or confirmatory')
    required=['research_question','method','inputs','outputs','stopping_rule','metrics',
              'statistical_unit','randomness','data_access','budget','implementation_ref','environment_ref']
    if c['mode']=='confirmatory':
        required += ['hypotheses','falsifying_outcomes','controls','selection_rule',
                     'missingness_rule','decision_rule']
    missing=[key for key in required if not filled(c.get(key))]
    if missing:
        raise RHError('contract incomplete for '+c['mode']+': '+', '.join(missing)+
                      '; preserve frozen history and create a complete new design before new attempts')


def do_experiment_freeze(args):
    root=project_root(args.project_root); p=ledger(root)
    path,c=lookup(root,args.experiment)
    if not args.experiment.startswith('X-'):raise RHError('expected experiment ID')
    if (path.parent/'frozen.json').exists():raise RHError('experiment is already frozen; create a new experiment for changed conditions')
    require_complete_contract(c)
    with single_writer(p):
        c=load_json(path)
        if (path.parent/'frozen.json').exists():raise RHError('experiment is already frozen')
        require_complete_contract(c)
        snapshot=path.parent/'contract.frozen.json'
        write_json(snapshot,c,new=True)
        frozen={
            'schema_version':SCHEMA,'experiment_id':args.experiment,'mode':c['mode'],
            'draft_sha256':file_hash(path)[0],'snapshot_sha256':file_hash(snapshot)[0],
            'frozen_at':now(),'authorization':'not_assessed', 'scientific_validity':'not_assessed',
        }
        write_json(path.parent/'frozen.json',frozen,new=True)
    return {'ok':True,'id':args.experiment,'snapshot_sha256':frozen['snapshot_sha256'],'authorization':'not_assessed'}


def do_attempt_prepare(args):
    root=project_root(args.project_root); p=ledger(root)
    x_path,c=lookup(root,args.experiment)
    if not args.experiment.startswith('X-'):raise RHError('expected experiment ID')
    frozen=ensure_frozen(root,x_path,c)
    if not args.authorization_ref.strip():raise RHError('current approval reference is required; a string is not proof of authorization')
    qid=c['question_id']; q_path,_=lookup(root,qid)
    aid=new_id('AT')
    data={
        'schema_version':SCHEMA,'id':aid,'experiment_id':args.experiment,'question_id':qid,
        'frozen_contract_sha256':frozen['snapshot_sha256'],
        'command_description':args.command,'authorization_ref':args.authorization_ref,
        'status':'prepared','created_at':now(),'history':[{'status':'prepared','at':now(),'receipt_ref':None}],
        'failure_reason':None,
    }
    output=q_path.parent/'attempts'/(aid+'.json')
    with single_writer(p):
        safe_destination(p,output)
        x_path, c = lookup(root, args.experiment)
        frozen = ensure_frozen(root, x_path, c)
        require_complete_contract(c)
        if frozen['snapshot_sha256'] != data['frozen_contract_sha256']:
            raise RHError('frozen contract changed while preparing the attempt')
        _, question = lookup(root, qid)
        if question.get('status') in {'resolved', 'abandoned'}:
            raise RHError('question is closed; reopen it before preparing an attempt')
        unknown = [aid for aid, (_, a) in scan(root, 'AT').items()
                   if a.get('experiment_id') == args.experiment and a.get('status') == 'submission_unknown']
        if unknown:
            raise RHError('reconcile unknown submission before preparing another attempt: ' + ', '.join(unknown))
        write_json(output,data,new=True)
    return {'ok':True,'id':aid,'status':'prepared','important':'Record only: no command has been executed; verify approval externally before running'}


def do_attempt_update(args):
    root=project_root(args.project_root); p=ledger(root)
    path,_=lookup(root,args.attempt)
    if not args.attempt.startswith('AT-'):raise RHError('expected attempt ID')
    if args.status in {'submitted','running','completed'} and not args.receipt_ref:
        raise RHError('receipt-ref / observed external status source required for submitted, running or completed')
    with single_writer(p):
        d=load_json(path)
        state=d['status']
        if args.status not in TRANSITIONS.get(state,set()):
            raise RHError(f'invalid attempt transition: {state} -> {args.status}')
        d['status']=args.status
        event={'status':args.status,'at':now(),'receipt_ref':args.receipt_ref or None}
        if args.note:event['note']=args.note
        d['history'].append(event)
        if args.status=='failed':d['failure_reason']=args.note or 'unspecified'
        write_json(path,d)
    return {'ok':True,'id':args.attempt,'status':args.status,'scientific_acceptance':'not_assessed'}


def do_evidence_add(args):
    root=project_root(args.project_root); p=ledger(root)
    qpath,_=lookup(root,args.question)
    if not args.question.startswith('Q-'):raise RHError('expected question ID')
    source,source_rel=relative_file(root,args.file)
    if args.attempt:
        _,a=lookup(root,args.attempt)
        if a.get('question_id')!=args.question:raise RHError('attempt is not linked to the selected question')
        # Partial diagnostics from a running/failed attempt are evidence of observation,
        # but never evidence of a completed or scientifically accepted result.
    sha,size=file_hash(source)
    eid=new_id('E'); copied=None
    with single_writer(p):
        if args.snapshot:
            obj=p/'objects'/sha[:2]/sha
            safe_destination(p,obj)
            if obj.is_symlink():
                raise RHError('snapshot object must not be a symlink')
            obj.parent.mkdir(parents=True,exist_ok=True)
            if not obj.exists():
                fd,tmp=tempfile.mkstemp(prefix='._obj_',dir=obj.parent)
                try:
                    with os.fdopen(fd,'wb') as out,source.open('rb') as inp:
                        shutil.copyfileobj(inp,out,1024*1024)
                        out.flush();os.fsync(out.fileno())
                    if file_hash(Path(tmp))[0]!=sha:raise RHError('source changed while snapshotting evidence')
                    try:
                        os.link(tmp,obj)
                    except FileExistsError:pass
                finally:
                    if os.path.exists(tmp):os.unlink(tmp)
                # Remove the temporary hard link before setting shared Windows attributes.
                try:obj.chmod(0o444)
                except OSError:pass
            if file_hash(obj) != (sha,size):
                raise RHError('existing snapshot object has wrong bytes; preserve it and investigate')
            copied=obj.relative_to(root).as_posix()
        item={'schema_version':SCHEMA,'id':eid,'question_id':args.question,'attempt_id':args.attempt,
              'role':args.role,'description':args.description,'source_path':source_rel,
              'sha256':sha,'bytes':size,'archived_path':copied,'created_at':now(),
              'scientific_acceptance':'not_assessed','is_complete':False}
        output=qpath.parent/'evidence'/(eid+'.json')
        safe_destination(p,output)
        write_json(output,item,new=True)
    return {'ok':True,'id':eid,'sha256':sha,'archived':bool(copied),'record':output.relative_to(root).as_posix()}


def do_evidence_link(args):
    root=project_root(args.project_root);p=ledger(root)
    if not args.reason.strip():raise RHError('explicit reuse reason is required')
    if not args.question.startswith('Q-') or not args.evidence.startswith('E-'):
        raise RHError('expected target question and source evidence IDs')
    with single_writer(p):
        checked=do_check(args)
        if not checked['ok']:raise RHError('cannot link evidence while integrity check fails')
        qpath,_=lookup(root,args.question)
        _,source=lookup(root,args.evidence)
        origin=source.get('origin_evidence_id') or args.evidence
        eid=new_id('E')
        item=dict(source)
        item.update(id=eid, question_id=args.question, attempt_id=None, created_at=now(),
                    derived_from_evidence_id=args.evidence, origin_evidence_id=origin,
                    source_question_id=source['question_id'], reuse_reason=args.reason,
                    reuse_not_independent=True)
        output=qpath.parent/'evidence'/(eid+'.json')
        safe_destination(p,output)
        write_json(output,item,new=True)
    return {'ok':True,'id':eid,'origin_evidence_id':origin,'reuse_not_independent':True,
            'note':'Explicit reuse of existing bytes; not a new run or independent replication'}


def find_evidence(root:Path, ids:list[str], qid:str) -> None:
    qs=scan(root,'Q')
    for eid in ids:
        _,e=lookup(root,eid)
        if not eid.startswith('E-') or not ancestry(qs,e['question_id'],qid):
            raise RHError(f'evidence {eid} is not in question subtree {qid}')


def do_finding_add(args):
    root=project_root(args.project_root); p=ledger(root)
    qpath,_=lookup(root,args.question)
    if not args.question.startswith('Q-'):raise RHError('finding must belong to question')
    evidence=args.evidence or [];counter=args.counterevidence or []
    if args.kind in {'observation','scoped_claim'} and not evidence:
        raise RHError('observation/scoped claim requires at least one evidence ID')
    if args.kind=='scoped_claim' and not (args.scope or '').strip():
        raise RHError('scoped claim must specify scope')
    find_evidence(root,evidence+counter,args.question)
    fid=new_id('F')
    item={'schema_version':SCHEMA,'id':fid,'question_id':args.question,'kind':args.kind,
          'statement':args.statement,'scope':args.scope or '', 'evidence_ids':evidence,
          'counterevidence_ids':counter,'limitations':args.limitations or '',
          'status':'proposed','review_ref':None,'supersedes_id':args.supersedes,
          'created_at':now()}
    if args.supersedes:
        _,old=lookup(root,args.supersedes)
        if not args.supersedes.startswith('F-') or old['question_id']!=args.question:
            raise RHError('superseded finding must be in same question')
    output=qpath.parent/'findings'/(fid+'.json')
    with single_writer(p):
        safe_destination(p,output)
        write_json(output,item,new=True)
    return {'ok':True,'id':fid,'status':'proposed','note':'Recording a claim is not validating it'}


def do_finding_review(args):
    root=project_root(args.project_root); p=ledger(root)
    path,_=lookup(root,args.finding)
    if not args.finding.startswith('F-'):raise RHError('expected finding ID')
    if not args.review_ref.strip():raise RHError('explicit review-source reference required (the CLI cannot authenticate it)')
    with single_writer(p):
        d=load_json(path)
        if d['status']!='proposed':raise RHError('finding already reviewed; create a superseding finding for a correction')
        if args.status=='accepted' and d['kind']=='hypothesis':
            raise RHError('hypotheses cannot be accepted as established facts; create an evidence-supported scoped claim')
        if args.status=='accepted':
            checked=do_check(args)
            if not checked['ok']:
                raise RHError('cannot accept finding while integrity check fails: '+ '; '.join(checked['errors'][:3]))
        d['status']=args.status;d['review_ref']=args.review_ref;d['reviewed_at']=now()
        write_json(path,d)
    return {'ok':True,'id':args.finding,'status':args.status,'review_authenticity':'not_assessed'}


def direct_children(root: Path, qid: str) -> list[tuple[str,dict]]:
    return sorted(((cid,rec) for cid,(_,rec) in scan(root,'Q').items()
                   if rec.get('parent_id')==qid), key=lambda x:x[0])


def child_status_snapshot(root: Path, qid: str) -> list[dict]:
    return conclusion_state(root)['questions'][qid]['child_status_snapshot']


def synthesis_coverage(root: Path, qid: str) -> tuple[str,list[str]]:
    current=conclusion_state(root)['questions'][qid]
    return current['coverage'], current['incomplete_child_question_ids']


def do_synthesis_add(args):
    root=project_root(args.project_root);p=ledger(root)
    qpath,_=lookup(root,args.question)
    if not args.question.startswith('Q-'):raise RHError('synthesis must belong to question')
    src,rel=relative_file(root,args.file)
    if not src.suffix.lower() in {'.md','.txt'}:raise RHError('synthesis must be a Markdown or text file')
    qs=scan(root,'Q');findings=[]
    for fid in args.findings or []:
        _,f=lookup(root,fid)
        if not fid.startswith('F-') or not ancestry(qs,f['question_id'],args.question):
            raise RHError(f'finding {fid} is outside question subtree')
        findings.append(f)
    sid=new_id('S'); dest=qpath.parent/'syntheses'/sid
    text=src.read_bytes()
    if not text.strip():raise RHError('synthesis is empty')
    with single_writer(p):
        coverage,incomplete=synthesis_coverage(root,args.question)
        safe_destination(p,dest)
        dest.mkdir(parents=True,exist_ok=False)
        snapshot=dest/'report.md'
        with snapshot.open('xb') as out:out.write(text)
        record={'schema_version':SCHEMA,'id':sid,'question_id':args.question,
                'source_document':rel,'document_path':snapshot.relative_to(root).as_posix(),
                'sha256':content_hash(text),'finding_ids':args.findings or [],
                'finding_state_snapshot':{fid:content_hash(json_bytes(lookup(root,fid)[1])) for fid in args.findings or []},
                'direct_child_question_ids':[cid for cid,_ in direct_children(root,args.question)],
                'child_status_snapshot':child_status_snapshot(root,args.question),
                'incomplete_child_question_ids':incomplete,
                'coverage':coverage,
                'limitations':args.limitations,'status':'proposed','review_ref':None,
                'created_at':now()}
        write_json(dest/'record.json',record,new=True)
    return {'ok':True,'id':sid,'status':'proposed','coverage':coverage,
            'incomplete_children':incomplete,'finding_count':len(findings),
            'note':'Synthesis is not automatically established scientific truth'}


def do_synthesis_review(args):
    root=project_root(args.project_root);p=ledger(root)
    path,d=lookup(root,args.synthesis)
    if not args.synthesis.startswith('S-'):raise RHError('expected synthesis ID')
    if not args.review_ref.strip():raise RHError('review-source reference required')
    with single_writer(p):
        d=load_json(path)
        if d['status']!='proposed':raise RHError('synthesis already reviewed')
        coverage,incomplete=synthesis_coverage(root,d['question_id'])
        old_children=set(d.get('direct_child_question_ids',[]))
        current_children={cid for cid,_ in direct_children(root,d['question_id'])}
        if old_children!=current_children:
            raise RHError('child-question list changed since synthesis; create a new synthesis')
        if d.get('child_status_snapshot',[])!=child_status_snapshot(root,d['question_id']):
            raise RHError('child statuses or reviewed conclusions changed; draft a new synthesis reflecting updated evidence')
        if args.status=='reviewed':
            abandoned=[cid for cid,c in direct_children(root,d['question_id']) if c.get('status')=='abandoned']
            if abandoned and not d.get('limitations','').strip():
                raise RHError('synthesis with abandoned children must explicitly record limitations: '+', '.join(abandoned))
            checked=do_check(args)
            if not checked['ok']:
                raise RHError('cannot review synthesis while integrity check fails: '+ '; '.join(checked['errors'][:3]))
            if not d.get('finding_ids'):raise RHError('cannot review an evidence-free synthesis as complete')
            findings=scan(root,'F')
            current=conclusion_state(root)['findings']
            for fid in d['finding_ids']:
                if not current[fid]['current']:
                    raise RHError(f'synthesis uses an unaccepted or superseded finding: {fid}')
            revisions={fid:content_hash(json_bytes(findings[fid][1])) for fid in d['finding_ids']}
            if d.get('finding_state_snapshot') != revisions:
                raise RHError('finding revisions changed or legacy dependency snapshot missing; create a new synthesis')
            if incomplete and not args.allow_partial:
                raise RHError('open/unreviewed child questions: '+', '.join(incomplete)+'; use --allow-partial with documented limitations')
            if incomplete and not d.get('limitations','').strip():
                raise RHError('partial synthesis must document limitations')
        d['status']=args.status;d['review_ref']=args.review_ref;d['reviewed_at']=now()
        d['coverage']=coverage;d['incomplete_child_question_ids']=incomplete
        write_json(path,d)
    return {'ok':True,'id':args.synthesis,'status':args.status,'coverage':coverage,
            'incomplete_children':incomplete,'review_authenticity':'not_assessed'}


def do_show(args):
    root=project_root(args.project_root)
    p,d=lookup(root,args.id)
    result={'ok':True,'path':p.relative_to(root).as_posix(),'record':d}
    kind=args.id.split('-',1)[0]
    if kind in {'Q','F','S'}:
        collection={'Q':'questions','F':'findings','S':'syntheses'}[kind]
        result['interpretation']=conclusion_state(root)[collection].get(args.id)
    return result


def do_status(args):
    root=project_root(args.project_root);p=ledger(root)
    qs=scan(root,'Q');xs=scan(root,'X');ats=scan(root,'AT');ev=scan(root,'E');fs=scan(root,'F');ss=scan(root,'S')
    focus=resolved_focus(root,qs)
    if args.question and args.question not in qs:raise RHError('unknown focus question')
    if args.limit < 1:raise RHError('limit must be positive')
    selected=args.question or focus.get('question_id')
    state=conclusion_state(root,qs,fs,ss,ats)
    def item(qid,visited):
        d=qs[qid][1];view=state['questions'][qid]
        result={'id':qid,'title':d.get('title'),'status':view['status'],
                'recorded_status':d.get('status'),'resolution_reasons':view['resolution_reasons'],
                'latest_complete_synthesis_id':view['latest_complete_synthesis_id'],
                'mode':d.get('mode'),'next_action':d.get('next_action')}
        result['children']=[] if qid in visited else [item(cid,visited|{qid}) for cid in sorted(qs)
                                                     if qs[cid][1].get('parent_id')==qid]
        return result
    tree=[item(selected,set())] if selected else [item(qid,set()) for qid in sorted(qs) if qs[qid][1].get('parent_id') is None]
    subtree={qid for qid in qs if selected is None or ancestry(qs,qid,selected)}
    def recent(records):return sorted(records.items(),key=lambda entry:(entry[1][1].get('created_at',''),entry[0]))
    findings=[dict(id=fid,question_id=d['question_id'],statement=d['statement'],status=d['status'],
                   kind=d.get('kind'),scope=d.get('scope'),supersedes_id=d.get('supersedes_id'),
                   evidence_ids=d.get('evidence_ids',[]),counterevidence_ids=d.get('counterevidence_ids',[]),
                   **state['findings'][fid]) for fid,(_,d) in recent(fs) if d['question_id'] in subtree]
    attempts=[{'id':aid,'experiment_id':d['experiment_id'],'status':d['status'],
               'last_observation':d.get('history',[])[-1] if d.get('history') else None}
              for aid,(_,d) in recent(ats) if d['question_id'] in subtree]
    syntheses=[dict(id=sid,question_id=d['question_id'],status=d['status'],coverage=d.get('coverage'),
                    document_path=d.get('document_path'),finding_ids=d.get('finding_ids',[]),
                    **state['syntheses'][sid]) for sid,(_,d) in recent(ss) if d['question_id'] in subtree]
    evidence_refs=[{'id':eid,'question_id':d['question_id'],'attempt_id':d.get('attempt_id'),
                    'source_path':d.get('source_path'),'archived':bool(d.get('archived_path')),
                    'origin_evidence_id':d.get('origin_evidence_id') or eid,
                    'derived_from_evidence_id':d.get('derived_from_evidence_id'),
                    'reuse_not_independent':bool(d.get('reuse_not_independent'))}
                   for eid,(_,d) in recent(ev) if d['question_id'] in subtree]
    return {'ok':True,'project':load_json(p/'PROJECT.json')['title'],'focus':focus,'questions':tree,
            'counts':{'questions':len(subtree),'experiments':sum(d['question_id'] in subtree for _,d in xs.values()),
                      'attempts':len(attempts),'evidence':len(evidence_refs),'findings':len(findings),'syntheses':len(syntheses)},
            'attempts':attempts[-args.limit:],'findings':findings[-args.limit:],
            'syntheses':syntheses[-args.limit:],'evidence_refs':evidence_refs[-args.limit:],
            'open_question_ids':sorted(qid for qid in subtree if state['questions'][qid]['status'] in {'open','investigating','blocked','needs_review'}),
            'note':'Recorded state only; last observation timestamps do not prove live executor status'}


def do_check(args):
    root=project_root(args.project_root);p=ledger(root)
    qs=scan(root,'Q');xs=scan(root,'X');ats=scan(root,'AT');es=scan(root,'E');fs=scan(root,'F');ss=scan(root,'S')
    errors=[];warnings=[]
    for records in [qs,xs,ats,es,fs,ss]:
        for rid,(_,d) in records.items():
            if d.get('schema_version')!=SCHEMA:errors.append(f'{rid}: unsupported record schema')
    focus=load_json(p/'FOCUS.json');focus_id=focus.get('question_id')
    if focus_id is not None and focus_id not in qs:errors.append('focus question does not exist')
    if 'next_action' in focus and focus_id in qs:
        if focus['next_action'] != qs[focus_id][1].get('next_action'):
            errors.append('legacy FOCUS next_action conflicts with question; explicitly normalize using focus --question ID [--next-action TEXT]')
        else:warnings.append('legacy FOCUS next_action is ignored; normalize with focus --question ID')
    for qid,(path,d) in qs.items():
        parent=d.get('parent_id')
        if parent is not None and parent not in qs:errors.append(f'{qid}: unknown parent {parent}')
        seen=set();cur=qid
        while cur is not None and cur in qs:
            if cur in seen:errors.append(f'{qid}: question ancestry cycle');break
            seen.add(cur);cur=qs[cur][1].get('parent_id')
        if d.get('status') not in STATUS_QUESTION:errors.append(f'{qid}: invalid question status')
        if not isinstance(d.get('next_action'),str) or not d['next_action'].strip():errors.append(f'{qid}: missing next action')
        if d.get('status')=='abandoned' and not d.get('status_reason'):errors.append(f'{qid}: abandoned without reason')
        if parent is None and path.parent.parent != p/'questions':errors.append(f'{qid}: root question in wrong directory')
        if parent in qs and path.parent.parent != qs[parent][0].parent/'subquestions':errors.append(f'{qid}: physically outside direct parent')
    for xid,(path,c) in xs.items():
        if c.get('question_id') not in qs:errors.append(f'{xid}: missing question')
        if c.get('mode') not in {'exploratory','confirmatory'}:errors.append(f'{xid}: invalid experiment mode')
        if (path.parent/'frozen.json').exists() or (path.parent/'contract.frozen.json').exists():
            try:ensure_frozen(root,path,c)
            except (RHError,OSError) as e:errors.append(f'{xid}: {e}')
    for aid,(_,a) in ats.items():
        if a.get('question_id') not in qs:errors.append(f'{aid}: unknown question')
        if a.get('experiment_id') not in xs:errors.append(f'{aid}: unknown experiment')
        else:
            xp,c=xs[a['experiment_id']]
            if c.get('question_id')!=a.get('question_id'):errors.append(f'{aid}: question/experiment mismatch')
            try:
                frozen=ensure_frozen(root,xp,c)
                if a.get('frozen_contract_sha256')!=frozen.get('snapshot_sha256'):errors.append(f'{aid}: frozen contract digest mismatch')
            except (RHError,OSError) as e:errors.append(f'{aid}: {e}')
        if a.get('status') not in STATUS_ATTEMPT:errors.append(f'{aid}: invalid status')
        history=a.get('history')
        if not isinstance(history,list) or not history or history[0].get('status')!='prepared':
            errors.append(f'{aid}: missing prepared history');continue
        previous=None
        for event in history:
            status=event.get('status')
            if previous is not None and status not in TRANSITIONS.get(previous,set()):errors.append(f'{aid}: invalid history transition {previous} -> {status}')
            if status in {'submitted','running','completed'} and not event.get('receipt_ref'):errors.append(f'{aid}: missing observed receipt')
            previous=status
        if previous!=a.get('status'):errors.append(f'{aid}: status/history mismatch')
    for eid,(_,e) in es.items():
        if e.get('question_id') not in qs:errors.append(f'{eid}: unknown question')
        if not e.get('source_path'):errors.append(f'{eid}: missing source path')
        if e.get('attempt_id') and e['attempt_id'] not in ats:errors.append(f'{eid}: unknown attempt')
        if e.get('attempt_id') in ats and ats[e['attempt_id']][1].get('question_id')!=e.get('question_id'):errors.append(f'{eid}: attempt/question mismatch')
        for ref in ['source_path','archived_path']:
            if not e.get(ref):continue
            try:
                file,_=relative_file(root,e[ref]);sha,size=file_hash(file)
                if sha!=e.get('sha256') or size!=e.get('bytes'):errors.append(f'{eid}: {ref} hash/size mismatch')
            except (RHError,OSError) as err:errors.append(f'{eid}: {ref}: {err}')
        source=e.get('derived_from_evidence_id')
        if source:
            if source not in es:errors.append(f'{eid}: missing reused evidence')
            else:
                original=es[source][1]
                if any(e.get(k)!=original.get(k) for k in ['source_path','sha256','bytes','archived_path']):errors.append(f'{eid}: reuse changes source identity')
                if not e.get('reuse_reason') or not e.get('reuse_not_independent'):errors.append(f'{eid}: reuse provenance incomplete')
                origin=original.get('origin_evidence_id') or source
                if e.get('origin_evidence_id')!=origin:errors.append(f'{eid}: reuse origin mismatch')
            seen=set();cur=eid
            while cur in es:
                if cur in seen:errors.append(f'{eid}: evidence reuse cycle');break
                seen.add(cur);cur=es[cur][1].get('derived_from_evidence_id')
    for fid,(_,f) in fs.items():
        if f.get('question_id') not in qs:errors.append(f'{fid}: unknown question')
        if f.get('status') not in {'proposed','accepted','rejected'}:errors.append(f'{fid}: invalid finding status')
        if f.get('kind') not in {'hypothesis','observation','scoped_claim'}:errors.append(f'{fid}: invalid finding kind')
        if f.get('kind') in {'observation','scoped_claim'} and not f.get('evidence_ids'):errors.append(f'{fid}: evidence required')
        if f.get('kind')=='scoped_claim' and not f.get('scope'):errors.append(f'{fid}: scope required')
        if f.get('status')=='accepted':
            if not f.get('review_ref'):errors.append(f'{fid}: accepted without review reference')
            if f.get('kind')=='hypothesis':errors.append(f'{fid}: hypothesis cannot be accepted as fact')
        for eid in f.get('evidence_ids',[])+f.get('counterevidence_ids',[]):
            if eid not in es:errors.append(f'{fid}: unknown evidence {eid}')
            elif f.get('question_id') in qs and not ancestry(qs,es[eid][1]['question_id'],f['question_id']):errors.append(f'{fid}: evidence from unrelated question {eid}')
        sup=f.get('supersedes_id')
        if sup and (sup not in fs or sup==fid):errors.append(f'{fid}: invalid supersedes_id')
        if sup in fs and fs[sup][1].get('question_id')!=f.get('question_id'):errors.append(f'{fid}: correction outside question')
        seen=set();cur=fid
        while cur in fs:
            if cur in seen:errors.append(f'{fid}: correction cycle');break
            seen.add(cur);cur=fs[cur][1].get('supersedes_id')
    for sid,(_,s) in ss.items():
        if s.get('question_id') not in qs:errors.append(f'{sid}: unknown question')
        if s.get('status') not in {'proposed','reviewed','rejected'}:errors.append(f'{sid}: invalid synthesis status')
        if s.get('coverage') not in {'complete','partial'}:errors.append(f'{sid}: invalid coverage')
        if s.get('status')=='reviewed' and (not s.get('review_ref') or not s.get('finding_ids')):errors.append(f'{sid}: reviewed without review reference or findings')
        for fid in s.get('finding_ids',[]):
            if fid not in fs:errors.append(f'{sid}: unknown finding {fid}')
            elif s['question_id'] in qs and not ancestry(qs,fs[fid][1]['question_id'],s['question_id']):errors.append(f'{sid}: finding from unrelated question {fid}')
        try:
            file,_=relative_file(root,s['document_path'])
            if file_hash(file)[0]!=s.get('sha256'):errors.append(f'{sid}: document hash mismatch')
        except (RHError,OSError,KeyError) as err:errors.append(f'{sid}: document: {err}')
    state=conclusion_state(root,qs,fs,ss,ats) if not errors else None
    if state:
        for sid,view in state['syntheses'].items():
            if view['currency']=='needs_review':warnings.append(f'{sid}: historical reviewed synthesis needs re-review: '+ '; '.join(view['reasons']))
        for qid,view in state['questions'].items():
            if view['status']=='needs_review':warnings.append(f'{qid}: recorded resolution is stale; effective status needs_review')
    return {'ok':not errors,'operation':'check','errors':errors,'warnings':warnings,
            'counts':{'questions':len(qs),'experiments':len(xs),'attempts':len(ats),'evidence':len(es),'findings':len(fs),'syntheses':len(ss)},
            'needs_review_question_ids':sorted(qid for qid,view in state['questions'].items() if view['status']=='needs_review') if state else [],
            'scientific_validity':'not_assessed','authorization_authenticity':'not_assessed',
            'concurrency':'single-local-writer only; not a distributed lock'}


def parser():
    ap=argparse.ArgumentParser(description='Research Harness v2; maintains a research question tree and verifies local records; never runs experiments')
    ap.add_argument('--project-root',default='.',help='existing target repository directory (default: .)')
    sub=ap.add_subparsers(dest='command',required=True)
    inspect=sub.add_parser('inspect');inspect.set_defaults(func=do_inspect)
    init=sub.add_parser('init');init.add_argument('--title',required=True);init.add_argument('--objective',default='');init.set_defaults(func=do_init)
    question=sub.add_parser('question');qsub=question.add_subparsers(dest='operation',required=True)
    q=qsub.add_parser('add');q.add_argument('--title',required=True);q.add_argument('--parent');q.add_argument('--uncertainty');q.add_argument('--why');q.add_argument('--mode',choices=['exploratory','confirmatory'],default='exploratory');q.set_defaults(func=do_question_add)
    q=qsub.add_parser('update');q.add_argument('--question',required=True);q.add_argument('--status',choices=sorted(STATUS_QUESTION));q.add_argument('--next-action');q.add_argument('--reason');q.set_defaults(func=do_question_update)
    focus=sub.add_parser('focus');focus.add_argument('--question',required=True);focus.add_argument('--next-action');focus.set_defaults(func=do_focus)
    exp=sub.add_parser('experiment');exsub=exp.add_subparsers(dest='operation',required=True)
    e=exsub.add_parser('create');e.add_argument('--question',required=True);e.add_argument('--title',required=True);e.add_argument('--mode',choices=['exploratory','confirmatory'],default='exploratory');e.set_defaults(func=do_experiment_create)
    e=exsub.add_parser('freeze');e.add_argument('--experiment',required=True);e.set_defaults(func=do_experiment_freeze)
    attempt=sub.add_parser('attempt');asub=attempt.add_subparsers(dest='operation',required=True)
    a=asub.add_parser('prepare');a.add_argument('--experiment',required=True);a.add_argument('--command',required=True);a.add_argument('--authorization-ref',required=True);a.set_defaults(func=do_attempt_prepare)
    a=asub.add_parser('update');a.add_argument('--attempt',required=True);a.add_argument('--status',choices=sorted(STATUS_ATTEMPT),required=True);a.add_argument('--receipt-ref');a.add_argument('--note');a.set_defaults(func=do_attempt_update)
    evidence=sub.add_parser('evidence');esub=evidence.add_subparsers(dest='operation',required=True)
    e=esub.add_parser('add');e.add_argument('--question',required=True);e.add_argument('--attempt');e.add_argument('--file',required=True);e.add_argument('--role',choices=['output','log','dataset','analysis','source','other'],default='output');e.add_argument('--description',default='');e.add_argument('--snapshot',action='store_true');e.set_defaults(func=do_evidence_add)
    e=esub.add_parser('link');e.add_argument('--question',required=True);e.add_argument('--evidence',required=True);e.add_argument('--reason',required=True);e.set_defaults(func=do_evidence_link)
    finding=sub.add_parser('finding');fsub=finding.add_subparsers(dest='operation',required=True)
    f=fsub.add_parser('add');f.add_argument('--question',required=True);f.add_argument('--kind',choices=['observation','hypothesis','scoped_claim'],required=True);f.add_argument('--statement',required=True);f.add_argument('--scope');f.add_argument('--evidence',nargs='*');f.add_argument('--counterevidence',nargs='*');f.add_argument('--limitations');f.add_argument('--supersedes');f.set_defaults(func=do_finding_add)
    f=fsub.add_parser('review');f.add_argument('--finding',required=True);f.add_argument('--status',choices=['accepted','rejected'],required=True);f.add_argument('--review-ref',required=True);f.set_defaults(func=do_finding_review)
    syn=sub.add_parser('synthesis');ssub=syn.add_subparsers(dest='operation',required=True)
    s=ssub.add_parser('add');s.add_argument('--question',required=True);s.add_argument('--file',required=True);s.add_argument('--findings',nargs='*');s.add_argument('--limitations',default='');s.set_defaults(func=do_synthesis_add)
    s=ssub.add_parser('review');s.add_argument('--synthesis',required=True);s.add_argument('--status',choices=['reviewed','rejected'],required=True);s.add_argument('--review-ref',required=True);s.add_argument('--allow-partial',action='store_true');s.set_defaults(func=do_synthesis_review)
    show=sub.add_parser('show');show.add_argument('--id',required=True);show.set_defaults(func=do_show)
    status=sub.add_parser('status');status.add_argument('--question');status.add_argument('--limit',type=int,default=20);status.set_defaults(func=do_status)
    check=sub.add_parser('check');check.set_defaults(func=do_check)
    return ap


def main(argv=None):
    try:
        args=parser().parse_args(argv)
        result=args.func(args)
    except (RHError,OSError,TypeError,ValueError,KeyError,UnicodeDecodeError) as exc:
        result={'ok':False,'errors':[str(exc)]}
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    return 0 if result.get('ok') else 1

if __name__=='__main__':sys.exit(main())
