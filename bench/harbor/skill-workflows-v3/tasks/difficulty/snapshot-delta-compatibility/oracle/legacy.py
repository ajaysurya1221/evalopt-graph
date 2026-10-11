def encode(text):
    return "L1|" + str(len(text)) + "|" + text


def decode(encoded):
    fields = encoded.split("|", 2)
    if (
        len(fields) != 3
        or fields[0] != "L1"
        or not fields[1].isdigit()
        or str(int(fields[1])) != fields[1]
        or len(fields[2]) != int(fields[1])
    ):
        raise ValueError("invalid legacy frame")
    return fields[2]
