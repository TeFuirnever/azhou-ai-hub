#!/usr/bin/env python3
"""Analyze pre-registered raw readability frames; collection alone is not acceptance."""
import argparse
import ast
import hashlib
import itertools
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[3]
CHECK = 'theme readability is pixel bounded through viewport changes and legacy handover'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def regions(scenario, sample, size):
    sx, sy = size[0] / scenario['width'], size[1] / scenario['height']
    assert size == (round(scenario['width'] * scenario['dpr']), round(scenario['height'] * scenario['dpr']))
    boxes = {'topProbe': (280, 24, 12, 12), 'sidebarProbe': (24, 180, 12, 12),
             'header': (280, 12, 192, 24), 'sidebar': (24, 128, 96, 192)}
    for group in ('header', 'sidebar'):
        x, y, width, height = boxes[group]
        for row in range(height // 24):
            for col in range(width // 24):
                boxes[f'{group}/tile-{col}-{row}'] = (x + col * 24, y + row * 24, 24, 24)
    rect = sample['evidence'][0]['before']['geometry']
    boxes['boundary'] = (round(rect['x'] + 5), round(rect['y'] - 2), 12, 12)
    return {key: (round(x * sx), round(y * sy), round((x + width) * sx), round((y + height) * sy))
            for key, (x, y, width, height) in boxes.items()}


def metrics(first, second):
    difference = ImageChops.difference(first, second)
    maximum = max(high for low, high in difference.getextrema())
    channels = difference.split()
    any_channel = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2])
    pixels = first.width * first.height
    result = {'max': maximum, 'changedFraction': (pixels - any_channel.histogram()[0]) / pixels}
    for name, a, b in zip('RGB', first.split(), second.split()):
        positive = ImageChops.subtract(b, a).histogram()
        negative = ImageChops.subtract(a, b).histogram()
        plus = sum(positive[1:]) / pixels
        minus = sum(negative[1:]) / pixels
        signed = sum(i * (positive[i] - negative[i]) for i in range(256)) / pixels
        result.update({f'plus{name}': plus, f'minus{name}': minus,
                       f'meanAbs{name}': sum(i * (positive[i] + negative[i]) for i in range(256)) / pixels,
                       f'signedMeanAbs{name}': abs(signed)})
    return result


def session_identity(report):
    environment, cleanup = report['environment'], report['cleanup']
    pid, started = environment.get('chromePID'), report.get('startedAt')
    assert type(pid) is int and pid > 0, 'missing browser process identity'
    assert isinstance(started, str) and started.endswith('Z') and 'T' in started, 'missing session start identity'
    assert environment.get('isolatedTemporaryProfile') is True, 'non-isolated profile'
    assert cleanup.get('ownChromeStopped') is True and cleanup.get('serverClosed') is True, 'session still running'
    assert cleanup.get('errors') == [], 'session cleanup error'
    return pid, started


def validate_source(protocol):
    head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    index = hashlib.sha256(subprocess.check_output(['git','ls-files','--stage','-z'],cwd=ROOT)).hexdigest()
    assert head == protocol['head'] and index == protocol['indexSHA256'], 'HEAD/index drift'
    names = set(subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=ROOT).decode().split('\0')) - {''}
    assert names == set(protocol['sourceSHA256']), 'input inventory drift'
    for name in names:
        assert digest(ROOT/name) == protocol['sourceSHA256'][name], 'source drift: '+name
        assert (ROOT/name).lstat().st_mode == protocol['sourceModes'][name], 'mode drift: '+name


def validate_collection(directory):
    path = directory/'collection-manifest.json'
    manifest = json.loads(path.read_text())
    names = {p.name for p in directory.iterdir() if p.name != path.name}
    assert names == set(manifest['files']), 'collection inventory drift'
    for name, expected in manifest['files'].items():
        assert Path(name).name == name and digest(directory/name) == expected, 'collection artifact drift: '+name
    return {'path':str(path),'sha256':digest(path),'files':manifest['files']}


def validate_session_registration(report, registration, protocol_hash, envelope):
    assert registration['rootProtocolSHA256'] == protocol_hash
    if envelope:
        assert registration['envelopeSHA256'] == envelope['_inputSHA256'], 'different frozen envelope'
        assert registration['frozenAt'] == envelope['frozenAt']
        assert report['startedAt'] > envelope['frozenAt'], 'holdout before freeze'
        pid,started = session_identity(report)
        previous = envelope['browserSessions']
        assert all(str(pid) != value.split('@',1)[0] and started != value.split('@',1)[1] for value in previous), 'training session reused'


