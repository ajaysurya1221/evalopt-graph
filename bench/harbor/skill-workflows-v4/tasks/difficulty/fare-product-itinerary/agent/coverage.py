def endpoints(trips, start, p):
    rides = 0
    previous = None
    for end in range(start, len(trips)):
        trip = trips[end]
        if trip["at"] >= trips[start]["at"] + p["duration"]:
            break
        if not bool(set(trip["zones"]) & set(p["zones"])) or trip["mode"] not in p["modes"]:
            break
        if previous is None or trip["at"] - trips[start]["at"] > p["transfer"]:
            rides += 1
        if rides > p["rides"]:
            break
        yield end + 1
        previous = trip
