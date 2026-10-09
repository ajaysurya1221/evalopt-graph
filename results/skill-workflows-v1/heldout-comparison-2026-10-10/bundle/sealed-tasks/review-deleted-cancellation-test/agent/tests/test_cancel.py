from jobs import finish

def test_cancel_cleanup():
    assert finish([], True) == ["closed"]
