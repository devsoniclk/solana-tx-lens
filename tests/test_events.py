from __future__ import annotations

import base64
import struct
import pytest
from solana_tx_lens.events import (
    AnchorEventDecoder,
    ProgramReturnData,
    b58decode,
    b58encode,
    compute_anchor_event_discriminator,
    decode_program_events_and_returns,
)


def test_b58encode_and_decode():
    raw = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\n\x0b\x0c\r\x0e\x0f"
    enc = b58encode(raw)
    dec = b58decode(enc)
    assert dec == raw

    # Empty
    assert b58encode(b"") == ""
    assert b58decode("") == b""

    # Invalid
    with pytest.raises(ValueError):
        b58decode("Invalid0OIl")


def test_anchor_event_discriminator():
    disc = compute_anchor_event_discriminator("SwapEvent")
    assert len(disc) == 8
    assert isinstance(disc, bytes)


def test_decode_program_return_data():
    decoder = AnchorEventDecoder()

    # UTF-8 string return
    text_b64 = base64.b64encode(b"TradeExecutedOK").decode("utf-8")
    ret_str = decoder.decode_return_data("Prog11111111111111111111111111111111", text_b64)
    assert ret_str.interpreted_type == "string"
    assert ret_str.as_utf8 == "TradeExecutedOK"

    # u64 integer return
    u64_bytes = struct.pack("<Q", 1_500_000_000)
    u64_b64 = base64.b64encode(u64_bytes).decode("utf-8")
    ret_num = decoder.decode_return_data("Prog22222222222222222222222222222222", u64_b64)
    assert ret_num.as_u64_le == 1_500_000_000
    assert "u64" in ret_num.interpreted_type


def test_decode_known_anchor_event():
    decoder = AnchorEventDecoder()

    # Create payload for SwapEvent: discriminator (8 bytes) + first_u64 (8 bytes) + second_u64 (8 bytes)
    disc = compute_anchor_event_discriminator("SwapEvent")
    payload = disc + struct.pack("<QQ", 500_000_000, 485_000_000)
    b64_ev = base64.b64encode(payload).decode("utf-8")

    event = decoder.decode_anchor_event(b64_ev, current_program="Raydium11111111111111111111111111111111")
    assert event.event_name == "SwapEvent"
    assert event.matched_catalog is True
    assert event.fields["first_u64"] == 500_000_000
    assert event.fields["second_u64"] == 485_000_000
    assert "500000000" in event.summary


def test_decode_custom_and_unknown_event():
    decoder = AnchorEventDecoder()

    # Unknown discriminator
    random_bytes = b"\xde\xad\xbe\xef\xca\xfe\xba\xbe" + struct.pack("<Q", 12345)
    ev_unknown = decoder.decode_anchor_event(base64.b64encode(random_bytes).decode("utf-8"))
    assert ev_unknown.matched_catalog is False
    assert "UnknownAnchorEvent" in ev_unknown.event_name

    # Register custom
    decoder.register_event("OrderMatched", protocol="DEXv3")
    disc = compute_anchor_event_discriminator("OrderMatched")
    ev_custom = decoder.decode_anchor_event(base64.b64encode(disc + struct.pack("<Q", 999)).decode("utf-8"))
    assert ev_custom.event_name == "OrderMatched"
    assert ev_custom.protocol == "DEXv3"
    assert ev_custom.matched_catalog is True


def test_decode_program_events_and_returns_full_logs():
    disc_swap = compute_anchor_event_discriminator("SwapEvent")
    swap_b64 = base64.b64encode(disc_swap + struct.pack("<Q", 100_000)).decode("utf-8")
    ret_b64 = base64.b64encode(b"SuccessReceipt").decode("utf-8")

    logs = [
        "Program 675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8 invoke [1]",
        "Program log: Raydium: swap instruction initiated",
        f"Program data: {swap_b64}",
        f"Program return: 675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8 {ret_b64}",
        "Program 675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8 success",
    ]

    report = decode_program_events_and_returns(logs)
    assert report.total_events_count == 1
    assert report.has_return_data is True
    assert report.return_data is not None
    assert report.return_data.as_utf8 == "SuccessReceipt"
    assert report.anchor_events[0].event_name == "SwapEvent"
    assert len(report.custom_logs) == 1
