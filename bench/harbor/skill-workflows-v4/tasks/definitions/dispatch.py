"""Fresh authored task definition, executed by author.py with explicit helper bindings."""

code = globals()["code"]
author = globals()["author"]

source = {
    "service.py": code("""
 from events import apply_events
 from dependencies import propagate,ready
 from fairness import choose
 def solve(q):
     jobs={j['id']:dict(j) for j in q['jobs']}
     state={i:{'state':'pending','finished':None,'remaining':j['work']} for i,j in jobs.items()}
     served={t:0 for t in q['weights']}; trace=[]
     for now in range(q['horizon']+1):
         apply_events(jobs,state,q['cancel'],now); propagate(jobs,state,now)
         if now==q['horizon']: break
         options=[j for i,j in jobs.items() if state[i]['state']=='pending' and ready(j,state,now)]
         selected=choose(options,served,q['weights'])
         trace.append(selected['id'] if selected else None)
         if selected:
             i=selected['id']; state[i]['remaining']-=1; served[selected['tenant']]+=1
             if state[i]['remaining']==0: state[i].update(state='complete',finished=now+1)
     return {'trace':trace,'jobs':{i:state[i] for i in sorted(state)},'served':served}
 """),
    "events.py": code("""
 def apply_events(jobs,state,cancel,now):
     for i,j in jobs.items():
         if state[i]['state']!='pending': continue
         if cancel.get(i)==now: state[i].update(state='cancelled',finished=now)
         elif j['deadline']<=now: state[i].update(state='expired',finished=now)
 """),
    "dependencies.py": code("""
 def propagate(jobs,state,now):
     changed=True
     while changed:
         changed=False
         for i,j in jobs.items():
             if state[i]['state']=='pending' and any(state[d]['state'] in ('cancelled','expired','blocked') for d in j['deps']):
                 state[i].update(state='blocked',finished=now); changed=True
 def ready(j,state,now): return j['release']<=now and all(state[d]['state']=='complete' for d in j['deps'])
 """),
    "fairness.py": code("""
 from functools import cmp_to_key
 def choose(options,served,weights):
     def compare(a,b):
         left=served[a['tenant']]*weights[b['tenant']]; right=served[b['tenant']]*weights[a['tenant']]
         if left!=right:return -1 if left<right else 1
         return -1 if (a['deadline'],a['id'])<(b['deadline'],b['id']) else 1
     return sorted(options,key=cmp_to_key(compare))[0] if options else None
 """),
}
reference = """
from fractions import Fraction
def solve(q):
    rows=[dict(j,remaining=j['work'],state='pending',finished=None) for j in q['jobs']]
    byid={j['id']:j for j in rows}; totals=dict.fromkeys(q['weights'],0); trace=[]
    for time in range(q['horizon']+1):
        for j in rows:
            if j['state']=='pending':
                reason='cancelled' if q['cancel'].get(j['id'])==time else 'expired' if time>=j['deadline'] else None
                if reason: j.update(state=reason,finished=time)
        for _ in rows:
            for j in rows:
                if j['state']=='pending' and any(byid[d]['state'] not in ('pending','complete') for d in j['deps']):j.update(state='blocked',finished=time)
        if time==q['horizon']:break
        available=[j for j in rows if j['state']=='pending' and j['release']<=time and all(byid[d]['state']=='complete' for d in j['deps'])]
        if not available:trace.append(None);continue
        job=min(available,key=lambda j:(Fraction(totals[j['tenant']],q['weights'][j['tenant']]),j['deadline'],j['id']))
        trace.append(job['id']); totals[job['tenant']]+=1;job['remaining']-=1
        if job['remaining']==0:job.update(state='complete',finished=time+1)
    return {'trace':trace,'served':totals,'jobs':{j['id']:{k:j[k] for k in ('state','finished','remaining')} for j in rows}}
"""


def j(id, tenant="a", work=1, release=0, deadline=20, deps=()):
    return dict(id=id, tenant=tenant, work=work, release=release, deadline=deadline, deps=list(deps))


def inp(jobs, h=6, weights=None, cancel=None):
    return dict(jobs=jobs, horizon=h, weights=weights or {"a": 1, "b": 2}, cancel=cancel or {})


