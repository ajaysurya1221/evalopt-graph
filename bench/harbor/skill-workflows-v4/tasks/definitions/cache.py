"""Fresh authored task definition, executed by author.py with explicit helper bindings."""

code = globals()["code"]
author = globals()["author"]

source = {
    "service.py": code("""
 from selection import select
 from revalidation import merge
 from variants import matches
 def solve(q):
     entry=select(q['entries'],q['request'])
     if entry is None:return {'state':'miss'}
     age=q['now']-entry['stored_at']
     if age<entry['max_age']:return {'state':'hit','id':entry['id'],'body':entry['body'],'headers':dict(entry['headers']),'age':age}
     update=q['not_modified']
     if update is None:return {'state':'stale','id':entry['id'],'etag':entry['headers'].get('etag')}
     headers=merge(entry['headers'],update['headers'])
     changed={**entry,'headers':headers}
     if not matches(changed,q['request']):return {'state':'miss'}
     return {'state':'revalidated','id':entry['id'],'body':entry['body'],'headers':headers,'age':0}
 """),
    "variants.py": code("""
 def matches(entry,request):
     if entry['url']!=request['url']:return False
     old=entry['request_headers']; new=request['headers']
     if old.get('authorization')!=new.get('authorization'):return False
     vary=entry['headers'].get('vary',[])
     return '*' not in vary and all(old.get(k)==new.get(k) for k in vary)
 """),
    "selection.py": code("""
 from variants import matches
 def select(entries,request):
     valid=[e for e in entries if matches(e,request)]
     return min(valid,key=lambda e:(-e['stored_at'],e['id'])) if valid else None
 """),
    "revalidation.py": code("""
 def merge(old,new):
     headers={**old,**new}
     if 'warning' not in new:headers.pop('warning',None)
     return headers
 """),
}
reference = """
from copy import deepcopy
def solve(q):
    req=q['request']; eligible=[]
    def valid(e,headers):
        if e['url']!=req['url']:return False
        a=e['request_headers']; b=req['headers']
        keys=set(headers.get('vary',[]))|{'authorization'}
        if '*' in keys:return False
        return not any(a.get(k)!=b.get(k) for k in keys)
    for e in q['entries']:
        if valid(e,e['headers']):eligible.append(e)
    if not eligible:return {'state':'miss'}
    e=sorted(eligible,key=lambda e:(-e['stored_at'],e['id']))[0]
    age=q['now']-e['stored_at']
    if age<e['max_age']:return dict(state='hit',id=e['id'],body=e['body'],headers=deepcopy(e['headers']),age=age)
    n=q['not_modified']
    if n is None:return {'state':'stale','id':e['id'],'etag':e['headers'].get('etag')}
    h=deepcopy(e['headers'])
    h.pop('warning',None)
    for k,v in n['headers'].items():h[k]=deepcopy(v)
    if not valid(e,h):return {'state':'miss'}
    return dict(state='revalidated',id=e['id'],body=e['body'],headers=h,age=0)
"""


def e(id="a", url="/x", request=None, headers=None, at=0, age=10, body="payload"):
    return dict(
        id=id,
        url=url,
        request_headers=request or {},
        headers=headers or {},
        stored_at=at,
        max_age=age,
        body=body,
    )


def inp(entries, request=None, now=5, update=None, url="/x"):
    return dict(entries=entries, request=dict(url=url, headers=request or {}), now=now, not_modified=update)


