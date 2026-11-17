"""Restricted private-WS wire primitives, unused by every service/listener.

No sockets, clocks, authentication, storage or financial modules are imported.
The owner supplies monotonic model times and drives partial reads/writes. These
deadlines do not demonstrate actual scheduler, network or revocation latency.
"""
from __future__ import annotations

import base64
import codecs
from collections import deque
from dataclasses import dataclass, field
from hashlib import sha1
import re
import struct


WIRE_FRAME_CAP = 262144
TEXT_PAYLOAD_CAP = WIRE_FRAME_CAP - 10
APPLICATION_QUEUE_CAP = 524288
CONTROL_QUEUE_CAP = 254
MAX_ENCODING_CHUNKS = 65536
_COMMON_CLOSE_CODES = frozenset({1000, 1001, 1002, 1003, 1007, 1008, 1009,
                                1011, 1012, 1013, 1014, 3000, 3003, 3008})
_KEY = re.compile(r"[A-Za-z0-9+/]{22}==\Z", re.ASCII)
_CHALLENGE = re.compile(r"[0-9a-f]{32}\Z", re.ASCII)


class HandshakeReject(ValueError):
    """A pre-upgrade HTTP rejection; contains no supplied header material."""
    http_status = 400

    def __init__(self, code):
        self.code = code
        super().__init__(code)


class FrameReject(ValueError):
    """An upgraded-connection outcome, not an HTTP response or financial fact."""
    def __init__(self, close_code, code, *, abort_transport=False):
        self.close_code, self.code = close_code, code
        self.abort_transport = abort_transport
        super().__init__(code)


