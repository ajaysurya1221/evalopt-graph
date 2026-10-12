"""Fresh authored task definition, executed by author.py with explicit helper bindings."""

code = globals()["code"]
author = globals()["author"]

source = {
    "service.py": code("""
 from planner import best
 def solve(q): return best(q['trips'],q['products'],q['daily_cap'])
 """),
    "coverage.py": code("""
 def endpoints(trips,start,p):
     rides=0; previous=None
     for end in range(start,len(trips)):
         trip=trips[end]
         if trip['at']>=trips[start]['at']+p['duration']: break
         if not set(trip['zones']).issubset(p['zones']) or trip['mode'] not in p['modes']: break
         if previous is None or trip['at']-previous['at']>p['transfer']: rides+=1
         if rides>p['rides']: break
         yield end+1
         previous=trip
 """),
    "pricing.py": code("""
 def charge(price,spent,cap): return min(price,max(0,cap-spent))
 def day(minute): return minute//1440
 """),
    "planner.py": code("""
 from functools import lru_cache
 from coverage import endpoints
 from pricing import charge,day
 def best(trips,products,cap):
     @lru_cache(None)
     def visit(i,spent):
         if i==len(trips): return (0,())
         choices=[]
         for p in products:
             paid=charge(p['price'],spent,cap)
             for end in endpoints(trips,i,p):
                 next_spent=spent+paid if end<len(trips) and day(trips[end]['at'])==day(trips[i]['at']) else 0
                 tail=visit(end,next_spent)
                 if tail is not None: choices.append((paid+tail[0],((i,end,p['id'],paid),)+tail[1]))
         return min(choices) if choices else None
     answer=visit(0,0)
     return None if answer is None else {'cost':answer[0],'tickets':[list(t) for t in answer[1]]}
 """),
}
reference = """
def solve(q):
    trips=q['trips']; plans=[]
    def search(index,spent,cost,tickets):
        if index==len(trips): plans.append((cost,tuple(tickets))); return
        origin=trips[index]['at']; today=origin//1440
        for product in q['products']:
            count=0
            for end in range(index,len(trips)):
                segment=trips[end]
                eligible=(segment['at']-origin<product['duration'] and all(z in product['zones'] for z in segment['zones']) and segment['mode'] in product['modes'])
                if not eligible: break
                count+=int(end==index or segment['at']-trips[end-1]['at']>product['transfer'])
                if count>product['rides']: break
                payment=min(product['price'],max(0,q['daily_cap']-spent))
                nxt=end+1
                used=spent+payment if nxt<len(trips) and trips[nxt]['at']//1440==today else 0
                search(nxt,used,cost+payment,tickets+[(index,nxt,product['id'],payment)])
    search(0,0,0,[])
    if not plans: return None
    cost,tickets=min(plans)
    return {'cost':cost,'tickets':[list(t) for t in tickets]}
"""


def t(at, z=("a",), mode="bus"):
    return {"at": at, "zones": list(z), "mode": mode}


def p(id, price=5, duration=100, rides=1, transfer=0, z=("a", "b"), m=("bus", "rail")):
    return dict(
        id=id, price=price, duration=duration, rides=rides, transfer=transfer, zones=list(z), modes=list(m)
    )


def inp(trips, products, cap=99):
    return dict(trips=trips, products=products, daily_cap=cap)


