def page(items, offset, limit):
    return [items[index] for index in range(offset, min(len(items), offset + limit))]
