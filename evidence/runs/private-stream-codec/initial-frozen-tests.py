"""Literal private-WS transport requirements; no SQL, auth store or listener."""
import base64
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import struct
import unittest

from uta.private_stream_codec import (BufferFull, EncodeReject, FrameParser,
    FrameReject, HandshakeReject, OutboundBuffer, PingTracker, encode_close,
    encode_control, encode_text, encode_text_chunks, validate_handshake_key)


ROOT = Path(__file__).resolve().parents[1]
V1 = json.loads((ROOT / "tests/fixtures/managed_private_stream_v1_contract.json").read_text())
V2 = json.loads((ROOT / "tests/fixtures/managed_private_stream_v2_contract.json").read_text())
CASES = {row["id"]: row for row in [*V1["cases"], *V2["cases"]]}


def client_frame(opcode, payload=b"", *, final=True):
    """Independent tiny literal construction, never the production encoder."""
    mask = b"\x01\x02\x03\x04"
    n = len(payload)
    first = (0x80 if final else 0) | opcode
    length = bytes([0x80 | n]) if n <= 125 else b"\xfe" + struct.pack("!H", n)
    return bytes([first]) + length + mask + bytes(v ^ mask[i % 4] for i, v in enumerate(payload))


class HandshakeKeyTests(unittest.TestCase):
    def test_rfc_canonical_key_accept_and_signed_hex_binding(self):
        key = validate_handshake_key("dGhlIHNhbXBsZSBub25jZQ==", "7468652073616d706c65206e6f6e6365")
        self.assertEqual(key.accept, "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=")
        self.assertEqual(key.canonical_key, "dGhlIHNhbXBsZSBub25jZQ==")
        with self.assertRaises(FrozenInstanceError):
            key.accept = "wrong"

    def test_nonzero_pad_bit_alias_is_rejected_despite_equal_decoded_bytes(self):
        good, alias = "dGhlIHNhbXBsZSBub25jZQ==", "dGhlIHNhbXBsZSBub25jZR=="
        self.assertEqual(base64.b64decode(good, validate=True), base64.b64decode(alias, validate=True))
        with self.assertRaises(HandshakeReject) as caught:
            validate_handshake_key(alias, "7468652073616d706c65206e6f6e6365")
        self.assertEqual((caught.exception.http_status, caught.exception.code), (400, "invalid_ws_key"))
        self.assertFalse(hasattr(caught.exception, "close_code"))
        self.assertNotIn(alias, str(caught.exception))

    def test_whitespace_wrong_length_and_challenge_do_not_normalize(self):
        for key in (None, " dGhlIHNhbXBsZSBub25jZQ==", "dGhlIHNhbXBsZSBub25jZQ==\n", "AAAA", "A" * 24):
            with self.subTest(key_type=type(key).__name__), self.assertRaises(HandshakeReject):
                validate_handshake_key(key, "7468652073616d706c65206e6f6e6365")
        for challenge in ("0" * 32, "7468652073616D706C65206E6F6E6365", "short", True):
            with self.subTest(challenge_type=type(challenge).__name__), self.assertRaises(HandshakeReject):
                validate_handshake_key("dGhlIHNhbXBsZSBub25jZQ==", challenge)


