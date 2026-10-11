"""Byte-preserving, literal-LF framing for private native JSONL evidence."""

from __future__ import annotations

import hashlib
import json
import math

SCHEMA = "evalopt-workflows-v2/1"


class FramingError(ValueError):
    """Static reason and byte offset only; never include native payloads."""

    def __init__(self, reason: str, offset: int = 0):
        self.reason, self.offset = reason, offset
        super().__init__(reason)


def strict_json(raw: bytes | str):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise FramingError("duplicate_json_key")
            value[key] = item
        return value

    def constant(_):
        raise FramingError("nonfinite_json")

    def number(value):
        result = float(value)
        if not math.isfinite(result):
            raise FramingError("nonfinite_json")
        return result

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant, parse_float=number)


def _extendable_object_prefix(text: str) -> bool:
    """Recognize prefixes of strict JSON objects, not arbitrary invalid EOF text.

    This parser only classifies the tail. Decoded records still come exclusively
    from strict_json. Duplicate keys and nonfinite numbers remain invalid even
    when an enclosing object has not yet been closed.
    """

    class More(Exception):
        pass

    class Invalid(Exception):
        pass

    position, size = 0, len(text)

    def whitespace():
        nonlocal position
        while position < size and text[position] in " \t\r\n":
            position += 1

    def peek():
        whitespace()
        if position == size:
            raise More
        return text[position]

    def string():
        nonlocal position
        start = position
        position += 1
        while position < size:
            character = text[position]
            position += 1
            if character == '"':
                return json.loads(text[start:position])
            if ord(character) < 32:
                raise Invalid
            if character == "\\":
                if position == size:
                    raise More
                escaped = text[position]
                position += 1
                if escaped == "u":
                    for _ in range(4):
                        if position == size:
                            raise More
                        if text[position] not in "0123456789abcdefABCDEF":
                            raise Invalid
                        position += 1
                elif escaped not in '"\\/bfnrt':
                    raise Invalid
        raise More

    def number():
        nonlocal position
        start = position
        if text[position] == "-":
            position += 1
            if position == size:
                raise More
        if text[position] == "0":
            position += 1
        elif text[position] in "123456789":
            while position < size and text[position] in "0123456789":
                position += 1
        else:
            raise Invalid
        if position < size and text[position] == ".":
            position += 1
            if position == size:
                raise More
            if text[position] not in "0123456789":
                raise Invalid
            while position < size and text[position] in "0123456789":
                position += 1
        if position < size and text[position] in "eE":
            position += 1
            if position == size:
                raise More
            if text[position] in "+-":
                position += 1
                if position == size:
                    raise More
            if text[position] not in "0123456789":
                raise Invalid
            while position < size and text[position] in "0123456789":
                position += 1
        token = text[start:position]
        if any(character in token for character in ".eE") and not math.isfinite(float(token)):
            raise FramingError("nonfinite_json")

    def value(depth=0):
        nonlocal position
        if depth > 128:
            raise FramingError("native_json_depth_exceeded")
        character = peek()
        if character == '"':
            string()
        elif character == "{":
            position += 1
            keys = set()
            if peek() == "}":
                position += 1
                return
            while True:
                if peek() != '"':
                    raise Invalid
                key = string()
                if key in keys:
                    raise FramingError("duplicate_json_key")
                keys.add(key)
                if peek() != ":":
                    raise Invalid
                position += 1
                value(depth + 1)
                character = peek()
                position += 1
                if character == "}":
                    return
                if character != ",":
                    raise Invalid
        elif character == "[":
            position += 1
            if peek() == "]":
                position += 1
                return
            while True:
                value(depth + 1)
                character = peek()
                position += 1
                if character == "]":
                    return
                if character != ",":
                    raise Invalid
        elif character in "-0123456789":
            number()
        else:
            token = next((token for token in ("true", "false", "null") if token[0] == character), None)
            if token is None:
                raise Invalid
            remaining = text[position : position + len(token)]
            if not token.startswith(remaining):
                raise Invalid
            if len(remaining) < len(token):
                raise More
            position += len(token)

    try:
        if peek() != "{":
            return False
        value()
        whitespace()
        return False  # Either already complete or has impossible trailing text.
    except More:
        return True
    except (Invalid, ValueError, RecursionError):
        return False


def decode_jsonl(raw: bytes, *, max_bytes: int = 64 * 1024**2, max_record_bytes: int = 8 * 1024**2) -> dict:
    """Keep a syntactically incomplete EOF tail, never skip malformed complete lines.

    A valid final JSON object needs no trailing LF. A syntactically extendable final
    object prefix is retained as an opaque partial tail; none of its content is trusted.
    Invalid UTF-8, duplicate keys and nonfinite values are invalid provenance even
    at EOF. CRLF's CR is JSON whitespace; Unicode separators are not delimiters.
    """
    if (
        type(max_bytes) is not int
        or type(max_record_bytes) is not int
        or min(max_bytes, max_record_bytes) <= 0
    ):
        raise FramingError("invalid_framing_limit")
    if not isinstance(raw, bytes) or len(raw) > max_bytes:
        raise FramingError("native_log_size_or_type")
    records, offset, tail = [], 0, None
    chunks = raw.split(b"\n")
    for index, chunk in enumerate(chunks):
        final = index == len(chunks) - 1
        if not chunk and final:
            break
        if len(chunk) > max_record_bytes:
            raise FramingError("native_record_too_large", offset)
        if not chunk.strip(b" \t\r"):
            raise FramingError("empty_native_record", offset)
        try:
            value = strict_json(chunk)
        except FramingError as exc:
            raise FramingError(exc.reason, offset) from None
        except UnicodeError:
            raise FramingError("invalid_native_utf8", offset) from None
        except RecursionError:
            raise FramingError("native_json_depth_exceeded", offset) from None
        except json.JSONDecodeError:
            try:
                extendable = final and _extendable_object_prefix(chunk.decode("utf-8"))
            except FramingError as error:
                raise FramingError(error.reason, offset) from None
            if not extendable:
                raise FramingError("malformed_native_record", offset) from None
            tail = {"offset": offset, "bytes": len(chunk), "sha256": hashlib.sha256(chunk).hexdigest()}
            break
        except ValueError:
            raise FramingError("native_json_number_limit", offset) from None
        if not isinstance(value, dict):
            raise FramingError("native_record_not_object", offset)
        records.append({"offset": offset, "bytes": len(chunk), "value": value})
        offset += len(chunk) + (0 if final else 1)
    return {
        "schema_version": SCHEMA,
        "kind": "native_framing",
        "status": "partial" if tail is not None else "complete",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_bytes": len(raw),
        "records": records,
        "tail": tail,
    }
