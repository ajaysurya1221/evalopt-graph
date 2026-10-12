"""Fresh authored task definition, executed by author.py with explicit helper bindings."""

code = globals()["code"]
author = globals()["author"]

source = {
    "service.py": code("""
 from retention import roots
 from reachability import closure
 from quarantine import collect
 def solve(q):
     live=closure(q['objects'],roots(q['snapshots'],q['keep'],q['now'],q['window']))
     dead,waiting=collect(q['objects'],live,q['quarantine'],q['now'],q['grace'])
     return {'live':sorted(live),'delete':dead,'quarantine':waiting}
 """),
    "retention.py": code("""
 def roots(snapshots,keep,now,window):
     selected={s['object'] for s in snapshots if s['pinned'] or s['created']>=now-window}
     for branch in {s['branch'] for s in snapshots}:
         ordered=sorted([s for s in snapshots if s['branch']==branch],key=lambda s:(-s['created'],s['id']))
         selected.update(s['object'] for s in ordered[:keep])
     return selected
 """),
    "reachability.py": code("""
 def closure(objects,roots):
     todo=list(roots); seen=set()
     while todo:
         ident=todo.pop()
         if ident in seen:continue
         seen.add(ident); obj=objects[ident]; todo.extend(obj['refs'])
         if obj['base'] is not None:todo.append(obj['base'])
     return seen
 """),
    "quarantine.py": code("""
 def collect(objects,live,quarantine,now,grace):
     deleted=[]; waiting={}
     for ident in sorted(objects):
         if ident in live:continue
         if ident in quarantine and now-quarantine[ident]>=grace:deleted.append(ident)
         else:waiting[ident]=quarantine.get(ident,now)
     return deleted,waiting
 """),
}
reference = """
def solve(q):
    candidates=q['snapshots']; selected=[]
    for s in candidates:
        newer=sum(1 for other in candidates if other['branch']==s['branch'] and (-other['created'],other['id'])<(-s['created'],s['id']))
        if s['pinned'] or s['created']>=q['now']-q['window'] or newer<q['keep']:selected.append(s['object'])
    live=set(selected)
    for _ in range(len(q['objects'])):
        addition=set()
        for i in live:
            obj=q['objects'][i]; addition.update(obj['refs'])
            if obj['base'] is not None:addition.add(obj['base'])
        live |= addition
    removal=[]; hold={}
    for i in q['objects']:
        if i not in live:
            old=q['quarantine'].get(i)
            if old is not None and old+q['grace']<=q['now']:removal.append(i)
            else:hold[i]=q['now'] if old is None else old
    return {'live':sorted(live),'delete':sorted(removal),'quarantine':hold}
"""


def o(base=None, refs=()):
    return {"base": base, "refs": list(refs)}


def s(id, obj, created=0, branch="main", pinned=False):
    return dict(id=id, object=obj, created=created, branch=branch, pinned=pinned)


def inp(objects, snap=(), keep=1, now=20, window=0, grace=5, quarantine=None):
    return dict(
        objects=objects,
        snapshots=list(snap),
        keep=keep,
        now=now,
        window=window,
        grace=grace,
        quarantine=quarantine or {},
    )


