from __future__ import annotations

import base64
import dataclasses
import hashlib
import json
import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58encode(data: bytes) -> str:
    """Zero-dependency Base58 encoder for Solana addresses and public keys."""
    if not data:
        return ""
    num = int.from_bytes(data, "big")
    chars = []
    while num > 0:
        num, rem = divmod(num, 58)
        chars.append(ALPHABET[rem])
    encoded = "".join(reversed(chars))
    pad = 0
    for byte in data:
        if byte == 0:
            pad += 1
        else:
            break
    return (ALPHABET[0] * pad) + encoded


def b58decode(s: str) -> bytes:
    """Zero-dependency Base58 decoder."""
    if not s:
        return b""
    num = 0
    for char in s:
        idx = ALPHABET.find(char)
        if idx == -1:
            raise ValueError(f"Invalid base58 character: '{char}'")
        num = num * 58 + idx
    pad = 0
    for char in s:
        if char == ALPHABET[0]:
            pad += 1
        else:
            break
    num_bytes = (num.bit_length() + 7) // 8
    result = num.to_bytes(num_bytes, "big") if num > 0 else b""
    return (b"\x00" * pad) + result


def compute_anchor_event_discriminator(event_name: str) -> bytes:
    """Computes Anchor 8-byte event discriminator: sha256('event:<Name>')[0..8]."""
    digest = hashlib.sha256(f"event:{event_name}".encode("utf-8")).digest()
    return digest[:8]


# Known Anchor Event Discriminators across Solana DeFi protocols
KNOWN_ANCHOR_EVENTS: Dict[str, Tuple[str, str]] = {
    # Discriminator hex -> (Protocol, EventName)
    compute_anchor_event_discriminator("SwapEvent").hex(): ("Generic/Raydium/Orca", "SwapEvent"),
    compute_anchor_event_discriminator("TradeEvent").hex(): ("Pump.fun/DEX", "TradeEvent"),
    compute_anchor_event_discriminator("CreateEvent").hex(): ("Pump.fun/Token", "CreateEvent"),
    compute_anchor_event_discriminator("CompleteEvent").hex(): ("Pump.fun/BondingCurve", "CompleteEvent"),
    compute_anchor_event_discriminator("DepositEvent").hex(): ("DeFi Vault/Lending", "DepositEvent"),
    compute_anchor_event_discriminator("WithdrawEvent").hex(): ("DeFi Vault/Lending", "WithdrawEvent"),
    compute_anchor_event_discriminator("LiquidateEvent").hex(): ("Lending Protocol", "LiquidateEvent"),
    compute_anchor_event_discriminator("OrderPlaced").hex(): ("Phoenix/OpenBook", "OrderPlaced"),
    compute_anchor_event_discriminator("OrderFilled").hex(): ("Phoenix/OpenBook", "OrderFilled"),
    compute_anchor_event_discriminator("OrderCancelled").hex(): ("Phoenix/OpenBook", "OrderCancelled"),
    compute_anchor_event_discriminator("LiquidityChangeEvent").hex(): ("Orca Whirlpool", "LiquidityChangeEvent"),
    compute_anchor_event_discriminator("FeeEvent").hex(): ("Jupiter/DEX", "FeeEvent"),
}


@dataclass
class ProgramReturnData:
    program_id: str
    raw_base64: str
    raw_bytes: bytes
    hex_data: str
    as_utf8: Optional[str] = None
    as_u64_le: Optional[int] = None
    as_u128_le: Optional[int] = None
    as_i64_le: Optional[int] = None
    interpreted_type: str = "bytes"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "program_id": self.program_id,
            "raw_base64": self.raw_base64,
            "hex_data": self.hex_data,
            "as_utf8": self.as_utf8,
            "as_u64_le": self.as_u64_le,
            "as_u128_le": self.as_u128_le,
            "as_i64_le": self.as_i64_le,
            "interpreted_type": self.interpreted_type,
        }