class EncodeReject(ValueError):
    """Invalid local encoding input; no bytes were authorized for sending."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class BufferFull(ValueError):
    """Backpressure, never permission to evict an application page and continue."""


@dataclass(frozen=True)
class HandshakeKey:
    canonical_key: str
    challenge: str
    accept: str


def validate_handshake_key(value, challenge):
    """Bind a canonical 16-byte RFC key to the signed lowercase-hex challenge."""
    if not isinstance(value, str) or _KEY.fullmatch(value) is None:
        raise HandshakeReject("invalid_ws_key")
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        raise HandshakeReject("invalid_ws_key") from None
    if len(raw) != 16 or base64.b64encode(raw).decode("ascii") != value:
        raise HandshakeReject("invalid_ws_key")
    if (not isinstance(challenge, str) or _CHALLENGE.fullmatch(challenge) is None
            or raw.hex() != challenge):
        raise HandshakeReject("invalid_ws_challenge")
    accept = base64.b64encode(sha1((value + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii"),
                                  usedforsecurity=False).digest()).decode("ascii")
    return HandshakeKey(value, challenge, accept)


def _valid_close(code, *, client):
    return (type(code) is int and (code in _COMMON_CLOSE_CODES
            or client and code == 1010 or 4000 <= code <= 4999))


def _close_payload(payload, *, client):
    if not payload:
        return None, ""
    if len(payload) == 1:
        raise EncodeReject("invalid_close_payload")
    code = int.from_bytes(payload[:2], "big")
    if not _valid_close(code, client=client):
        reason = "invalid_close_code_direction" if not client and code == 1010 else "invalid_close_code"
        raise EncodeReject(reason)
    try:
        text = bytes(payload[2:]).decode("utf-8", errors="strict")
    except UnicodeError:
        raise EncodeReject("invalid_utf8") from None
    return code, text


def _view(value):
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise EncodeReject("invalid_payload_type")
    try:
        view = memoryview(value)
        if view.ndim != 1 or not view.c_contiguous:
            raise ValueError
        return view.cast("B")
    except (TypeError, ValueError):
        raise EncodeReject("invalid_payload_type") from None


def _header(opcode, n):
    if n <= 125:
        return bytes((0x80 | opcode, n))
    if n <= 65535:
        return bytes((0x80 | opcode, 126)) + struct.pack("!H", n)
    return bytes((0x80 | opcode, 127)) + struct.pack("!Q", n)


@dataclass(frozen=True)
class WireFrame:
    """Two wire segments: queues do not concatenate/copy a large whole frame.

    Payload backing is immutable even through a public view's ``obj``.
    ``to_bytes`` is an explicit bounded copy, not used by the output queue.
    """
    opcode: int
    header: bytes
    _payload: bytes = field(repr=False)

    def __post_init__(self):
        if type(self.opcode) is not int or self.opcode not in (1, 8, 9, 10):
            raise EncodeReject("invalid_opcode")
        payload = _view(self._payload)
        # Direct construction cannot retain an externally mutable payload.
        if type(self._payload) is not bytes:
            if len(payload) > (TEXT_PAYLOAD_CAP if self.opcode == 1 else 125):
                raise EncodeReject("frame_too_large")
            object.__setattr__(self, "_payload", bytes(payload))
            payload = _view(self._payload)
        if self.opcode == 1:
            if len(payload) > TEXT_PAYLOAD_CAP:
                raise EncodeReject("frame_too_large")
            try:
                codecs.decode(payload, "utf-8", errors="strict")
            except UnicodeError:
                raise EncodeReject("invalid_utf8") from None
        else:
            if len(payload) > 125:
                raise EncodeReject("control_too_large")
            if self.opcode == 8:
                _close_payload(payload, client=False)
        if self.header != _header(self.opcode, len(payload)) or self.wire_size > WIRE_FRAME_CAP:
            raise EncodeReject("invalid_frame_header")

    @property
    def payload(self):
        return memoryview(self._payload).toreadonly()

    @property
    def wire_size(self):
        return len(self.header) + len(self._payload)

    def to_bytes(self):
        """Explicit copy, for small vectors/debugging; queues use segments."""
        return self.header + bytes(self._payload)

    def _segment(self, offset, maximum):
        if offset < len(self.header):
            return memoryview(self.header)[offset:offset + maximum]
        start = offset - len(self.header)
        return self.payload[start:start + maximum]


def encode_text(payload):
    view = _view(payload)
    if len(view) > TEXT_PAYLOAD_CAP:
        raise EncodeReject("frame_too_large")
    # Immutable bytes can be retained without a copy; external mutable buffers
    # cannot alter a queued frame through their original alias.
    owned = payload if type(payload) is bytes else bytes(view)
    return WireFrame(1, _header(1, len(owned)), owned)


def encode_text_chunks(chunks):
    """Bound each append before copying; no oversized serialized-body buffer."""
    payload = bytearray()
    decoder = codecs.getincrementaldecoder("utf-8")(errors="strict")
    for index, chunk in enumerate(chunks):
        if index >= MAX_ENCODING_CHUNKS:
            raise EncodeReject("encoding_chunk_limit")
        view = _view(chunk)
        if len(view) > TEXT_PAYLOAD_CAP - len(payload):
            raise EncodeReject("frame_too_large")
        try:
            decoder.decode(view, final=False)
        except UnicodeError:
            raise EncodeReject("invalid_utf8") from None
        payload.extend(view)
    try:
        decoder.decode(b"", final=True)
    except UnicodeError:
        raise EncodeReject("invalid_utf8") from None
    # Freeze before publication. The bounded builder's temporary allocation is
    # not a claim that logical wire accounting proves process RSS.
    owned = bytes(payload)
    payload.clear()
    return WireFrame(1, _header(1, len(owned)), owned)


def encode_control(kind, payload=b""):
    opcode = {"close": 8, "ping": 9, "pong": 10}.get(kind)
    if opcode is None:
        raise EncodeReject("invalid_control_kind")
    view = _view(payload)
    if len(view) > 125:
        raise EncodeReject("control_too_large")
    owned = payload if type(payload) is bytes else bytes(view)
    return WireFrame(opcode, _header(opcode, len(owned)), owned)


def encode_close(code=1000, reason=""):
    if not _valid_close(code, client=False):
        raise EncodeReject("invalid_close_code_direction" if code == 1010 else "invalid_close_code")
    if not isinstance(reason, str):
        raise EncodeReject("invalid_close_reason")
    try:
        raw = reason.encode("utf-8", errors="strict")
    except UnicodeError:
        raise EncodeReject("invalid_utf8") from None
    if len(raw) > 123:
        raise EncodeReject("control_too_large")
    return encode_control("close", struct.pack("!H", code) + raw)


@dataclass(frozen=True)
class ControlEvent:
    kind: str
    payload: bytes = field(repr=False)
    close_code: int | None = None
    reason: str = field(default="", repr=False)
    reply_close_code: int | None = None


@dataclass(frozen=True)
class FeedBatch:
    consumed: int
    events: tuple[ControlEvent, ...]
    needs_more: bool
    turn_exhausted: bool


class _ModelClock:
    def __init__(self):
        self._last_ms = None

    def _time(self, now_ms):
        if type(now_ms) is not int or now_ms < 0:
            raise ValueError("model time must be a nonnegative integer")
        if self._last_ms is not None and now_ms < self._last_ms:
            raise FrameReject(1011, "codec_clock_regressed")
        self._last_ms = now_ms
        return now_ms


class FrameParser(_ModelClock):
    """Incremental masked-client control parser; leaves excess input to owner."""
    def __init__(self, *, controls_per_turn=8):
        super().__init__()
        if type(controls_per_turn) is not int or not 1 <= controls_per_turn <= 8:
            raise ValueError("controls_per_turn must be an integer in 1..8")
        self._turn_limit = controls_per_turn
        self._header, self._payload = bytearray(), bytearray()
        self._started_ms = None
        self._payload_length = None
        self._mask = None
        self._opcode = None
        self.closed = False
        self.maximum_buffered_bytes = 0

    @property
    def buffered_bytes(self):
        return len(self._header) + len(self._payload)

    def _record_size(self):
        self.maximum_buffered_bytes = max(self.maximum_buffered_bytes, self.buffered_bytes)

    def _reject(self, close_code, code):
        self.closed = True
        self._header.clear()
        self._payload.clear()
        raise FrameReject(close_code, code)

    def check_deadlines(self, *, now_ms):
        try:
            now = self._time(now_ms)
        except FrameReject:
            self.closed = True
            raise
        if self.closed or self._started_ms is None:
            return
        if self._mask is None and now >= self._started_ms + 500:
            self._reject(1008, "frame_read_timeout")
        if now >= self._started_ms + 1000:
            self._reject(1008, "frame_read_timeout")

    def _target(self):
        if len(self._header) < 2:
            return 2
        first, second = self._header[:2]
        opcode, length = first & 15, second & 127
        if first & 0x70 or opcode not in (0, 1, 2, 8, 9, 10) or not second & 0x80:
            self._reject(1002, "invalid_frame_header")
        if opcode == 0 or opcode >= 8 and (not first & 0x80 or length > 125):
            self._reject(1002, "invalid_frame_header")
        extra = 2 if length == 126 else 8 if length == 127 else 0
        if len(self._header) < 2 + extra:
            return 2 + extra
        n = int.from_bytes(self._header[2:2 + extra], "big") if extra else length
        if (extra == 2 and n < 126 or extra == 8 and (n < 65536 or n >= 2**63)):
            self._reject(1002, "invalid_frame_length")
        if len(self._header) < 2 + extra + 4:
            return 2 + extra + 4
        if opcode in (1, 2):
            self._reject(1008 if opcode == 1 else 1003, "client_data_unsupported")
        self._payload_length, self._opcode = n, opcode
        self._mask = bytes(self._header[-4:])
        return len(self._header)

    def feed(self, data, *, now_ms):
        if self.closed:
            raise FrameReject(1002, "parser_closed")
        self.check_deadlines(now_ms=now_ms)
        view = _view(data)
        offset, events = 0, []
        while offset < len(view) and len(events) < self._turn_limit and not self.closed:
            if self._started_ms is None:
                self._started_ms = now_ms
            if self._mask is None:
                target = self._target()
                n = min(target - len(self._header), len(view) - offset)
                self._header.extend(view[offset:offset + n])
                offset += n
                self._record_size()
                self._target()
                if self._mask is None:
                    continue
            if self._payload_length:
                n = min(self._payload_length - len(self._payload), len(view) - offset)
                self._payload.extend(view[offset:offset + n])
                offset += n
                self._record_size()
                if len(self._payload) < self._payload_length:
                    continue
            payload = bytes(value ^ self._mask[i % 4] for i, value in enumerate(self._payload))
            kind = {8: "close", 9: "ping", 10: "pong"}[self._opcode]
            code, reason = None, ""
            if kind == "close":
                try:
                    code, reason = _close_payload(payload, client=True)
                except EncodeReject as exc:
                    self._reject(1007 if exc.code == "invalid_utf8" else 1002, exc.code)
                self.closed = True
            events.append(ControlEvent(kind, payload, code, reason, 1000 if kind == "close" else None))
            self._header.clear()
            self._payload.clear()
            self._started_ms = self._payload_length = self._mask = self._opcode = None
        return FeedBatch(offset, tuple(events), self.buffered_bytes > 0,
                         len(events) == self._turn_limit and offset < len(view))


class PingTracker(_ModelClock):
    def __init__(self, *, timeout_ms=10000):
        super().__init__()
        if type(timeout_ms) is not int or not 1 <= timeout_ms <= 10000:
            raise ValueError("timeout_ms must be an integer in 1..10000")
        self._timeout_ms = timeout_ms
        self._payload = None
        self.deadline_ms = None

    def check_deadline(self, *, now_ms):
        self._time(now_ms)
        if self.deadline_ms is not None and now_ms >= self.deadline_ms:
            raise FrameReject(1001, "pong_timeout")

    def sent_ping(self, payload, *, now_ms):
        self.check_deadline(now_ms=now_ms)
        raw = _view(payload)
        if len(raw) > 125:
            raise EncodeReject("control_too_large")
        if self.deadline_ms is not None:
            raise ValueError("only one ping may be outstanding")
        self._payload = bytes(raw)
        self.deadline_ms = now_ms + self._timeout_ms

    def received_pong(self, payload, *, now_ms):
        self.check_deadline(now_ms=now_ms)
        if self.deadline_ms is None or _view(payload) != self._payload:
            return False
        self._payload = self.deadline_ms = None
        return True


@dataclass
class _Pending:
    identity: int
    frame: WireFrame
    queued_ms: int
    offset: int = 0
    started_ms: int | None = None


@dataclass(frozen=True)
class SendChunk:
    identity: int
    offset: int
    data: memoryview = field(repr=False)


class OutboundBuffer(_ModelClock):
    """Bounded segments with explicit partial-output accounting, no socket I/O."""
    def __init__(self):
        super().__init__()
        self._application, self._controls = deque(), deque()
        self._active = None
        self._next_identity = 1
        self.application_wire_bytes = self.control_wire_bytes = 0
        self._application_count = self._control_count = 0
        self.closing = False
        self.close_deadline_ms = None

    def _pending(self, frame, now_ms):
        value = _Pending(self._next_identity, frame, now_ms)
        self._next_identity += 1
        return value

    def _release(self, pending):
        if pending.frame.opcode == 1:
            self.application_wire_bytes -= pending.frame.wire_size
            self._application_count -= 1
        else:
            self.control_wire_bytes -= pending.frame.wire_size
            self._control_count -= 1

    def check_deadlines(self, *, now_ms):
        self._time(now_ms)
        if (self._active is not None and self._active.started_ms is not None
                and now_ms >= self._active.started_ms + 500):
            raise FrameReject(1001, "frame_write_timeout", abort_transport=True)
        if self.close_deadline_ms is not None and now_ms >= self.close_deadline_ms:
            raise FrameReject(1001, "close_handshake_timeout", abort_transport=True)
        if not self.closing:
            pending = list(self._application)
            if self._active is not None and self._active.frame.opcode == 1:
                pending.append(self._active)
            if pending and now_ms >= min(p.queued_ms for p in pending) + 5000:
                raise FrameReject(4008, "slow_consumer")

    def enqueue_application(self, frame, *, now_ms):
        self.check_deadlines(now_ms=now_ms)
        if not isinstance(frame, WireFrame) or frame.opcode != 1:
            raise EncodeReject("application_frame_required")
        if self.closing:
            raise BufferFull("connection is closing")
        if self._application_count >= 2 or self.application_wire_bytes + frame.wire_size > APPLICATION_QUEUE_CAP:
            raise BufferFull("application queue is full")
        self._application.append(self._pending(frame, now_ms))
        self.application_wire_bytes += frame.wire_size
        self._application_count += 1

    def enqueue_text_chunks(self, chunks, *, now_ms):
        """Check capacity before requesting any serialization/source chunk."""
        self.check_deadlines(now_ms=now_ms)
        if self.closing or self._application_count >= 2:
            raise BufferFull("application queue is full or closing")
        frame = encode_text_chunks(chunks)
        self.enqueue_application(frame, now_ms=now_ms)

    def enqueue_control(self, frame, *, now_ms):
        self.check_deadlines(now_ms=now_ms)
        if not isinstance(frame, WireFrame) or frame.opcode not in (9, 10):
            raise EncodeReject("ping_or_pong_required")
        if self.closing:
            return False
        # RFC permits answering only the most recent of multiple waiting pings.
        if frame.opcode == 10:
            retained = deque()
            for old in self._controls:
                if old.frame.opcode == 10:
                    self._release(old)
                else:
                    retained.append(old)
            self._controls = retained
        if self._control_count >= 2 or self.control_wire_bytes + frame.wire_size > CONTROL_QUEUE_CAP:
            raise BufferFull("control queue is full")
        self._controls.append(self._pending(frame, now_ms))
        self.control_wire_bytes += frame.wire_size
        self._control_count += 1
        return True

    def begin_close(self, code=1000, reason="", *, now_ms):
        self._time(now_ms)
        frame = encode_close(code, reason)
        if self.closing:
            return False
        self.closing = True
        self.close_deadline_ms = now_ms + 2000
        for queue in (self._application, self._controls):
            while queue:
                self._release(queue.popleft())
        if self._active is not None and self._active.offset == 0:
            self._release(self._active)
            self._active = None
        self._controls.append(self._pending(frame, now_ms))
        self.control_wire_bytes += frame.wire_size
        self._control_count += 1
        return True

    def peek(self, *, now_ms, maximum=65536):
        self.check_deadlines(now_ms=now_ms)
        if type(maximum) is not int or not 1 <= maximum <= 65536:
            raise ValueError("maximum must be an integer in 1..65536")
        if self._active is None:
            if self._controls:
                self._active = self._controls.popleft()
            elif self._application and not self.closing:
                self._active = self._application.popleft()
            else:
                return None
        pending = self._active
        if pending.started_ms is None:
            pending.started_ms = now_ms
        return SendChunk(pending.identity, pending.offset, pending.frame._segment(pending.offset, maximum))

    def advance(self, chunk, count, *, now_ms):
        self.check_deadlines(now_ms=now_ms)
        pending = self._active
        if (not isinstance(chunk, SendChunk) or pending is None
                or (chunk.identity, chunk.offset) != (pending.identity, pending.offset)
                or type(count) is not int or not 0 <= count <= len(chunk.data)):
            raise ValueError("partial output does not match the current wire segment")
        pending.offset += count
        if pending.offset == pending.frame.wire_size:
            self._release(pending)
            self._active = None
