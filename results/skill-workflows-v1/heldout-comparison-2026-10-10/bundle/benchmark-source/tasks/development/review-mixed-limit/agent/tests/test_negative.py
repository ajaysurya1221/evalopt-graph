from cli import read_limit

def test_reject_negative():
    try:
        read_limit("-2")
    except ValueError:
        return
    raise AssertionError("negative accepted")
