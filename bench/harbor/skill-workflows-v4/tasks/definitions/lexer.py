"""Fresh authored task definition, executed by author.py with explicit helper bindings."""

code = globals()["code"]
author = globals()["author"]

source = {
    "service.py": code("""
 from api import feed
 def solve(q):
     state={'buffer':[],'offset':0}; batches=[]
     for i,chunk in enumerate(q['chunks']):
         state,tokens=feed(state,chunk,q['finish'] and i==len(q['chunks'])-1)
         batches.append(tokens)
     return {'batches':batches,'state':state}
 """),
    "api.py": code("""
 from lexer import scan
 def feed(state,chunk,final):
     data=bytes(state['buffer']+chunk)
     tokens,consumed=scan(data,final,state['offset'])
     return {'buffer':list(data[consumed:]),'offset':state['offset']+consumed},tokens
 """),
    "utf8.py": code("""
 def prefix(data,final):
     try:return data.decode('utf-8')
     except UnicodeDecodeError as exc:
         if not final and exc.reason=='unexpected end of data' and exc.end==len(data):return data[:exc.start].decode('utf-8')
         raise ValueError('invalid UTF-8') from None
 """),
    "lexer.py": code("""
 from utf8 import prefix
 def scan(data,final,base):
     text=prefix(data,final); byte=[0]
     for c in text:byte.append(byte[-1]+len(c.encode('utf-8')))
     out=[]; i=0; committed=0
     while i<len(text):
         if text[i] in ' \\t\\r\\n':i+=1;committed=byte[i];continue
         if text[i]=='#':
             end=text.find('\\n',i)
             if end<0:
                 if final:committed=len(data)
                 break
             i=end+1;committed=byte[i];continue
         start=i; value=[]; quoted=False; escape=False
         while i<len(text):
             c=text[i]
             if escape:value.append(c);escape=False;i+=1;continue
             if c=='\\\\':escape=True;i+=1;continue
             if c=='"':quoted=not quoted;i+=1;continue
             if not quoted and (c in ' \\t\\r\\n' or c=='#'):break
             value.append(c);i+=1
         if i==len(text) and not final:break
         if quoted or escape:raise ValueError('unfinished token')
         out.append({'text':''.join(value),'start':base+byte[start],'end':base+byte[i]})
         committed=byte[i]
     return out,committed
 """),
}
reference = r"""
import re,codecs
TOKEN=re.compile(r'(?:\\[\s\S]|"(?:\\[\s\S]|[^"\\])*"|[^\s#"\\])+')
def parse(data,final,base):
    decoder=codecs.getincrementaldecoder('utf-8')()
    try:text=decoder.decode(data,final=final)
    except UnicodeDecodeError:raise ValueError('invalid UTF-8') from None
    pos=0; consumed=0; records=[]
    while pos<len(text):
        c=text[pos]
        if c in ' \t\r\n':pos+=1;consumed=len(text[:pos].encode());continue
        if c=='#':
            nextline=text.find('\n',pos)
            if nextline<0:
                if final:consumed=len(data)
                break
            pos=nextline+1;consumed=len(text[:pos].encode());continue
        match=TOKEN.match(text,pos)
        if match is None or (match.end()<len(text) and text[match.end()] not in ' \t\r\n#'):
            if final:raise ValueError('unfinished token')
            break
        end=match.end()
        if end==len(text) and not final:break
        syntax=match.group(); chars=[]; cursor=0
        while cursor<len(syntax):
            if syntax[cursor]=='\\':cursor+=1;chars.append(syntax[cursor])
            elif syntax[cursor]!='"':chars.append(syntax[cursor])
            cursor+=1
        records.append({'text':''.join(chars),'start':base+len(text[:pos].encode()),'end':base+len(text[:end].encode())})
        pos=end;consumed=len(text[:pos].encode())
    return records,consumed
def solve(q):
    carry=b''; offset=0; batches=[]
    for i,part in enumerate(q['chunks']):
        raw=carry+bytes(part); rows,used=parse(raw,q['finish'] and i==len(q['chunks'])-1,offset)
        batches.append(rows);offset+=used;carry=raw[used:]
    return {'batches':batches,'state':{'buffer':list(carry),'offset':offset}}
"""