inputs = [
    inp([]),
    inp([e()]),
    inp(
        [e(request={"lang": "en", "encoding": "gzip"}, headers={"vary": ["lang", "encoding"]})],
        {"lang": "en", "encoding": "br"},
    ),
    inp([e(request={"lang": "en"}, headers={"vary": ["lang"]})], {"lang": "en"}),
    inp(
        [e(headers={"etag": "v1", "content-type": "text", "warning": "old"}, age=0)],
        update={"headers": {"etag": "v2"}},
    ),
    inp([e(headers={"vary": ["*"]})]),
    inp([e(request={"authorization": "secret-a"})], {"authorization": "secret-b"}),
    inp([e(request={"authorization": "a"})]),
    inp([e()], {"authorization": "a"}),
    inp([e(headers={"etag": "v1"})], now=10),
    inp([e("z", at=2), e("a", at=2), e("new", at=3)], now=5),
    inp([e(url="/other")]),
    inp(
        [e(request={"lang": "en"}, headers={"etag": "v1"}, age=0)],
        {"lang": "fr"},
        update={"headers": {"vary": ["lang"]}},
    ),
    inp([e(headers={"warning": "old", "etag": "v1"}, age=0)], update={"headers": {"warning": "new"}}),
    inp([e(headers={"vary": ["lang"]}, request={}, age=0)], {}, update={"headers": {}}),
    inp(
        [
            e("wrong", request={"lang": "fr"}, headers={"vary": ["lang"]}, at=4),
            e("right", request={"lang": "en"}, headers={"vary": ["lang"]}, at=1),
        ],
        {"lang": "en"},
    ),
    inp([e(headers={"etag": "v1"})], update={"headers": {"etag": "should-ignore"}}),
    inp(
        [e(request={"authorization": "x", "lang": "en"}, headers={"vary": ["lang"], "etag": "v1"}, age=0)],
        {"authorization": "x", "lang": "en"},
        update={"headers": {"content-type": "json", "vary": []}},
    ),
]
b1 = source["variants.py"].replace(
    "all(old.get(k)==new.get(k) for k in vary)", "(not vary or any(old.get(k)==new.get(k) for k in vary))"
)
b2 = source["revalidation.py"].replace("headers={**old,**new}", "headers=dict(new)")
b3 = b1.replace("if old.get('authorization')!=new.get('authorization'):return False", "if False:return False")


def obl(id, path, symbol, index):
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


def find(path, symbol, index):
    return dict(
        path=path,
        symbol=symbol,
        kind="incorrect-result",
        witness=dict(module="service", function="solve", args=[inputs[index - 1]]),
    )


review = dict(
    obligations=[
        obl("all-vary-fields", "variants.py", "matches", 3),
        obl("revalidation-preserves-metadata", "revalidation.py", "merge", 5),
        obl("authorization-isolation", "variants.py", "matches", 7),
    ],
    findings=[
        find("variants.py", "matches", 3),
        find("revalidation.py", "merge", 5),
        find("variants.py", "matches", 7),
    ],
    layers=[{"variants.py": b1}, {"variants.py": b1, "revalidation.py": b2}],
)
review["obligations"][1]["witness_case_ids"] = ["case-05", "case-14", "case-15", "case-18"]
review["obligations"][2]["witness_case_ids"] = ["case-07", "case-08", "case-09"]
review["isolated_mutations"] = {
    "all-vary-fields": {"variants.py": b1},
    "revalidation-preserves-metadata": {"revalidation.py": b2},
    "authorization-isolation": {
        "variants.py": source["variants.py"].replace(
            "if old.get('authorization')!=new.get('authorization'):return False", "if False:return False"
        )
    },
}
author(
    "http-variant-revalidation",
    "mixed-workspace-review",
    """
Review ALL committed, staged and unstaged changes relative to benchmark-base for service.solve(q). This is a bounded structured HTTP-cache model, not an unstated RFC exercise. q={entries,request,now,not_modified}. entries<=10 have unique id,url,request_headers (lowercase header names to strings), headers (lowercase names to strings except vary:list of lowercase names or '*'), stored_at0..now,max_age>=0,body:string. request={url,headers:string mapping}; now integer0..100. not_modified is null or {headers:new response-header mapping}. URLs/strings are exact literal comparisons; absent request-header differs from present empty string.
An entry matches iff URL matches, stored/request authorization values are equal INCLUDING absence, vary contains no '*', and EVERY listed vary header has equal stored/current request value. Duplicate vary fields are neutral; empty vary permits any nonauthorization headers. Select newest matching stored_at, breaking ties by lexicographic id. If none return {state:miss}. If age=now-stored_at<max_age return {state:hit,id,body,headers,age}, ignoring not_modified. Otherwise if no update return {state:stale,id,etag:headerOrNull}. With update, merge headers by replacing supplied keys while retaining other old keys; drop old warning unless update supplies warning. Re-check variant matching against merged vary and the ORIGINAL stored request; if mismatched return miss. Otherwise return {state:revalidated,id,body,headers:merged,age:0}; body never replaced by a304. Inputs remain unchanged.
Required introduced-defect coverage: all-field Vary matching (variants.matches), preservation of unmodified revalidation metadata (revalidation.merge), and authorization isolation (variants.matches). service.solve is also a supported location. Review the final combined workspace while inspecting all layers; do not make repairs.
""",
    source,
    reference,
    inputs,
    bugs={"variants.py": b3, "revalidation.py": b2},
    review=review,
    smoke="from service import solve\nassert solve({'entries':[],'request':{'url':'/','headers':{}},'now':0,'not_modified':None}) == {'state':'miss'}\n",
)