@dataclass
class DecodedAnchorEvent:
    program_id: Optional[str]
    discriminator_hex: str
    event_name: str
    protocol: str
    matched_catalog: bool
    raw_base64: str
    payload_bytes_len: int
    fields: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class ProgramEventsReport:
    return_data: Optional[ProgramReturnData] = None
    anchor_events: List[DecodedAnchorEvent] = field(default_factory=list)
    custom_logs: List[str] = field(default_factory=list)
    total_events_count: int = 0
    has_return_data: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "has_return_data": self.has_return_data,
            "total_events_count": self.total_events_count,
            "return_data": self.return_data.to_dict() if self.return_data else None,
            "anchor_events": [e.to_dict() for e in self.anchor_events],
            "custom_logs_count": len(self.custom_logs),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class AnchorEventDecoder:
    """
    Decodes Solana program execution logs, Anchor event logs (`Program data: <base64>`),
    and program return data (`Program return: <program_id> <base64>`).
    """

    def __init__(self, custom_catalog: Optional[Dict[str, Tuple[str, str]]] = None):
        self.catalog = dict(KNOWN_ANCHOR_EVENTS)
        if custom_catalog:
            self.catalog.update(custom_catalog)

    def register_event(self, event_name: str, protocol: str = "Custom") -> str:
        """Calculates discriminator and registers event in decoder catalog."""
        disc_hex = compute_anchor_event_discriminator(event_name).hex()
        self.catalog[disc_hex] = (protocol, event_name)
        return disc_hex

    def decode_return_data(self, program_id: str, raw_base64: str) -> ProgramReturnData:
        try:
            raw_bytes = base64.b64decode(raw_base64)
        except Exception:
            raw_bytes = b""

        hex_data = raw_bytes.hex()
        as_utf8 = None
        try:
            decoded_str = raw_bytes.decode("utf-8")
            if all(c.isprintable() or c in ("\n", "\r", "\t") for c in decoded_str) and len(decoded_str) > 0:
                as_utf8 = decoded_str
        except Exception:
            pass

        as_u64 = None
        as_i64 = None
        if len(raw_bytes) >= 8:
            as_u64 = struct.unpack("<Q", raw_bytes[:8])[0]
            as_i64 = struct.unpack("<q", raw_bytes[:8])[0]

        as_u128 = None
        if len(raw_bytes) >= 16:
            as_u128 = int.from_bytes(raw_bytes[:16], "little")

        interpreted = "bytes"
        if as_utf8 and len(as_utf8) >= 3:
            interpreted = "string"
        elif len(raw_bytes) == 8:
            interpreted = "u64/i64"
        elif len(raw_bytes) == 16:
            interpreted = "u128"
        elif len(raw_bytes) == 32:
            interpreted = f"pubkey:{b58encode(raw_bytes)}"

        return ProgramReturnData(
            program_id=program_id,
            raw_base64=raw_base64,
            raw_bytes=raw_bytes,
            hex_data=hex_data,
            as_utf8=as_utf8,
            as_u64_le=as_u64,
            as_u128_le=as_u128,
            as_i64_le=as_i64,
            interpreted_type=interpreted,
        )

    def decode_anchor_event(self, raw_base64: str, current_program: Optional[str] = None) -> DecodedAnchorEvent:
        try:
            data = base64.b64decode(raw_base64)
        except Exception:
            data = b""

        if len(data) < 8:
            return DecodedAnchorEvent(
                program_id=current_program,
                discriminator_hex=data.hex(),
                event_name="TruncatedEvent",
                protocol="Unknown",
                matched_catalog=False,
                raw_base64=raw_base64,
                payload_bytes_len=len(data),
                fields={},
                summary=f"Truncated event payload ({len(data)} bytes)",
            )

        disc = data[:8]
        disc_hex = disc.hex()
        payload = data[8:]

        protocol, event_name = self.catalog.get(disc_hex, ("Unknown", f"UnknownAnchorEvent_{disc_hex[:8]}"))
        matched = disc_hex in self.catalog

        fields: Dict[str, Any] = {}
        # Attempt basic primitive field extraction if payload has predictable structure
        if len(payload) >= 8:
            fields["first_u64"] = struct.unpack("<Q", payload[:8])[0]
        if len(payload) >= 16:
            fields["second_u64"] = struct.unpack("<Q", payload[8:16])[0]
        if len(payload) == 32:
            fields["pubkey"] = b58encode(payload)
        elif len(payload) >= 48 and len(payload) % 8 == 0:
            fields["payload_words"] = len(payload) // 8

        summary = f"{protocol} :: {event_name} ({len(payload)} bytes payload)"
        if "first_u64" in fields:
            summary += f" | val1={fields['first_u64']}"

        return DecodedAnchorEvent(
            program_id=current_program,
            discriminator_hex=disc_hex,
            event_name=event_name,
            protocol=protocol,
            matched_catalog=matched,
            raw_base64=raw_base64,
            payload_bytes_len=len(payload),
            fields=fields,
            summary=summary,
        )

    def decode_logs(self, logs: List[str]) -> ProgramEventsReport:
        """Parses execution log lines for return data and Anchor events."""
        report = ProgramEventsReport()
        current_program: Optional[str] = None

        for log in logs:
            if " invoke [" in log:
                parts = log.split()
                if len(parts) >= 2:
                    current_program = parts[1]
            elif " success" in log or " failed:" in log:
                pass

            if "Program return: " in log:
                # Format: Program return: <program_id> <base64_data>
                content = log.split("Program return: ", 1)[1].strip()
                tokens = content.split()
                if len(tokens) >= 2:
                    prog_id = tokens[0]
                    b64_val = tokens[1]
                    report.return_data = self.decode_return_data(prog_id, b64_val)
                    report.has_return_data = True
                elif len(tokens) == 1 and current_program:
                    report.return_data = self.decode_return_data(current_program, tokens[0])
                    report.has_return_data = True

            elif "Program data: " in log:
                # Format: Program data: <base64_data>
                b64_data = log.split("Program data: ", 1)[1].strip()
                event = self.decode_anchor_event(b64_data, current_program=current_program)
                report.anchor_events.append(event)
            elif "Program log: " in log:
                report.custom_logs.append(log.split("Program log: ", 1)[1].strip())

        report.total_events_count = len(report.anchor_events)
        return report


def decode_program_events_and_returns(
    logs: List[str], custom_catalog: Optional[Dict[str, Tuple[str, str]]] = None
) -> ProgramEventsReport:
    """Convenience helper to extract and decode Anchor events and return data from simulation logs."""
    decoder = AnchorEventDecoder(custom_catalog=custom_catalog)
    return decoder.decode_logs(logs)
