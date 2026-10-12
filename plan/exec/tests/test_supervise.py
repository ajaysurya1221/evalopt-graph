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
            (1,False,self.valid(),'Status DONE',[],'nonzero_exit'),
            (0,False,'{','Status DONE',[],'invalid_json'),
            (0,False,'[]','Status DONE',[],'invalid_json'),
            (0,False,self.valid(),'',[],'missing_or_nonaccepted_report'),
            (-15,True,self.valid(),'Status DONE',[],'timeout'),
            (0,False,self.valid(),'Status DONE',['src/kernel.py'],'out_of_scope'),
            (0,False,self.valid().replace('claude-fable-5-1','other'),'Status DONE',[],'model_identity'),
            (0,False,self.valid().replace('firstParty','other'),'Status DONE',[],'provider_identity')]:
            with self.subTest(reason=reason):
                result=m.classify(code,timeout,raw,report,errors)
                self.assertEqual(result['state'],'PARTIAL');self.assertIn(reason,result['reasons'])
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
        self.assertEqual(m.classify(0,False,self.valid(),'REVIEW 02 — Verdict ACCEPT',[])['state'],'DONE')

if __name__=='__main__': unittest.main()
