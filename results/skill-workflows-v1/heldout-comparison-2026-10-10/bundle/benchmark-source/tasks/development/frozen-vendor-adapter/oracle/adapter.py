from vendor import reserve_legacy

def reserve(stock, requested):
    if stock < 0 or requested < 0:
        raise ValueError("negative input")
    return reserve_legacy(stock, requested)