inputs = [
    inp([]),
    inp([j("x")]),
    inp([j("x", work=5), j("y", "b", work=5)]),
    inp([j("x", work=4), j("y", "b", work=3, release=2)]),
    inp([j("a", work=2), j("b", "b", work=2, deps=["a"])]),
    inp([j("a", work=5), j("b", deps=["a"]), j("c", deps=["b"])], cancel={"a": 2}),
    inp([j("x", work=4, deadline=2)]),
    inp([j("x", work=2, deadline=2)]),
    inp([j("x", work=3, release=4, deadline=2)]),
    inp([j("x", deadline=2, release=3)], cancel={"x": 2}),
    inp([j("b", deadline=4), j("a", deadline=4), j("c", deadline=2)]),
    inp([j("a", work=3), j("b", work=3), j("c", "b", work=5)], weights={"a": 3, "b": 2}),
    inp([j("x", work=1), j("y", release=3), j("z", "b", work=5)]),
    inp([j("x", work=2), j("y", "b", work=3)], h=0),
    inp([j("x", work=6), j("y", "b", work=6)], h=4, cancel={"x": 4}),
    inp([j("x"), j("y", deps=["x"])], cancel={"x": 3}),
    inp(
        [
            j("root", work=2),
            j("left", "b", work=2, deps=["root"]),
            j("right", work=3, deps=["root"]),
            j("end", "b", deps=["left", "right"]),
        ],
        h=10,
    ),
    inp([j("root", work=3, deadline=1), j("child", "b", deps=["root"]), j("independent", release=3)], h=5),
]
stubs = {
    "events.py": code("""
def apply_events(jobs,state,cancel,now): pass
"""),
    "dependencies.py": code("""
def propagate(jobs,state,now): pass
def ready(j,state,now):return j['release']<=now
"""),
    "fairness.py": code("""
def choose(options,served,weights):return min(options,key=lambda j:j['id']) if options else None
"""),
}
m1 = source["fairness.py"].replace("weights[b['tenant']]", "1").replace("weights[a['tenant']]", "1")
m2 = source["events.py"].replace("if cancel.get(i)==now:", "if False:")
m3 = source["dependencies.py"].replace("all(state[d]['state']=='complete' for d in j['deps'])", "True")
author(
    "dependency-fair-dispatch",
    "bounded-implementation",
    """
Implement service.solve(q), a deterministic single-slot preemptive dispatcher. q={jobs,weights,cancel,horizon}. jobs<=10 have unique string id,tenant listed in weights,work1..10,release0..40,deadline1..60,deps list of existing IDs forming a DAG. weights maps<=4 tenants to integer1..7, cancel maps some job IDs to integer0..40, horizon0..40. Each unit tick [t,t+1) executes at most one unit. Pending includes never-started and partially completed jobs. Preserve every input.
At every integer time t from0 THROUGH horizon, first cancel pending jobs with cancel[id]==t; otherwise expire pending jobs with deadline<=t. Cancellation beats expiration on that tick; completed jobs never change. Then repeatedly mark pending jobs blocked if any dependency is cancelled, expired or blocked, reaching a fixed point at the same t. These terminal states record finished=t and retain unexecuted remaining work. If t==horizon stop before scheduling.
Ready pending jobs have release<=t and ALL dependencies complete. Select the job whose tenant has smallest cumulative servedUnits/weight, using exact rational comparison (no rounding), then smaller deadline, then lexicographic job ID. Service counts persist across idle periods, job completion and arrivals; they aggregate ALL jobs of a tenant. Re-evaluate every tick (preemptive). Increment served by1 and decrement remaining; if it reaches0 mark complete at t+1, so completing exactly at deadline is legal. After horizon unfinished pending jobs remain pending/finished=null. Return {trace:[idOrNull for exactly horizon ticks],jobs:{id:{state,finished,remaining}},served:{every declared tenant:units}}. States are pending,complete,cancelled,expired,blocked. Required work includes event ordering, transitive dependency failure, readiness, exact weighted fairness and persistent accounting; supplied helpers are intentionally incomplete.
""",
    source,
    reference,
    inputs,
    bugs=stubs,
    mutants=[{"fairness.py": m1}, {"events.py": m2}, {"dependencies.py": m3}],
    smoke="from service import solve\nassert solve({'jobs':[],'weights':{'a':1},'cancel':{},'horizon':0}) == {'trace':[],'jobs':{},'served':{'a':0}}\n",
)
