"""Read-only baseline comparison, including the sole allowed source version edit."""
import hashlib
import json
from pathlib import Path
import subprocess

BASE = 'fc3045dbda29c1d274747329ceb6724a783b0df7'
ROOT = Path(__file__).resolve().parents[2]


def main():
    names = subprocess.check_output(['git','ls-tree','-r','--name-only',BASE,'src','tests','bench'],cwd=ROOT,text=True).splitlines()
    errors = []
    for name in names:
        old = subprocess.check_output(['git','show',f'{BASE}:{name}'],cwd=ROOT)
        path = ROOT/name
        if not path.is_file():
            errors.append(name + ': missing')
            continue
        new = path.read_bytes()
        if name == 'src/evalopt_graph/__init__.py':
            new = new.replace(b'__version__ = "0.1.1"', b'__version__ = "0.1.0"')
        if old != new:
            errors.append(name + ': bytes changed')
    new_names = subprocess.check_output(['git','ls-files','src','tests','bench'],cwd=ROOT,text=True).splitlines()
    errors += [n + ': new protected path' for n in new_names if n not in names]
    plan = ROOT/'plan/exec/PLAN.md'
    if hashlib.sha256(plan.read_bytes()).hexdigest() != '697f3fd7fa61b294146fff13868c87d6762d00395f39d8085ba52a111eb22b3c':
        errors.append('approved PLAN bytes changed')
    print(json.dumps({'baseline':BASE,'protected_files':len(names),'errors':errors}))
    raise SystemExit(bool(errors))

if __name__=='__main__': main()
