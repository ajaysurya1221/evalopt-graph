def charge(price, spent, cap):
    return min(price, max(0, cap - spent))


def day(minute):
    return minute // 1440
