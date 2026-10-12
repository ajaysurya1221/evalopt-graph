import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('preservation',Path(__file__).parents[1]/'preservation.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

class Preservation(unittest.TestCase):
    def test_untracked_source_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            subprocess.run(['git','init','-q',d],check=True)
            (root/'src').mkdir();(root/'src/a.py').write_text('x=1\n')
            subprocess.run(['git','add','src/a.py'],cwd=root,check=True)
            subprocess.run(['git','-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','fixture'],cwd=root,check=True)
            base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
            (root/'plan/exec').mkdir(parents=True)
            original=Path(__file__).parents[1]/'PLAN.md'
            (root/'plan/exec/PLAN.md').write_bytes(original.read_bytes())
            with patch.object(p,'ROOT',root),patch.object(p,'BASE',base):
                with contextlib.redirect_stdout(io.StringIO()),self.assertRaises(SystemExit) as code:p.main()
                self.assertEqual(code.exception.code,False)
                (root/'src/untracked_new_capability.py').write_text('x=2\n')
                output=io.StringIO()
                with contextlib.redirect_stdout(output),self.assertRaises(SystemExit) as code:p.main()
                self.assertEqual(code.exception.code,True)
                self.assertIn('untracked_new_capability.py: new protected path',output.getvalue())

if __name__=='__main__': unittest.main()
