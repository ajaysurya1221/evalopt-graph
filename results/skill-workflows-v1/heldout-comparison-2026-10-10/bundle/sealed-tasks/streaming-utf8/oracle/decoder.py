import codecs

def decode_chunks(chunks):
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    try:
        result = "".join(decoder.decode(bytes.fromhex(chunk), final=False) for chunk in chunks)
        return result + decoder.decode(b"", final=True)
    except UnicodeDecodeError as exc:
        raise ValueError("invalid UTF-8") from exc
