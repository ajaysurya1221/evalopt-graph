"""Fresh authored task definition, executed by author.py with explicit helper bindings."""

code = globals()["code"]
author = globals()["author"]

source = {
    "service.py": code("""
 from versions import latest
 from transaction import read, scan
 from conflicts import conflict
 def solve(q):
     history={k:[(0,v)] for k,v in q['initial'].items()}
     revision=0; active={}; out=[]
     for op in q['operations']:
         tag=op[0]; ident=op[1]
         if tag=='begin':
             active[ident]={'at':revision,'writes':{},'reads':set(),'ranges':[]}
             out.append(['begin',ident,revision]); continue
         t=active[ident]
         if tag=='get': out.append(['get',ident,read(history,t,op[2])])
         elif tag=='scan': out.append(['scan',ident,scan(history,t,op[2],op[3])])
         elif tag in ('put','delete'):
             t['writes'][op[2]]=op[3] if tag=='put' else None
             out.append([tag,ident])
         elif tag=='commit':
             if t['writes'] and conflict(history,t): out.append(['commit',ident,'conflict',revision])
             else:
                 if t['writes']:
                     revision+=1
                     for k,v in t['writes'].items(): history.setdefault(k,[]).append((revision,v))
                 out.append(['commit',ident,'ok',revision])
             del active[ident]
     final={k:latest(v)[1] for k,v in sorted(history.items()) if latest(v)[1] is not None}
     return {'events':out,'revision':revision,'values':final}
 """),
    "versions.py": code("""
 def latest(entries): return entries[-1]
 def view(history,key,at):
     candidates=[v for rev,v in history.get(key,[]) if rev<=at]
     return candidates[-1] if candidates else None
 """),
    "transaction.py": code("""
 from versions import view
 def read(history,t,key):
     t['reads'].add(key)
     return t['writes'][key] if key in t['writes'] else view(history,key,t['at'])
 def scan(history,t,lo,hi):
     t['ranges'].append((lo,hi))
     return [[k,read(history,t,k)] for k in sorted(set(history)|set(t['writes']))
             if lo<=k<hi and read(history,t,k) is not None]
 """),
    "conflicts.py": code("""
 def conflict(history,t):
     changed={k for k,versions in history.items() if versions[-1][0]>t['at']}
     return bool(changed & (set(t['writes'])|t['reads'])) or any(
         lo<=k<hi for k in changed for lo,hi in t['ranges'])
 """),
}
reference = """
from copy import deepcopy
def solve(q):
    state=deepcopy(q['initial']); serial=0; transactions={}; log=[]; events=[]
    for op in q['operations']:
        kind,tx,*args=op
        if kind=='begin':
            transactions[tx]=[serial,deepcopy(state),{},set(),[]]
            events.append(['begin',tx,serial]); continue
        stamp,snap,writes,reads,ranges=transactions[tx]
        overlay={**snap,**writes}
        if kind=='get':
            reads.add(args[0]); events.append(['get',tx,overlay.get(args[0])])
        elif kind=='scan':
            lo,hi=args; ranges.append((lo,hi))
            events.append(['scan',tx,[[k,overlay[k]] for k in sorted(overlay) if lo<=k<hi and overlay[k] is not None]])
        elif kind in ('put','delete'):
            writes[args[0]]=args[1] if kind=='put' else None
            events.append([kind,tx])
        else:
            touched=set().union(*(keys for rev,keys in log if rev>stamp)) if log else set()
            invalid=bool(touched & (reads|set(writes))) or any(a<=k<b for a,b in ranges for k in touched)
            if writes and invalid: events.append(['commit',tx,'conflict',serial])
            else:
                if writes:
                    serial+=1; log.append((serial,set(writes)))
                    for k,v in writes.items():
                        if v is None: state.pop(k,None)
                        else: state[k]=v
                events.append(['commit',tx,'ok',serial])
            del transactions[tx]
    return {'events':events,'revision':serial,'values':state}
"""


def inp(ops, initial=None):
    return {"initial": initial or {}, "operations": ops}


def B(t):
    return ["begin", t]


def C(t):
    return ["commit", t]


def P(t, k, v):
    return ["put", t, k, v]


def G(t, k):
    return ["get", t, k]


def D(t, k):
    return ["delete", t, k]


def S(t, a, b):
    return ["scan", t, a, b]


