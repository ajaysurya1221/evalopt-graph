def solve(q):
    trips = q["trips"]
    plans = []

    def search(index, spent, cost, tickets):
        if index == len(trips):
            plans.append((cost, tuple(tickets)))
            return
        origin = trips[index]["at"]
        today = origin // 1440
        for product in q["products"]:
            count = 0
            for end in range(index, len(trips)):
                segment = trips[end]
                eligible = (
                    segment["at"] - origin < product["duration"]
                    and all(z in product["zones"] for z in segment["zones"])
                    and segment["mode"] in product["modes"]
                )
                if not eligible:
                    break
                count += int(end == index or segment["at"] - trips[end - 1]["at"] > product["transfer"])
                if count > product["rides"]:
                    break
                payment = min(product["price"], max(0, q["daily_cap"] - spent))
                nxt = end + 1
                used = spent + payment if nxt < len(trips) and trips[nxt]["at"] // 1440 == today else 0
                search(nxt, used, cost + payment, tickets + [(index, nxt, product["id"], payment)])

    search(0, 0, 0, [])
    if not plans:
        return None
    cost, tickets = min(plans)
    return {"cost": cost, "tickets": [list(t) for t in tickets]}