def inp(parts, finish=True):
    return {"chunks": [list(p.encode("utf-8")) if isinstance(p, str) else p for p in parts], "finish": finish}


inputs = [
    inp([""]),
    inp(["a b"]),
    inp(["al", "pha ", "be", "ta"]),
    inp(['"a b" c']),
    inp(['"" ', 'a"b c"d']),
    inp(["a\\", " b "]),
    inp(["a#note\nb"]),
    inp(["#no", "te\n", "x"]),
    inp([[0xC3], [0xA9, 32], list("雪".encode())]),
    inp(['"é', '\\"z', '" ']),
    inp(["partial"], False),
    inp(['"unterminated'], False),
    inp(['"unterminated']),
    inp(["x\\"]),
    inp([[0xC3]], True),
    inp([[0xFF]], True),
    inp(["one\r\n", "two\\\nthree ", "#final"]),
    inp(["é", " ", [0xE9, 0x9B], [0xAA, 32], "end"], False),
]
b1 = source["utf8.py"].replace(
    "data[:exc.start].decode('utf-8')", "data.decode('utf-8',errors='ignore')"
)  # same on incomplete; use replacement corruption
b1 = source["utf8.py"].replace("data.decode('utf-8')", "data.decode('utf-8',errors='replace')", 1)
b2 = source["lexer.py"].replace("len(c.encode('utf-8'))", "1").replace("for c in text:", "for _c in text:")
b3 = source["lexer.py"].replace(
    "if i==len(text) and not final:break",
    "if i==len(text) and not final and not quoted and not escape:pass\n        elif i==len(text) and not final:break",
)
author(
    "chunked-escaped-tokenizer",
    "constraint-preservation",
    """
Repair the incremental tokenizer behind service.solve(q), preserving frozen service.py and api.py exactly. q={chunks:[byteLists],finish:boolean};1..12 chunks, each0..64 bytes, total<=256. Byte values0..255. feed's frozen state is {buffer:[unconsumed bytes],offset:number of committed prefix bytes}; no state keys or public return fields may change. Return {batches:[tokens emitted by each feed],state:finalState}. UTF-8 is strict: incomplete final sequence or any invalid sequence raises ValueError; an incomplete terminal sequence in a nonfinal chunk is buffered. Offsets count bytes, not Unicode characters.
Outside double quotes, ASCII space/tab/CR/LF separate tokens and # begins a comment through newline. A comment can immediately follow a token. Double quotes concatenate quoted/unquoted components, and are omitted from decoded text; an empty quoted component is still a token. Backslash escapes the next Unicode character literally in/outside quotes, including newline or # or quote; slash itself is omitted. Within quotes whitespace/# are literal. Each token is {text,start,end}, zero-based global byte interval INCLUDING syntactic quotes/backslashes and excluding separating whitespace/comment. An unterminated quote or trailing escape at final input raises ValueError. Other Unicode whitespace is not in the authored input domain; normal Unicode letters are allowed.
On nonfinal feed, emit only tokens already followed by a separator or #; even a closed quoted token at physical chunk end remains buffered until a following delimiter or final feed. Commit complete whitespace and complete newline-terminated comments; an unfinished nonfinal comment stays buffered starting at#. Token fragments stay buffered starting at their first syntax byte; previously committed offset must be retained exactly. Final feed flushes a complete token and discards final comment; unfinished syntax errors as above. Only final chunk gets final=True when finish=True; finish=False intentionally leaves incomplete state. Correctness includes per-chunk emission timing, escape carry, invalid-byte categories and byte offsets, not only concatenated tokens.
""",
    source,
    reference,
    inputs,
    bugs={
        "utf8.py": b1,
        "lexer.py": b2.replace(
            "if i==len(text) and not final:break",
            "if i==len(text) and not final and (quoted or escape):break",
        ),
    },
    mutants=[{"utf8.py": b1}, {"lexer.py": b2}, {"lexer.py": b3}],
    frozen=("service.py", "api.py"),
    smoke="from service import solve\nassert solve({'chunks':[[]],'finish':True}) == {'batches':[[]],'state':{'buffer':[],'offset':0}}\n",
)