inputs = [
    inp([], []),
    inp([t(0)], [p("one")]),
    inp([t(0), t(20)], [p("one"), p("pass", 7, rides=2)]),
    inp([t(0, ("a", "b"))], [p("cheap", 1, z=("a",)), p("wide", 8)]),
    inp([t(0), t(8), t(16)], [p("chain", 4, transfer=10), p("single", 2)]),
    inp([t(0), t(10), t(20)], [p("chain", 4, transfer=10)]),
    inp([t(0), t(11)], [p("chain", 4, transfer=10)]),
    inp([t(0), t(100)], [p("long", 4, duration=100, rides=3)]),
    inp([t(0), t(10), t(20)], [p("one", 5, duration=1)], cap=8),
    inp([t(1439), t(1441)], [p("single", 5, duration=1), p("cross", 8, duration=5, rides=2)], cap=5),
    inp([t(0, mode="rail")], [p("bus", 1, m=("bus",))]),
    inp(
        [t(0), t(5), t(11), t(30)], [p("short", 3, duration=10, rides=4), p("long", 8, duration=50, rides=4)]
    ),
    inp([t(0), t(5)], [p("b", 5, rides=2), p("a", 5, rides=2)]),
    inp([t(0), t(10), t(30)], [p("x", 2, transfer=10, rides=1), p("y", 5, rides=3)], cap=3),
    inp([t(1400), t(1440), t(1450)], [p("cross", 7, duration=80, rides=3), p("s", 4, duration=1)], cap=6),
    inp([t(0, ("a",)), t(2, ("b",)), t(3, ("a",))], [p("a", 2, z=("a",), rides=4), p("wide", 5, rides=3)]),
    inp([t(0), t(0), t(2)], [p("zero", 0, rides=1, transfer=0)], cap=0),
    inp(
        [t(0), t(7, mode="rail"), t(16), t(23), t(50)],
        [p("mix", 6, duration=40, rides=2, transfer=8), p("single", 4, duration=1)],
        cap=11,
    ),
]
b1 = source["coverage.py"].replace(
    "set(trip['zones']).issubset(p['zones'])", "bool(set(trip['zones']) & set(p['zones']))"
)
b2 = source["coverage.py"].replace("trip['at']-previous['at']", "trip['at']-trips[start]['at']")
b3 = source["pricing.py"].replace("min(price,max(0,cap-spent))", "price")
author(
    "fare-product-itinerary",
    "ordinary-bug-repair",
    """
Repair service.solve(q), an exact fare planner. q={trips,products,daily_cap}. trips is an ordered list (<=8) of {at:nonnegative integer minute,zones:nonempty list of zone strings,mode:string}; times are nondecreasing. products (<=4) have unique string id,price>=0,duration>=1,rides>=1,transfer>=0,zones:list,modes:list. All numbers <=5000. Cap is nonnegative integer. No validation outside this domain is required.
Partition ALL trips into contiguous nonempty ticket segments. A product purchased at segment index i covers segment [i,end) iff every trip's mode and ALL its zones are allowed, every trip starts strictly before trips[i].at+duration, and consumed boarding groups<=rides. First trip consumes one group. Each subsequent trip consumes one only when its time minus the immediately preceding trip's time is GREATER than transfer; chains of eligible transfers can extend beyond the first transfer window, but never duration. Every covered trip must be eligible, including transfers. A ticket may stop at ANY eligible endpoint; later purchases start exactly at first uncovered trip. Products are reusable without limit.
A ticket is charged on its first trip's UTC day (at//1440): payment=min(price,max(0,daily_cap-alreadyPaidThatDay)). Coverage may cross midnight; it does not consume the following day's cap. Return null if no full cover, else {cost,tickets} with minimal total payment and tickets=[[start,endExclusive,productID,payment],...]. Among equal costs choose lexicographically smallest complete ticket tuple sequence (compare start,end,ID,payment in that order, ordinary Python integer/string ordering). Empty itinerary returns cost0/tickets[]. Return actual capped payments, not nominal prices. Repair eligibility, transfer-chain and cap interaction defects; all arguments remain unchanged.
""",
    source,
    reference,
    inputs,
    bugs={
        "coverage.py": b1.replace("trip['at']-previous['at']", "trip['at']-trips[start]['at']"),
        "pricing.py": b3,
    },
    mutants=[{"coverage.py": b1}, {"coverage.py": b2}, {"pricing.py": b3}],
    smoke="from service import solve\nassert solve({'trips':[],'products':[],'daily_cap':0}) == {'cost':0,'tickets':[]}\n",
)