class IncrementalFrameTests(unittest.TestCase):
    def test_original_control_vectors_and_upgrade_errors(self):
        for i, field in ((14, "client_ping_hex"), (15, "client_close_hex"), (23, "client_unsolicited_empty_pong_hex")):
            row = CASES[f"WS-C{i:03d}"]
            frame = bytes.fromhex(row["input"][field])
            parser = FrameParser()
            batch = parser.feed(frame, now_ms=0)
            self.assertEqual(batch.consumed, len(frame))
            self.assertEqual(len(batch.events), 1)
            self.assertLessEqual(parser.maximum_buffered_bytes, 139)
        bad = [("WS-C016", "client_unmasked_ping_hex"), ("WS-C017", "client_fragmented_control_hex"),
               ("WS-C018", "client_valid_fragmented_text_start_hex"), ("WS-C019", "client_unexpected_continuation_hex"),
               ("WS-C020", "client_nonminimal_empty_text_length_hex"), ("WS-C021", "client_close_invalid_utf8_hex"),
               ("WS-C022", "client_close_reserved1005_hex"), ("WS-V2-C037", "client_frame_hex"),
               ("WS-V2-C040", "client_frame_hex"), ("WS-V2-C041", "client_header_hex"), ("WS-V2-C042", "client_header_hex")]
        for identity, field in bad:
            row = CASES[identity]
            parser = FrameParser()
            with self.subTest(case=identity), self.assertRaises(FrameReject) as caught:
                parser.feed(bytes.fromhex(row["input"][field]), now_ms=0)
            self.assertEqual(caught.exception.close_code, row["expected"]["close_code"])
            self.assertFalse(hasattr(caught.exception, "http_status"))
            self.assertTrue(parser.closed)
            self.assertLessEqual(parser.maximum_buffered_bytes, 139)

    def test_byte_at_a_time_utf8_close_and_mask_offset(self):
        raw = client_frame(8, struct.pack("!H", 1000) + "€".encode())
        parser, events = FrameParser(), []
        for i, byte in enumerate(raw):
            batch = parser.feed(bytes([byte]), now_ms=i)
            self.assertEqual(batch.consumed, 1)
            events.extend(batch.events)
        self.assertEqual([(e.kind, e.close_code, e.reason) for e in events], [("close", 1000, "€")])
        self.assertNotIn("€", repr(events[0]))
        self.assertEqual(events[0].reply_close_code, 1000)

    def test_split_input_all_cut_points_and_two_frames(self):
        raw = client_frame(9, b"abcde") + client_frame(10, b"x")
        for split in range(len(raw) + 1):
            parser = FrameParser()
            first = parser.feed(raw[:split], now_ms=0)
            second = parser.feed(raw[split:], now_ms=1)
            events = (*first.events, *second.events)
            self.assertEqual([(e.kind, e.payload) for e in events], [("ping", b"abcde"), ("pong", b"x")])

    def test_control_turn_budget_leaves_unconsumed_input_with_caller(self):
        one = client_frame(9)
        parser = FrameParser()
        raw = one * 10000
        first = parser.feed(raw, now_ms=0)
        self.assertEqual((len(first.events), first.consumed), (8, 8 * len(one)))
        self.assertEqual(parser.buffered_bytes, 0)
        self.assertLessEqual(parser.maximum_buffered_bytes, 139)

    def test_protocol_header_rules_precede_no_client_data_policy(self):
        for raw in (b"\xc1\x80\x01\x02\x03\x04", b"\x83\x80\x01\x02\x03\x04", b"\x81\x00"):
            with self.subTest(raw=raw.hex()), self.assertRaises(FrameReject) as caught:
                FrameParser().feed(raw, now_ms=0)
            self.assertEqual(caught.exception.close_code, 1002)
        for opcode, expected in ((1, 1008), (2, 1003)):
            with self.assertRaises(FrameReject) as caught:
                FrameParser().feed(client_frame(opcode), now_ms=0)
            self.assertEqual(caught.exception.close_code, expected)

    def test_absolute_header_deadline_never_resets_on_progress(self):
        parser = FrameParser()
        parser.feed(b"\x89", now_ms=0)
        parser.feed(b"\x82", now_ms=490)
        parser.check_deadlines(now_ms=499)
        with self.assertRaises(FrameReject) as caught:
            parser.check_deadlines(now_ms=500)
        self.assertEqual((caught.exception.close_code, caught.exception.code), (1008, "frame_read_timeout"))

    def test_payload_deadline_includes_header_time(self):
        parser = FrameParser()
        parser.feed(bytes.fromhex("898201020304"), now_ms=0)
        parser.feed(b"\x69", now_ms=900)
        with self.assertRaises(FrameReject) as caught:
            parser.feed(b"\x6b", now_ms=1000)
        self.assertEqual(caught.exception.close_code, 1008)

    def test_close_direction_set_and_no_data_after_close(self):
        row = CASES["WS-V2-C058"]
        valid = set(row["expected"]["client_accepted_codes"])
        for code in row["input"]["tested_codes"]:
            parser = FrameParser()
            if code in valid:
                event = parser.feed(client_frame(8, struct.pack("!H", code)), now_ms=0).events[0]
                self.assertEqual((event.close_code, event.reply_close_code), (code, 1000))
            else:
                with self.assertRaises(FrameReject) as caught:
                    parser.feed(client_frame(8, struct.pack("!H", code)), now_ms=0)
                self.assertEqual(caught.exception.close_code, 1002)
        raw = client_frame(8) + client_frame(9)
        parser = FrameParser()
        result = parser.feed(raw, now_ms=0)
        self.assertEqual(result.consumed, len(client_frame(8)))
        self.assertTrue(parser.closed)

    def test_control_payload_boundary_and_bad_clock(self):
        event = FrameParser().feed(client_frame(9, b"a" * 125), now_ms=0).events[0]
        self.assertEqual(event.payload, b"a" * 125)
        parser = FrameParser()
        parser.feed(b"\x89", now_ms=10)
        with self.assertRaises(FrameReject) as caught:
            parser.check_deadlines(now_ms=9)
        self.assertEqual(caught.exception.close_code, 1011)


