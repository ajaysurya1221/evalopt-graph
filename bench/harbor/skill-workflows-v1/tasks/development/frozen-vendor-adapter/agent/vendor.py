def reserve_legacy(stock, requested):
    if requested > stock:
        raise ValueError("insufficient stock")
    return stock - max(0, requested)