def validate_sample(sample):
    assert len(sample['contexts']) == len(sample['evidence']) == 6, 'missing per-frame context'
    first_context = sample['contexts'][0]['before']
    assert first_context['executionLane']=='generated-payload-public-settings', 'source-only sample is not formal evidence'
    assert isinstance(first_context['controllerOwner'],str) and first_context['controllerOwner'], 'missing generated controller identity'
    assert first_context['retained'] is True and first_context['mainConnected'] is True
    assert isinstance(first_context['owner'], str) and first_context['owner'], 'missing owner identity'
    for context, observation in zip(sample['contexts'], sample['evidence']):
        assert context['before'] == context['after'] == first_context, 'paint context or owner drift'
        for state in (observation['before'], observation['after']):
            assert state['status']['applied'] is True and state['status']['themeApplied'] is True
            assert state['status']['themePending'] is False
            assert state['geometry'] == sample['geometry'], 'geometry drift'
        a, b = dict(observation['before']), dict(observation['after'])
        assert b.pop('now') >= a.pop('now')
        assert a == b, 'owner epoch or status drift'
    context_key = {'paint': first_context['paint'], 'viewport': first_context['viewport'],
                   'structure': first_context['structure']['invariant']}
    assert first_context['structure']['alpha'] == (100 - sample['value']) / 100
    return context_key


def claim_condition(seen, key, trial, session):
    assert key not in seen and trial == session, 'duplicate condition/session'
    seen.add(key)


def validate_fault(fault):
    expected = {'rect':'theme structure: workspace geometry y', 'global-wash':'theme structure: not a local color mask',
                'outer-alpha':'external-alpha-invariant-mismatch'}[fault['kind']]
    assert fault['rejected'] is True and fault['rejectionReason'] == expected
    before, injected, restored = [fault[k] for k in ['controlBefore','controlInjected','controlRestored']]
    assert all(state['retained'] is True and state['owner'] == before['owner'] for state in [before,injected,restored])
    assert before['applied'] is True and restored == before
    assert fault['controlBeforeAfter'] == before and fault['controlInjectedAfter'] == injected
    assert fault['mutation']['before'] == before['wash'] and fault['mutation']['after'] == injected['wash']
    assert injected['wash'] != before['wash'] and injected['image'] == before['image']
    assert injected['geometry'] == before['geometry']


def validate_execution(report, protocol, expected):
    before=report['measurementInputs']['before']['execution']
    after=report['measurementInputs']['after']['execution']
    assert before == after, 'formal execution changed during collection'
    assert before['sources'] and before['fixtures'], 'formal execution inventory missing'
    assert before['sources']==protocol['executionSources'], 'formal execution inventory incomplete'
    for name, value in before['sources'].items():
        assert protocol['sourceSHA256'].get('packages/agent-skin/'+name) == value, 'unregistered execution source'
    for value in [before['payloadSHA256'],before['bindingSHA256'],*before['fixtures'].values()]:
        assert isinstance(value,str) and len(value)==64 and all(c in '0123456789abcdef' for c in value), 'invalid execution digest'
    stable={key:before[key] for key in ['sources','fixtures','payloadSHA256']}
    if expected is not None:
        assert stable == expected, 'formal execution content drift across sessions or holdout'
    return stable


