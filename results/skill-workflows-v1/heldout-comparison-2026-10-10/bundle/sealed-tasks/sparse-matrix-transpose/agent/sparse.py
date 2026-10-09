def transpose(rows, cols, entries):
    values = {}
    for row, col, value in entries:
        key = (col, row)
        values[key] = value
    return [cols, rows, [[col, row, value] for (col, row), value in sorted(values.items()) if value != 0]]