inputs = [
    inp({}),
    inp({"a": o()}, [s("one", "a")]),
    inp({"a": o(), "b": o("a")}, [s("one", "b")]),
    inp({"a": o()}, [], quarantine={"a": 15}),
    inp({"a": o()}, [], quarantine={"a": 16}),
    inp({"a": o()}, [], grace=0),
    inp({"a": o(), "b": o(), "c": o()}, [s("a", "a", 1), s("b", "b", 2), s("c", "c", 3)], keep=2),
    inp({"a": o(), "b": o()}, [s("z", "a", 2), s("a", "b", 2)]),
    inp({"a": o(), "b": o()}, [s("a", "a", 0, pinned=True), s("b", "b", 2)]),
    inp({"a": o(), "b": o()}, [s("a", "a", 0, "one"), s("b", "b", 0, "two")]),
    inp({"a": o(), "b": o()}, [s("a", "a", 15), s("b", "b", 14)], keep=0, window=5),
    inp({"a": o(refs=["b"]), "b": o(refs=["a"])}, [s("a", "a")]),
    inp({"a": o(), "b": o("a"), "c": o("b", refs=["d"]), "d": o()}, [s("a", "c")]),
    inp({"a": o()}, [s("a", "a")], quarantine={"a": 0}),
    inp({"a": o(), "b": o()}, [], quarantine={"a": 10, "b": 18}),
    inp({"a": o(), "b": o("a"), "c": o()}, [s("b", "b")], quarantine={"a": 0, "c": 10}),
    inp({"a": o(), "b": o()}, [s("a", "a")], keep=0, window=0),
    inp({"a": o(), "b": o("a")}, [s("b", "b", 19)], keep=0, window=2, quarantine={"a": 0}),
]
b1 = source["reachability.py"].replace(
    "if obj['base'] is not None:todo.append(obj['base'])", "if False:todo.append(obj['base'])"
)
b2 = source["quarantine.py"].replace("now-quarantine[ident]>=grace", "now-quarantine[ident]>grace")


def obligation(id, path, symbol, index):
    return dict(
        id=id,
        path=path,
        symbol=symbol,
        kinds=["incorrect-result"],
        supported_locations=[
            dict(path=path, symbol=symbol, witness_module="service", witness_function="solve"),
            dict(path="service.py", symbol="solve", witness_module="service", witness_function="solve"),
        ],
        witness_case_ids=[f"case-{index:02d}"],
    )


def finding(path, symbol, index):
    return dict(
        path=path,
        symbol=symbol,
        kind="incorrect-result",
        witness=dict(module="service", function="solve", args=[inputs[index - 1]]),
    )


review = {
    "obligations": [
        obligation("delta-base-retention", "reachability.py", "closure", 3),
        obligation("inclusive-grace-expiry", "quarantine.py", "collect", 4),
    ],
    "findings": [finding("reachability.py", "closure", 3), finding("quarantine.py", "collect", 4)],
}
review["obligations"][0]["witness_case_ids"] = ["case-03", "case-13", "case-16", "case-18"]
review["isolated_mutations"] = {
    "delta-base-retention": {"reachability.py": b1},
    "inclusive-grace-expiry": {"quarantine.py": b2},
}
author(
    "backup-reachability-collection",
    "committed-patch-review",
    """
Review the committed patch to service.solve(q), a backup retention planner. q={objects,snapshots,keep,now,window,grace,quarantine}. objects maps<=20 string IDs to {base:id|null,refs:[IDs]}; all referenced IDs exist, cycles allowed. snapshots<=12 have unique id,object existingID,branch string,created integer0..now,pinned boolean. keep0..12, now/window/grace nonnegative integers<=100 (window may exceed now). quarantine maps a subset of existing object IDs to first-unreachable time0..now. No I/O occurs.
Retention roots are the UNION of pinned snapshots, snapshots with created>=now-window, and the newest keep snapshots PER branch ordered by decreasing created then lexicographic snapshot id. Take transitive closure of BOTH refs AND base links; reachable objects stay live even if previously quarantined. For every unreachable object: if it was already quarantined and now-firstTime>=grace, delete it; otherwise retain its original firstTime or insert now if newly unreachable. Newly unreachable objects always enter quarantine once, even grace0. Reachable/deleted objects must be absent from returned quarantine. Return {live:sortedIDs,delete:sortedIDs,quarantine:mapping}. Do not alter the candidate. Identify all introduced behavioral defects with bounded witnesses. Finite-domain consequences concern delta-base retention and inclusive quarantine expiry, and helpers reachability.closure and quarantine.collect respectively; top-level service.solve is also a supported location. The whole baseline and clean control satisfy the contract on every registered request.
""",
    source,
    reference,
    inputs,
    bugs={"reachability.py": b1, "quarantine.py": b2},
    review=review,
    smoke="from service import solve\nassert solve({'objects':{},'snapshots':[],'keep':0,'now':0,'window':0,'grace':0,'quarantine':{}}) == {'live':[],'delete':[],'quarantine':{}}\n",
)
