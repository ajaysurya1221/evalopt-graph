import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v2.framing import FramingError, decode_jsonl, strict_json


class FramingTests(unittest.TestCase):
    def test_unicode_separators_are_content_and_offsets_are_bytes(self):
        first = json.dumps({"text": "a\u0085b\u2028c\u2029d"}, ensure_ascii=False).encode()
        raw = first + b'\n{"other":2}\n'
        result = decode_jsonl(raw)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(len(result["records"]), 2)
        self.assertEqual(result["records"][0]["value"]["text"], "a\u0085b\u2028c\u2029d")
        self.assertEqual(result["records"][1]["offset"], len(first) + 1)

    def test_valid_eof_and_crlf(self):
        for raw in (b'{"a":1}', b'{"a":1}\r\n'):
            with self.subTest(raw=raw):
                self.assertEqual(decode_jsonl(raw)["status"], "complete")

    def test_unterminated_tail_is_not_a_record(self):
        result = decode_jsonl(b'{"a":1}\n{"b":')
        self.assertEqual(result["status"], "partial")
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["tail"]["offset"], 8)

    def test_complete_malformed_line_is_invalid(self):
        for raw in (b'{"a":1}\n{"bad":\n', b"\n", b"[]\n", b'{"x":1}\n \n'):
            with self.subTest(raw=raw), self.assertRaises(FramingError):
                decode_jsonl(raw)

    def test_duplicate_and_nonfinite_are_invalid_even_at_eof(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}'):
            with self.subTest(raw=raw), self.assertRaises(FramingError):
                decode_jsonl(raw)

    def test_invalid_utf8_is_never_silently_partial(self):
        with self.assertRaisesRegex(FramingError, "invalid_native_utf8"):
            decode_jsonl(b'{"x":"\xff"}')

    def test_record_and_file_limits(self):
        with self.assertRaisesRegex(FramingError, "record_too_large"):
            decode_jsonl(b'{"x":123}', max_record_bytes=2)
        with self.assertRaisesRegex(FramingError, "size_or_type"):
            decode_jsonl(b"{}", max_bytes=1)

    def test_no_implicit_utf16_or_bom(self):
        for raw in ('{"x":1}'.encode("utf-16"), b'\xef\xbb\xbf{"x":1}\n'):
            with self.subTest(raw=raw), self.assertRaises((FramingError, ValueError)):
                decode_jsonl(raw)

    def test_strict_json_rejects_nested_duplicate(self):
        with self.assertRaises(FramingError):
            strict_json('{"nested":{"a":1,"a":2}}')

    def test_only_extendable_eof_prefixes_are_partial(self):
        # Cover object/array positions, literals, signs/fractions/exponents,
        # string escapes and every partial hex escape width.
        values = [
            b'{"x":null}',
            b'{"x":true}',
            b'{"x":false}',
            b'{"x":-1.25e+30}',
            b'{"x":0}',
            b'{"x":[]}',
            b'{"x":[{},true]}',
            b'{"x":"a\\n\\t\\b\\f\\r\\/\\\\\\"\\u1234"}',
            b'{"x":{"y":1},"z":2}',
        ]
        for value in values:
            for offset in range(1, len(value)):
                prefix = value[:offset]
                with self.subTest(prefix=prefix):
                    self.assertEqual(decode_jsonl(prefix)["status"], "partial")

    def test_impossible_eof_is_malformed_not_partial(self):
        for value in (
            b"not-json",
            b'{"bad":???}',
            b'{"x":truX',
            b'{"x":01',
            b'{"x":-x',
            b'{"x":1.e',
            b'{"x":1e+-',
            b'{"x":1e+z',
            b'{"x":nulx',
            b'{"x":True',
            b'{"x":"\\q',
            b'{"x":"\\u12x',
            b'{"x":"\x01',
            b'{"x":1,}',
            b'{"x":[1,]',
            b'{"x":1] ',
            b"{1:",
            b"{}garbage",
            b"[",
            b'"text',
            b' {"x": 1} {',
        ):
            with self.subTest(value=value), self.assertRaisesRegex(FramingError, "malformed_native_record"):
                decode_jsonl(value)

    def test_incomplete_envelope_cannot_hide_duplicate_or_nonfinite_value(self):
        for value in (b'{"x":1,"x":', b'{"x":1e999,', b'{"x":Infinity,'):
            with self.subTest(value=value), self.assertRaises(FramingError):
                decode_jsonl(value)


if __name__ == "__main__":
    unittest.main()
