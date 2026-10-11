import legacy


class Resolver:
    def __init__(self, snapshots):
        self.snapshots, self.memo, self.active = snapshots, {}, set()

    def read(self, name):
        if name in self.memo:
            return self.memo[name]
        if name not in self.snapshots or name in self.active:
            raise ValueError("missing or cyclic snapshot")
        self.active.add(name)
        try:
            frame = self.snapshots[name]
            text = legacy.decode(frame["legacy"])
            self.memo[name] = text
            return text
        finally:
            self.active.remove(name)
