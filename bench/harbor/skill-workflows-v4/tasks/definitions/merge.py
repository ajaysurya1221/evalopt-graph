"""Fresh authored task definition, executed by author.py with explicit helper bindings."""

code = globals()["code"]
author = globals()["author"]

source = {
    "service.py": code("""
 from presence import select
 from fields import merge_fields
 from structure import validate,ordered
 def solve(q):
     maps=[{n['id']:n for n in q[k]} for k in ('base','local','remote')]
     result={}; errors=[]
     for ident in sorted(set().union(*[set(m) for m in maps])):
         b,left,r=[m.get(ident) for m in maps]
         state,node=select(b,left,r)
         if state=='conflict': errors.append([ident,node])
         elif state=='merge':
             node,bad=merge_fields(b,left,r)
             errors.extend([[ident,f] for f in bad]); result[ident]=node
         elif state=='keep': result[ident]=dict(node)
     if not errors: errors=validate(result)
     return {'nodes':None,'conflicts':sorted(errors)} if errors else {'nodes':ordered(result),'conflicts':[]}
 """),
    "presence.py": code("""
 def select(b,left,r):
     if b is None:
         if left is not None and r is not None and left!=r: return 'conflict','add'
         return 'keep',left if left is not None else r
     if left is None or r is None:
         other=r if left is None else left
         return ('drop',None) if other is None or other==b else ('conflict','delete')
     return 'merge',None
 """),
    "fields.py": code("""
 def merge_fields(b,left,r):
     out={'id':b['id']}; errors=[]
     for f in ('parent','name','value','order'):
         if left[f]==r[f]: out[f]=left[f]
         elif left[f]==b[f]: out[f]=r[f]
         elif r[f]==b[f]: out[f]=left[f]
         else: errors.append(f); out[f]=b[f]
     return out,errors
 """),
    "structure.py": code("""
 def validate(nodes):
     errors=set()
     for ident,n in nodes.items():
         if n['parent'] is not None and n['parent'] not in nodes: errors.add((ident,'parent_missing'))
         path=[]; cur=ident
         while cur in nodes:
             if cur in path:
                 errors.update((x,'cycle') for x in path[path.index(cur):]); break
             path.append(cur); cur=nodes[cur]['parent']
     groups={}
     for ident,n in nodes.items(): groups.setdefault((n['parent'],n['name']),[]).append(ident)
     for ids in groups.values():
         if len(ids)>1: errors.update((i,'name_collision') for i in ids)
     return [list(e) for e in sorted(errors)]
 def ordered(nodes):
     out=[]
     def walk(parent):
         children=sorted((n for n in nodes.values() if n['parent']==parent),key=lambda n:(n['order'],n['id']))
         for n in children: out.append(n); walk(n['id'])
     walk(None)
     return out
 """),
}
reference = """
from copy import deepcopy
def solve(q):
    old,left_map,right=({n['id']:deepcopy(n) for n in q[k]} for k in ('base','local','remote'))
    merged={}; problems=set()
    for i in sorted(old.keys()|left_map.keys()|right.keys()):
        values=[d.get(i) for d in (old,left_map,right)]; b,left,r=values
        if b is None:
            options=[v for v in (left,r) if v is not None]
            if len(options)==2 and options[0]!=options[1]: problems.add((i,'add'))
            else: merged[i]=options[0]
        elif left is None or r is None:
            survivor=left or r
            if survivor is not None and survivor!=b: problems.add((i,'delete'))
        else:
            dl={k:left[k] for k in b if left[k]!=b[k]}; dr={k:r[k] for k in b if r[k]!=b[k]}
            problems.update((i,k) for k in dl.keys()&dr.keys() if dl[k]!=dr[k])
            merged[i]={**b,**dl,**dr}
    if not problems:
        for i,n in merged.items():
            par=n['parent']
            if par is not None and par not in merged: problems.add((i,'parent_missing'))
            seen=[]; j=i
            while j is not None and j in merged and j not in seen:
                seen.append(j); j=merged[j]['parent']
            if j in seen: problems.update((v,'cycle') for v in seen[seen.index(j):])
            for k,m in merged.items():
                if i!=k and (par,n['name'])==(m['parent'],m['name']): problems.add((i,'name_collision'))
    if problems:return {'nodes':None,'conflicts':[list(p) for p in sorted(problems)]}
    def descend(parent):
        flat=[]
        for n in sorted([x for x in merged.values() if x['parent']==parent],key=lambda x:(x['order'],x['id'])):
            flat += [n]+descend(n['id'])
        return flat
    return {'nodes':descend(None),'conflicts':[]}
"""


def n(id, parent=None, name=None, value=0, order=0):
    return dict(id=id, parent=parent, name=name or id, value=value, order=order)