def analyze(protocol_path, runs, envelope=None, revision_path=None):
    protocol = json.loads(protocol_path.read_text())
    assert protocol['name'] == 'p07-readability-measurement-v3', 'V3 needs newly registered context-complete frames'
    validate_source(protocol)
    expected_sources = dict(protocol['sourceSHA256'])
    if revision_path:
        revision = json.loads(revision_path.read_text())
        name = 'packages/agent-skin/tools/test-theme-readability-measurement.py'
        assert revision['reason'] == 'session-identity-metadata-only'
        assert revision['collectionProtocolSHA256'] == digest(protocol_path)
        assert revision['previousAnalyzerSHA256'] == expected_sources[name]
        assert revision['revisedAnalyzerSHA256'] == digest(ROOT / name)
        expected_sources[name] = revision['revisedAnalyzerSHA256']
    for name, expected in expected_sources.items():
        assert digest(ROOT / name) == expected, f'evaluator/source drift: {name}'
    expected_phase = 'holdout' if envelope else 'train'
    assert len(runs) == 5, 'five independent registered sessions are required'
    seen_profiles, seen_sessions, seen_pids, seen_starts = set(), set(), set(), set()
    bounds, violations, hard, evidence, contexts, fault_metrics, manifests = {}, [], [], [], {}, [], []
    execution_identity = envelope['executionIdentity'] if envelope else None
    for directory in runs:
        manifests.append(validate_collection(directory))
        report = json.loads((directory / 'report.json').read_text())
        assert report['passed'] is True and 'drift' not in report['measurementInputs']
        execution_identity=validate_execution(report,protocol,execution_identity)
        for checkpoint in ['before','after']:
            observed=report['measurementInputs'][checkpoint]
            assert observed['head']==protocol['head'] and observed['indexSHA256']==protocol['indexSHA256']
            assert observed['inputCount']==len(protocol['sourceSHA256'])
        assert report['environment']['browser'] == protocol['browser']
        assert report['environment']['node'] == protocol['node']
        assert report['environment']['platform'] == 'darwin'
        pid, started = session_identity(report)
        assert pid not in seen_pids and started not in seen_starts, 'duplicate browser session identity'
        seen_pids.add(pid); seen_starts.add(started)
        seen_profiles.add(str(pid) + '@' + started)
        check = next(item for item in report['checks'] if item['name'] == CHECK)
        assert check.get('passed'), 'raw collection structural/geometry/fault checks failed'
        registration = check['details']['protocol']
        assert registration['phase'] == expected_phase
        validate_session_registration(report,registration,digest(protocol_path),envelope)
        assert registration['session'] not in seen_sessions
        seen_sessions.add(registration['session'])
        matrices = json.loads((directory / 'holdout-matrix.json').read_text())
        assert len(matrices) == 4
        seen_conditions=set()
        for row in matrices:
            scenario = row['scenario']
            condition = {key: scenario[key] for key in ('width', 'height', 'dpr', 'zoom', 'color')}
            assert condition in protocol['conditions']
            key = json.dumps(condition, sort_keys=True, separators=(',', ':'))
            claim_condition(seen_conditions,key,scenario['trial'],registration['session'])
            outside_path = directory / f"outside-{scenario['width']}-{scenario['color'][1:]}-{scenario['trial']}.json"
            samples = json.loads(outside_path.read_text())['samples']
            assert sorted(sample['value'] for sample in samples) == protocol['transparencies']
            assert all(fault['rejected'] for fault in row['structuralFaults'])
            assert {(f['kind'], f.get('delta')) for f in row['structuralFaults']} == {
                ('rect', -1), ('rect', 1), ('outer-alpha', 1 / 255), ('outer-alpha', .01), ('global-wash', None)}
            first_structure = samples[0]['structure']['invariant']
            cross_frames = []
            for sample in samples:
                assert sample['structure']['invariant'] == first_structure
                assert sample['structure']['alpha'] == (100 - sample['value']) / 100
                assert sample['applied']['themeApplied'] is True
                assert len(sample['rawFrames']) == protocol['framesPerT'] == 6
                context_key=validate_sample(sample)
                if key in contexts:
                    assert contexts[key] == context_key, 'different registered paint context'
                else:
                    contexts[key] = context_key
                if envelope:
                    assert envelope['contexts'][key] == context_key, 'holdout context differs from frozen training'
                frames = []
                for name in sample['rawFrames']:
                    path = directory / name
                    assert path.parent == directory and path.is_file()
                    with Image.open(path) as source:
                        frames.append(source.convert('RGB'))
                    evidence.append({'path': str(path), 'sha256': digest(path)})
                boxes = regions(scenario, sample, frames[0].size)
                cross_frames.append((sample['value'], frames[0], boxes))
                pairs = [(f'sameT:{sample["value"]}:{a}-{b}', frames[a], frames[b], boxes)
                         for a, b in itertools.combinations(range(6), 2)]
                for pair, first, second, roi in pairs:
                    for region, box in roi.items():
                        result = metrics(first.crop(box), second.crop(box))
                        group = key + '/' + region
                        limits = bounds.setdefault(group, {})
                        for metric, value in result.items():
                            limits[metric] = max(limits.get(metric, 0), value)
                        if envelope:
                            for metric, value in result.items():
                                if value > envelope['bounds'][group][metric]:
                                    violations.append({'group': group, 'pair': pair, 'metric': metric, 'value': value,
                                                       'limit': envelope['bounds'][group][metric]})
            for fault in row['structuralFaults']:
                validate_fault(fault)
                before_path, after_path = directory / fault['rawBefore'], directory / fault['rawAfter']
                assert before_path.parent == directory and after_path.parent == directory
                with Image.open(before_path) as image:
                    before_fault = image.convert('RGB')
                with Image.open(after_path) as image:
                    after_fault = image.convert('RGB')
                evidence.extend({'path':str(path),'sha256':digest(path)} for path in [before_path,after_path])
                boxes = regions(scenario,samples[0],before_fault.size)
                fault_metrics.append({'session': registration['session'], 'condition': key,
                                      'kind':fault['kind'],'delta':fault.get('delta'),'structureDetected':fault['rejected'],
                                      'metrics':{region:metrics(before_fault.crop(box),after_fault.crop(box)) for region,box in boxes.items()}})
            if envelope:
                for (ta, first, boxes), (tb, second, _) in itertools.combinations(cross_frames, 2):
                    for region, box in boxes.items():
                        if region == 'boundary':
                            continue  # The authorized inside opacity differs across T.
                        result = metrics(first.crop(box), second.crop(box))
                        group, pair = key + '/' + region, f'crossT:{ta}-{tb}'
                        for metric, value in result.items():
                            if value > envelope['bounds'][group][metric]:
                                violations.append({'group': group, 'pair': pair, 'metric': metric, 'value': value,
                                                   'limit': envelope['bounds'][group][metric]})
    validate_source(protocol)
    comparison_bounds = envelope['bounds'] if envelope else bounds
    for fault in fault_metrics:
        fault['pixelDetectedRegions'] = [region for region,result in fault['metrics'].items()
            if any(value > comparison_bounds[fault['condition']+'/'+region][metric] for metric,value in result.items())]
        fault['pixelDetected'] = bool(fault['pixelDetectedRegions'])
        fault['pixelComparison'] = 'frozen-training-envelope' if envelope else 'training-envelope-diagnostic'
    status = 'hard-failure' if hard else 'inconclusive' if violations else 'holdout-passed' if envelope else 'training-frozen'
    return {'schema': 1, 'status': status, 'protocolSHA256': digest(protocol_path),
            'analysisRevisionSHA256': digest(revision_path) if revision_path else None,
            'boundRule': 'unmodified training upper envelopes; signed means use absolute value; no margins',
            'limitations': 'Finite observed training envelope, not a universal or future noise guarantee. Old strict-zero and V2 hard-max-one failures remain failed; V3 calibrates maximum per observed paint context.',
            'executionIdentity':execution_identity,'collectionManifests':manifests,'frozenAt':datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z') if not envelope else None,
            'faultDetection': fault_metrics, 'contexts': contexts, 'bounds': bounds, 'violations': violations, 'hardFailures': hard, 'frames': evidence,
            'browserSessions': sorted(seen_profiles), 'sessions': sorted(seen_sessions)}


