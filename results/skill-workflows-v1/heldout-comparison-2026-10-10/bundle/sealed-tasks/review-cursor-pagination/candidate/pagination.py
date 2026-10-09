def page(rows, cursor, limit):
    return [row[:] for row in sorted(rows, key=lambda row: (row[0], row[1])) if cursor is None or row[0] > cursor[0]][:limit]
