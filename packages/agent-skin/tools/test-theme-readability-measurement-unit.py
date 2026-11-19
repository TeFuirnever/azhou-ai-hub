#!/usr/bin/env python3
"""Cheap evidence-integrity controls; no browser or product execution."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
spec=importlib.util.spec_from_file_location('measurement',Path(__file__).with_name('test-theme-readability-measurement.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class EvidenceControls(unittest.TestCase):
    def sample(self):
        state={'now':1,'geometry':{'x':0},'status':{'applied':True,'themeApplied':True,'themePending':False}}
        context={'executionLane':'generated-payload-public-settings','controllerOwner':'payload-owner','retained':True,'mainConnected':True,'owner':'test-owner','paint':{},'viewport':{},'structure':{'invariant':{},'alpha':1}}
        return {'value':0,'geometry':{'x':0},'evidence':[{'before':copy.deepcopy(state),'after':copy.deepcopy(state)} for _ in range(6)],'contexts':[{'before':copy.deepcopy(context),'after':copy.deepcopy(context)} for _ in range(6)]}
    def test_source_only_sample_cannot_enter_formal_analysis(self):
        sample=self.sample()
        for pair in sample['contexts']:
            for context in pair.values():context['executionLane']='source-fixture'
        with self.assertRaises(AssertionError):m.validate_sample(sample)
    def test_geometry_is_required(self):
        sample=self.sample();m.validate_sample(sample);del sample['geometry']
        with self.assertRaises(KeyError):m.validate_sample(sample)
    def test_owner_must_remain_valid(self):
        for key in ['retained','mainConnected']:
            sample=self.sample();sample['contexts'][0]['before'][key]=False
            with self.assertRaises(AssertionError):m.validate_sample(sample)
        sample=self.sample();sample['evidence'][0]['after']['status']['applied']=False
        with self.assertRaises(AssertionError):m.validate_sample(sample)
    def test_condition_and_session_are_unique(self):
        seen=set();m.claim_condition(seen,'condition',0,0)
        with self.assertRaises(AssertionError):m.claim_condition(seen,'condition',0,0)
        with self.assertRaises(AssertionError):m.claim_condition(set(),'condition',1,0)
    def test_report_and_png_tampering_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix='theme-integrity-test-') as tmp:
            root=Path(tmp)
            for name in ['report.json','outside.json','holdout-matrix.json','frame.png']:(root/name).write_bytes(b'original')
            manifest={'files':{p.name:m.digest(p) for p in root.iterdir()}}
            (root/'collection-manifest.json').write_text(json.dumps(manifest));m.validate_collection(root)
            for name in ['report.json','frame.png','outside.json']:
                (root/name).write_bytes(b'changed')
                with self.assertRaises(AssertionError):m.validate_collection(root)
                (root/name).write_bytes(b'original')
    def registration(self):
        report={'startedAt':'2026-11-15T00:01:00.000Z','environment':{'chromePID':20,'isolatedTemporaryProfile':True},'cleanup':{'ownChromeStopped':True,'serverClosed':True,'errors':[]}}
        envelope={'_inputSHA256':'frozen','frozenAt':'2026-11-15T00:00:00.000Z','browserSessions':['10@2026-11-14T00:00:00.000Z']}
        registration={'rootProtocolSHA256':'protocol','envelopeSHA256':'frozen','frozenAt':envelope['frozenAt']}
        return report,registration,envelope
    def test_holdout_requires_binding_and_new_session(self):
        report,registration,envelope=self.registration();m.validate_session_registration(report,registration,'protocol',envelope)
        del registration['envelopeSHA256']
        with self.assertRaises(KeyError):m.validate_session_registration(report,registration,'protocol',envelope)
        report,registration,envelope=self.registration();report['environment']['chromePID']=10
        with self.assertRaises(AssertionError):m.validate_session_registration(report,registration,'protocol',envelope)
        report,registration,envelope=self.registration();report['startedAt']=envelope['frozenAt']
        with self.assertRaises(AssertionError):m.validate_session_registration(report,registration,'protocol',envelope)
    def test_formal_execution_identity_is_required_and_stable(self):
        source={'packages/agent-skin/tools/test-startup-browser.mjs':'a'*64}
        identity={'sources':{'tools/test-startup-browser.mjs':'a'*64},'fixtures':{'assets/private/scene.png':'b'*64},'payloadSHA256':'c'*64,'bindingSHA256':'d'*64}
        report={'measurementInputs':{'before':{'execution':copy.deepcopy(identity)},'after':{'execution':copy.deepcopy(identity)}}}
        protocol={'sourceSHA256':source,'executionSources':identity['sources']}
        stable=m.validate_execution(report,protocol,None)
        omitted=copy.deepcopy(protocol);omitted['executionSources']['tools/required.mjs']='a'*64
        with self.assertRaises(AssertionError):m.validate_execution(report,omitted,None)
        for invalid in [{}, {'measurementInputs':{'before':{},'after':{}}}]:
            with self.assertRaises((KeyError,AssertionError)):m.validate_execution(invalid,protocol,None)
        for field in ['payloadSHA256','fixtures','sources']:
            bad=copy.deepcopy(report)
            bad['measurementInputs']['before']['execution'][field]= 'e'*64 if field=='payloadSHA256' else {'bad':'e'*64}
            with self.assertRaises(AssertionError):m.validate_execution(bad,protocol,None)
            bad['measurementInputs']['after']['execution']=copy.deepcopy(bad['measurementInputs']['before']['execution'])
            with self.assertRaises(AssertionError):m.validate_execution(bad,protocol,stable)
        other=copy.deepcopy(report)
        for checkpoint in ['before','after']:other['measurementInputs'][checkpoint]['execution']['bindingSHA256']='f'*64
        self.assertEqual(m.validate_execution(other,protocol,stable),stable)

    def test_fault_generic_exception_is_not_detection(self):
        with self.assertRaises(AssertionError):m.validate_fault({'kind':'rect','rejected':True,'rejectionReason':'TypeError'})

if __name__=='__main__':unittest.main()