def register(directory, browser, node):
    directory = directory.resolve()
    assert ROOT not in directory.parents and directory != ROOT, 'evidence must be outside the repository'
    assert browser.startswith('Chrome/') and node.startswith('v'), 'explicit measured browser/Node identities required'
    names = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).decode().split('\0')
    sources = {name: digest(ROOT / name) for name in sorted(set(names)) if name and (ROOT / name).is_file()}
    build_tree=ast.parse((ROOT/'packages/agent-skin/tools/test-startup-build.py').read_text())
    clone_files=next(ast.literal_eval(statement.value) for statement in build_tree.body if isinstance(statement,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='BUILD_FILES' for target in statement.targets))
    execution_sources={name:sources['packages/agent-skin/'+name] for name in clone_files}
    protocol = {'schema': 1, 'name': 'p07-readability-measurement-v3', 'browser': browser, 'node': node,
                'conditions': [dict(width=w, height=h, dpr=d, zoom=z, color=c)
                               for w,h,d,z in [(997,613,1.5,.9),(811,577,2,1.1)]
                               for c in ['#123b57','#d8c49a']],
                'transparencies': [0,15,57,85,100], 'framesPerT': 6,
                'trainingSessions': 5, 'holdoutSessions': 5, 'sourceSHA256': sources,'executionSources':execution_sources,
                'sourceModes':{name:(ROOT/name).lstat().st_mode for name in sources},
                'head': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                'indexSHA256': hashlib.sha256(subprocess.check_output(['git','ls-files','--stage','-z'],cwd=ROOT)).hexdigest(),
                'threshold': 'per-condition/paint-context/ROI observed upper envelope including max, no margin',
                'protocolDocument': 'packages/agent-skin/docs/readability-measurement-v3.md',
                'priorFailures': 'V1 strict-zero and V2 hard-max-one remain failed; no old frames reused'}
    directory.mkdir(parents=True, exist_ok=False)
    path = directory / 'protocol.json'
    path.write_text(json.dumps(protocol,indent=2))
    for phase in ['train']:
        for session in range(5):
            order = protocol['transparencies'] if phase == 'train' else ([57,0,100,15,85] if session%2==0 else [85,15,100,0,57])
            config = {k: protocol[k] for k in ['schema','conditions','framesPerT']}
            config.update(phase=phase,session=session,transparencies=order,rootProtocolSHA256=digest(path),rootProtocolPath=str(path))
            (directory / f'{phase}-{session}.json').write_text(json.dumps(config,indent=2))
    return {'protocol':str(path),'sha256':digest(path),'inputCount':len(sources)}


