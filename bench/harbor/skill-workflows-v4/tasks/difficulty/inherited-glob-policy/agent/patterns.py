from fnmatch import fnmatchcase


def matches(pattern, path):
    return fnmatchcase("/".join(path), pattern)
