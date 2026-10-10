def finish(log, cancelled):
    output = list(log)
    try:
        if cancelled:
            return output
        output.append("completed")
        return output
    finally:
        output.append("closed")