inputs = [
    inp([]),
    inp([B("a"), G("a", "x"), C("a")]),
    inp([B("a"), P("a", "x", 1), G("a", "x"), C("a")]),
    inp([B("a"), B("b"), P("b", "x", 2), C("b"), G("a", "x"), C("a")], {"x": 1}),
    inp([B("a"), B("b"), P("a", "x", 1), P("b", "x", 2), C("a"), C("b")]),
    inp([B("a"), S("a", "a", "z"), B("b"), P("b", "m", 9), C("b"), P("a", "q", 1), C("a")]),
    inp([B("a"), S("a", "a", "m"), B("b"), P("b", "m", 9), C("b"), P("a", "q", 1), C("a")]),
    inp([B("a"), G("a", "x"), B("b"), D("b", "x"), C("b"), P("a", "y", 1), C("a")], {"x": 5}),
    inp([B("a"), G("a", "x"), B("b"), P("b", "x", 8), C("b"), C("a")]),
    inp([B("a"), D("a", "x"), G("a", "x"), S("a", "a", "z"), P("a", "x", 7), C("a")], {"x": 4}),
    inp([B("a"), S("a", "a", "z"), B("b"), D("b", "x"), C("b"), P("a", "w", 1), C("a")], {"x": 4}),
    inp([B("a"), B("b"), D("b", "x"), C("b"), P("a", "x", 4), C("a")]),
    inp([B("a"), S("a", "m", "z"), B("b"), P("b", "m", 9), C("b"), P("a", "q", 1), C("a")]),
    inp([B("a"), P("a", "x", 1), B("b"), P("b", "y", 2), C("b"), C("a")]),
    inp([B("a"), G("a", "x"), B("b"), P("b", "x", 1), C("b"), P("a", "y", 2), C("a")], {"x": 1}),
    inp([B("a"), S("a", "b", "b"), B("b"), P("b", "b", 1), C("b"), P("a", "a", 2), C("a")]),
    inp(
        [
            B("a"),
            B("b"),
            P("b", "x", 2),
            C("b"),
            B("c"),
            D("c", "x"),
            C("c"),
            G("a", "x"),
            P("a", "y", 3),
            C("a"),
        ],
        {"x": 1},
    ),
    inp([B("a"), P("a", "b", 2), S("a", "a", "z"), D("a", "a"), S("a", "a", "c"), C("a")], {"a": 1, "z": 9}),
]
bug1 = source["versions.py"].replace("if rev<=at", "if True")
bug2 = source["conflicts.py"].replace("(set(t['writes'])|t['reads'])", "t['reads']")
bug3 = (
    source["conflicts.py"]
    .replace("lo<=k<hi", "lo<k<hi")
    .replace("for k in changed for lo,hi", "for k in changed if history[k][-1][1] is not None for lo,hi")
)
author(
    "mvcc-predicate-serialization",
    "ordinary-bug-repair",
    """
Repair service.solve(q), a deterministic optimistic serializable key/value engine. q={initial:{string:int},operations:[list]}. Keys are lowercase ASCII strings length1..4, values integers[-20,20], <=20 keys and<=60 operations; transaction IDs are strings. Operations are [begin,id], [get,id,key], [scan,id,lo,hi], [put,id,key,value], [delete,id,key], [commit,id]. IDs begin only when inactive; all other operations name active IDs; lo<=hi. Inputs meet this structural domain; no validation behavior outside it is required.
Begin captures the current revision and immutable committed snapshot. Reads see the transaction's latest local write/delete, otherwise that captured snapshot; absent/deleted returns null. scan returns sorted [key,value] pairs for lo<=key<hi, excluding absent values. Register every get key and every scan predicate even if empty. put/delete stage writes and return no value. Repeated writes replace earlier ones. On commit with ANY staged write, reject if any key read OR written, or any key in ANY scanned range, has been committed after begin. Every committed write counts, including same-value writes and deletes of absent keys; retain their conflict history. Read-only commits always succeed even after concurrent changes. Successful write commit atomically increments revision once and applies all writes; no-write success and conflicts do not increment. Commit closes the transaction. Remaining open transactions do not affect committed state.
Return {events,revision,values}. events contains [begin,id,capturedRevision], [get,id,valueOrNull], [scan,id,pairs], [put|delete,id], or [commit,id,ok|conflict,currentRevision] for every operation in order. values is final nondeleted committed mapping. Repair all interacting snapshot, write-conflict and predicate/tombstone defects; preserve arguments.
""",
    source,
    reference,
    inputs,
    bugs={"versions.py": bug1, "conflicts.py": bug2.replace("lo<=k<hi", "lo<k<hi")},
    mutants=[{"versions.py": bug1}, {"conflicts.py": bug2}, {"conflicts.py": bug3}],
    smoke="from service import solve\nassert solve({'initial':{},'operations':[]}) == {'events':[],'revision':0,'values':{}}\n",
)
