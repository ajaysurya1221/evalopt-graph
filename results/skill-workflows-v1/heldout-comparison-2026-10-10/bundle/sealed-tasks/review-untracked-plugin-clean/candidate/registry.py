from plugin import apply

def transform(values):
    return [apply(value) for value in values]
