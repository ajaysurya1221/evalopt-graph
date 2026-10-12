import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('run_supervise',Path(__file__).parents[1]/'supervise.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Controls(unittest.TestCase):
    def valid(self):
        return json.dumps({'subtype':'success','is_error':False,'modelUsage':{'claude-fable-5-1':{'provider':'firstParty'}}})
    def test_success(self):
        self.assertEqual(m.classify(0,False,self.valid(),'REPORT 02 — Status DONE',[])['state'],'DONE')
    def test_failures(self):
        for code,timeout,raw,report,errors,reason in [
            (1,False,self.valid(),'REPORT 02 — Status DONE',[],'nonzero_exit'),
            (0,False,'{','REPORT 02 — Status DONE',[],'invalid_json'),
            (0,False,'[]','REPORT 02 — Status DONE',[],'invalid_json'),
            (0,False,self.valid(),'',[],'missing_or_nonaccepted_report'),
            (-15,True,self.valid(),'REPORT 02 — Status DONE',[],'timeout'),
            (0,False,self.valid(),'REPORT 02 — Status DONE',['src/kernel.py'],'out_of_scope'),
            (0,False,self.valid().replace('claude-fable-5-1','other'),'REPORT 02 — Status DONE',[],'model_identity'),
            (0,False,self.valid().replace('firstParty','other'),'REPORT 02 — Status DONE',[],'provider_identity')]:
            with self.subTest(reason=reason):
                result=m.classify(code,timeout,raw,report,errors)
                self.assertEqual(result['state'],'PARTIAL');self.assertIn(reason,result['reasons'])
    def test_rejected_headers_and_identity(self):
        for report in ['REPORT 02 — Status PARTIAL\nEarlier Status DONE',
                       'REVIEW 02 — Reviewer Fable high | Verdict REJECT\nPrior Verdict ACCEPT',
                       'REPORT 03 — Status DONE', 'quoted REPORT 02 — Status DONE']:
            with self.subTest(report=report):
                self.assertEqual(m.classify(0,False,self.valid(),report,[])['state'],'PARTIAL')
    def test_child_survives_leader_term(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            child='import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(30)'
            leader='import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",'+repr(child)+']); time.sleep(30)'
            result=m.execute([sys.executable,'-c',leader],p,p/'out',p/'err',.3)
            self.assertTrue(result['timed_out'])
            self.assertTrue(result['termination_confirmed'])
            self.assertFalse(m.group_live(result['pid']))
    def test_wrong_record_type(self):
        self.assertEqual(m.classify(0,False,self.valid(),'REVIEW 02 — Reviewer Fable high | Verdict ACCEPT',[])['state'],'PARTIAL')
    def test_scope(self):
        self.assertEqual(m.scope_errors(['docs/migration.md','src/kernel.py'],['docs/*.md']),['src/kernel.py'])
    def test_real_process_success_nonzero_timeout(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            for i,program,cap,code,timed in [(0,'print(1)',2,0,False),(1,'raise SystemExit(7)',2,7,False),(2,'import time; time.sleep(5)',.05,None,True)]:
                result=m.execute([sys.executable,'-c',program],p,p/f'{i}.out',p/f'{i}.err',cap)
                self.assertEqual(result['timed_out'],timed)
                if code is not None:self.assertEqual(result['exit_code'],code)
    def test_review(self):
        self.assertEqual(m.classify(0,False,self.valid(),'REVIEW 02 — Reviewer Fable high | Verdict ACCEPT',[],expected_kind='REVIEW')['state'],'DONE')

if __name__=='__main__': unittest.main()