def inp(b, left=None, r=None):
    return {"base": b, "local": b if left is None else left, "remote": b if r is None else r}


inputs = [
    inp([]),
    inp([n("a")]),
    inp([], [n("a")], []),
    inp([], [n("a")], [n("a")]),
    inp([], [n("a", value=1)], [n("a", value=2)]),
    inp([n("a")], [n("a", name="renamed")], [n("a", value=5)]),
    inp([n("a")], [n("a", value=1)], [n("a", value=2)]),
    inp([n("a")], [], [n("a")]),
    inp([n("a")], [], [n("a", value=2)]),
    inp([n("a"), n("b")], [n("a", "b"), n("b")], [n("a"), n("b", "a")]),
    inp([n("a")], [], [n("a"), n("b", "a")]),
    inp([], [n("a", name="x")], [n("b", name="x")]),
    inp([n("a"), n("b")], [n("a", order=2), n("b")], [n("a"), n("b", order=-1)]),
    inp([n("a"), n("b", "a"), n("c")], [n("a"), n("b", "c"), n("c")], [n("a"), n("b", "a", value=7), n("c")]),
    inp([n("a"), n("b", "a")], [], [n("a"), n("b", "a", value=1)]),
    inp([n("a")], [n("a", name="x", value=1)], [n("a", name="y", value=2)]),
    inp([], [n("b", order=0), n("a", order=0)], [n("c", order=-1), n("d", "c")]),
    inp(
        [n("a"), n("b"), n("c", "a")],
        [n("a"), n("b"), n("c", "b", order=3)],
        [n("a", value=8), n("b"), n("c", "a", name="renamed")],
    ),
]
stubs = {
    "presence.py": code("""
def select(b,left,r):
    if left is None:return 'drop',None
    return 'keep',left
"""),
    "fields.py": code("""
def merge_fields(b,left,r): return dict(left),[]
"""),
    "structure.py": source["structure.py"].replace("    errors=set()", "    return []\n    errors=set()"),
}
mut1 = source["fields.py"].replace("elif left[f]==b[f]: out[f]=r[f]", "elif left[f]==b[f]: out[f]=left[f]")
mut2 = source["presence.py"].replace("other is None or other==b", "other is None or other is not None")
mut3 = source["structure.py"].replace("errors.update((x,'cycle') for x in path[path.index(cur):])", "pass")
# Avoid recursive traversal of the invalid cyclic mutant by retaining cycle rejection and instead omit name collisions.
mut3 = source["structure.py"].replace(
    "if len(ids)>1: errors.update((i,'name_collision') for i in ids)",
    "if False: errors.update((i,'name_collision') for i in ids)",
)
author(
    "ordered-tree-three-way-merge",
    "bounded-implementation",
    """
Implement service.solve(q) three-way tree reconciliation, replacing incomplete local-only helpers. q={base,local,remote}; each value is a list<=12 of nodes {id,parent,name,value,order}. IDs/names are nonempty lowercase strings, parent null or an ID in that same input, value/order integers[-20,20]. Each input independently is an acyclic forest with unique IDs and unique sibling names; input order is irrelevant. Merge by ID, not path; do not mutate input.
For an ID absent from base: one added side wins; identical concurrent additions coalesce; different concurrent additions give [id,add]. For an ID in base: if either side deletes it, deletion wins only if the other side is absent or byte-equal (all fields) to base; otherwise [id,delete]. If both retain it, merge parent,name,value,order independently: equal side values win; a side equal to base yields to the changed side; two different changed values give [id,field]. Collect ALL such identity/field conflicts and, if any exist, skip global validation and return {nodes:null,conflicts:sortedPairs}.
Otherwise validate the combined nodes without silently repairing them: missing parent gives [child,parent_missing]; every node ON a directed parent cycle gets [id,cycle] (not descendants feeding the cycle); every member of a duplicate (parent,name) group gets [id,name_collision]. Collect all global conflicts, deduplicate and sort pairs lexicographically. If none exist, output nodes in preorder: roots and each sibling group ordered by (order,id), children immediately after parent; return {nodes:list,conflicts:[]}. Deletions can conflict with an independently added descendant through parent_missing. Moves and value/name edits commute when they affect separate fields; conflicting moves/collisions must remain explicit. No behavior is required for structurally invalid individual inputs.
""",
    source,
    reference,
    inputs,
    bugs=stubs,
    mutants=[{"fields.py": mut1}, {"presence.py": mut2}, {"structure.py": mut3}],
    smoke="from service import solve\nassert solve({'base':[],'local':[],'remote':[]}) == {'nodes':[],'conflicts':[]}\n",
)
