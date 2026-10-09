from memfs import FileSystem

def save(initial, name, text, crash):
    fs = FileSystem(initial)
    temporary = name + ".tmp"
    fs.write(temporary, text)
    if crash:
        fs.remove(temporary)
    else:
        fs.replace(temporary, name)
    return {"files": fs.files, "events": fs.events, "saved": not crash}
