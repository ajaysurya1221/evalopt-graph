class FileSystem:
    def __init__(self, initial):
        self.files = dict(initial)
        self.events = []
    def write(self, name, text):
        self.files[name] = text
        self.events.append(["write", name])
    def replace(self, source, destination):
        self.files[destination] = self.files.pop(source)
        self.events.append(["replace", source, destination])
    def remove(self, name):
        self.files.pop(name, None)
        self.events.append(["remove", name])
