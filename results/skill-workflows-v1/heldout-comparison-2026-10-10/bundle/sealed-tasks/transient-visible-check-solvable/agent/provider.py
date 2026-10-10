class TemporaryFailure(Exception):
    pass

class FatalFailure(Exception):
    pass

class Provider:
    def __init__(self, mode):
        self.mode = mode
        self.calls = 0
    def fetch(self):
        self.calls += 1
        if self.mode == "fatal":
            raise FatalFailure("unrecoverable")
        if self.mode == "always" or (self.mode == "transient" and self.calls == 1):
            raise TemporaryFailure("retry allowed")
        return "OK"