def register_holdout(directory, protocol_path, envelope_path):
    protocol=json.loads(protocol_path.read_text());validate_source(protocol)
    envelope=json.loads(envelope_path.read_text())
    assert envelope['status']=='training-frozen' and envelope['protocolSHA256']==digest(protocol_path)
    assert envelope['frozenAt'] < datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
    directory=directory.resolve();assert ROOT not in directory.parents and directory!=ROOT
    directory.mkdir(parents=True,exist_ok=False)
    for session in range(5):
        config={k:protocol[k] for k in ['schema','conditions','framesPerT']}
        config.update(phase='holdout',session=session,transparencies=[57,0,100,15,85] if session%2==0 else [85,15,100,0,57],
                      rootProtocolPath=str(protocol_path.resolve()),rootProtocolSHA256=digest(protocol_path),
                      envelopePath=str(envelope_path.resolve()),envelopeSHA256=digest(envelope_path),frozenAt=envelope['frozenAt'])
        (directory/f'holdout-{session}.json').write_text(json.dumps(config,indent=2))
    return {'directory':str(directory),'envelopeSHA256':digest(envelope_path),'frozenAt':envelope['frozenAt']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--register', type=Path)
    parser.add_argument('--register-holdout', type=Path)
    parser.add_argument('--browser-version')
    parser.add_argument('--node-version')
    parser.add_argument('--protocol', type=Path)
    parser.add_argument('--runs', nargs=5, type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--envelope', type=Path)
    parser.add_argument('--analysis-revision', type=Path)
    args = parser.parse_args()
    if args.register:
        assert args.browser_version and args.node_version
        print(json.dumps(register(args.register,args.browser_version,args.node_version)))
        return 0
    if args.register_holdout:
        assert args.protocol and args.envelope
        print(json.dumps(register_holdout(args.register_holdout,args.protocol,args.envelope)))
        return 0
    assert args.protocol and args.runs and args.output, 'analysis needs protocol, five runs and output'
    assert not args.output.exists(), 'never overwrite frozen evidence'
    envelope = json.loads(args.envelope.read_text()) if args.envelope else None
    if envelope:
        envelope['_inputSHA256']=digest(args.envelope)
        assert envelope['status'] == 'training-frozen'
        assert envelope['protocolSHA256'] == digest(args.protocol)
        assert envelope['analysisRevisionSHA256'] == (digest(args.analysis_revision) if args.analysis_revision else None)
    result = analyze(args.protocol, args.runs, envelope, args.analysis_revision)
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps({key: result[key] for key in ('status', 'protocolSHA256')}))
    return 1 if result['status'] == 'hard-failure' else 2 if result['status'] == 'inconclusive' else 0


if __name__ == '__main__':
    raise SystemExit(main())
