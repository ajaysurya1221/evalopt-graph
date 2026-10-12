from functools import cmp_to_key


def choose(options, served, weights):
    def compare(a, b):
        left = served[a["tenant"]] * weights[b["tenant"]]
        right = served[b["tenant"]] * weights[a["tenant"]]
        if left != right:
            return -1 if left < right else 1
        return -1 if (a["deadline"], a["id"]) < (b["deadline"], b["id"]) else 1

    return sorted(options, key=cmp_to_key(compare))[0] if options else None
