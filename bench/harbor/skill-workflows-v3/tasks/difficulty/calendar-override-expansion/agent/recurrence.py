def nominal_times(start, step, count):
    return [(i, start + i * step) for i in range(count)]