class EncodeAndBufferTests(unittest.TestCase):
    def test_whole_wire_header_boundaries(self):
        for i in range(43, 49):
            row = CASES[f"WS-V2-C{i:03d}"]
            n = row["input"]["json_utf8_payload_bytes"]
            if row["expected"]["may_enqueue"]:
                frame = encode_text(b"a" * n)
                self.assertEqual(frame.wire_size, row["expected"]["whole_wire_frame_bytes"])
                self.assertEqual(len(frame.header), row["expected"]["RFC_header_bytes"])
            else:
                with self.assertRaises(EncodeReject):
                    encode_text(b"a" * n)

    def test_chunk_encoding_counts_before_copy_and_validates_utf8(self):
        frame = encode_text_chunks([b"a", b"\xe2", b"\x82\xac"])
        self.assertEqual(bytes(frame.payload), "a€".encode())
        with self.assertRaises(EncodeReject):
            encode_text_chunks([b"a" * 262134, b"b"])
        for chunks in ([b"\xff"], [b"\xe2"]):
            with self.assertRaises(EncodeReject):
                encode_text_chunks(chunks)
        with self.assertRaises(TypeError):
            frame.payload[0] = 1

    def test_server_never_encodes_client_only_or_reserved_close(self):
        row = CASES["WS-V2-C058"]
        valid = set(row["expected"]["server_encoder_accepted_codes"])
        for code in row["input"]["tested_codes"]:
            if code in valid:
                self.assertEqual(encode_close(code).to_bytes(), b"\x88\x02" + struct.pack("!H", code))
            else:
                with self.assertRaises(EncodeReject):
                    encode_close(code)
        self.assertEqual(encode_close(1000, "a" * 123).wire_size, 127)
        for reason in ("a" * 124, "\ud800"):
            with self.assertRaises(EncodeReject):
                encode_close(1000, reason)

    def test_queue_counts_whole_wire_and_control_has_its_own_reserve(self):
        buffer = OutboundBuffer()
        frame = encode_text(b"a" * 262134)
        buffer.enqueue_application(frame, now_ms=0)
        buffer.enqueue_application(frame, now_ms=0)
        self.assertEqual(buffer.application_wire_bytes, 524288)
        with self.assertRaises(BufferFull):
            buffer.enqueue_application(encode_text(b"x"), now_ms=1)
        buffer.enqueue_control(encode_control("ping", b"a" * 125), now_ms=1)
        buffer.enqueue_control(encode_control("pong", b"b" * 125), now_ms=1)
        self.assertEqual(buffer.control_wire_bytes, 254)
        self.assertEqual(buffer.application_wire_bytes, 524288)

    def test_partial_write_does_not_reset_deadline_or_change_wire_accounting(self):
        buffer = OutboundBuffer()
        buffer.enqueue_application(encode_text(b"hello"), now_ms=0)
        chunk = buffer.peek(now_ms=100)
        buffer.advance(chunk, 1, now_ms=101)
        self.assertEqual(buffer.application_wire_bytes, 7)
        chunk = buffer.peek(now_ms=590)
        with self.assertRaises(FrameReject) as caught:
            buffer.advance(chunk, 1, now_ms=600)
        self.assertEqual((caught.exception.code, caught.exception.abort_transport), ("frame_write_timeout", True))

    def test_control_priority_cannot_interleave_an_already_started_frame(self):
        buffer = OutboundBuffer()
        buffer.enqueue_application(encode_text(b"hello"), now_ms=0)
        first = buffer.peek(now_ms=0)
        buffer.advance(first, 1, now_ms=0)
        buffer.begin_close(1008, now_ms=10)
        wire = bytearray(first.data[:1])
        for _ in range(20):
            chunk = buffer.peek(now_ms=11)
            if chunk is None:
                break
            wire.extend(chunk.data)
            buffer.advance(chunk, len(chunk.data), now_ms=11)
        self.assertEqual(bytes(wire), b"\x81\x05hello\x88\x02\x03\xf0")
        self.assertTrue(buffer.closing)
        self.assertEqual(buffer.application_wire_bytes, 0)

    def test_close_discards_unsent_pages_without_claiming_delivery(self):
        buffer = OutboundBuffer()
        buffer.enqueue_application(encode_text(b"not-delivered"), now_ms=0)
        old = buffer.peek(now_ms=1)
        buffer.begin_close(1000, now_ms=2)
        with self.assertRaises(ValueError):
            buffer.advance(old, 1, now_ms=2)
        self.assertEqual(buffer.application_wire_bytes, 0)
        self.assertEqual(buffer.peek(now_ms=2).data.tobytes(), b"\x88\x02")

    def test_slow_consumer_deadline_is_absolute(self):
        buffer = OutboundBuffer()
        buffer.enqueue_application(encode_text(b"page"), now_ms=0)
        with self.assertRaises(FrameReject) as caught:
            buffer.check_deadlines(now_ms=5000)
        self.assertEqual((caught.exception.close_code, caught.exception.code), (4008, "slow_consumer"))
        buffer.begin_close(4008, now_ms=5000)
        self.assertIsNotNone(buffer.peek(now_ms=5000))

    def test_pong_matches_identity_and_does_not_extend_original_deadline(self):
        ping = PingTracker(timeout_ms=10000)
        self.assertFalse(ping.received_pong(b"", now_ms=0))
        ping.sent_ping(b"hi", now_ms=1)
        self.assertFalse(ping.received_pong(b"other", now_ms=9999))
        self.assertEqual(ping.deadline_ms, 10001)
        with self.assertRaises(FrameReject) as caught:
            ping.check_deadline(now_ms=10001)
        self.assertEqual(caught.exception.close_code, 1001)
        ping = PingTracker()
        ping.sent_ping(b"hi", now_ms=0)
        self.assertTrue(ping.received_pong(b"hi", now_ms=1))
        self.assertIsNone(ping.deadline_ms)

    def test_encoder_preserves_large_integer_text_without_float_codec(self):
        raw = b'{"sequence":9007199254740993}'
        frame = encode_text(raw)
        self.assertEqual(bytes(frame.payload), raw)
        self.assertEqual(json.loads(bytes(frame.payload))["sequence"], 9007199254740993)


if __name__ == "__main__":
    unittest.main()
