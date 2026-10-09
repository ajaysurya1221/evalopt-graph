from cleanup import complete

def finish(log, cancelled):
    if cancelled:
        return list(log)
    return complete(log)
