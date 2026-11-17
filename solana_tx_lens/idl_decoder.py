from __future__ import annotations

"""
solana_tx_lens.idl_decoder: Anchor Dynamic IDL Registry & Instruction Reconstructor.

Dynamically registers Anchor IDL specifications, computes 8-byte instruction,
account, and event discriminators, and reconstructs typed instruction arguments,
account metamaps, and error messages from raw simulation data and logs.
"""

from dataclasses import asdict, dataclass
import hashlib
import struct
from typing import Any


def compute_anchor_discriminator(prefix: str, name: str) -> bytes:
    """Computes Anchor 8-byte discriminator: sha256(f"{prefix}:{name}")[0..8]."""
    payload = f"{prefix}:{name}".encode("utf-8")
    return hashlib.sha256(payload).digest()[:8]


def compute_instruction_discriminator(instruction_name: str) -> bytes:
    """Computes Anchor instruction discriminator: sha256('global:' + name)[0..8]."""
    return compute_anchor_discriminator("global", instruction_name)


def compute_account_discriminator(account_name: str) -> bytes:
    """Computes Anchor account discriminator: sha256('account:' + name)[0..8]."""
    return compute_anchor_discriminator("account", account_name)


def compute_event_discriminator(event_name: str) -> bytes:
    """Computes Anchor event discriminator: sha256('event:' + name)[0..8]."""
    return compute_anchor_discriminator("event", event_name)


@dataclass
class DecodedInstructionAccount:
    name: str
    pubkey: str | None
    is_writable: bool
    is_signer: bool


@dataclass
class DecodedInstruction:
    program_id: str
    instruction_name: str
    discriminator_hex: str
    args: dict[str, Any]
    accounts: list[DecodedInstructionAccount]

    def to_dict(self) -> dict[str, Any]:
        return {
            "program_id": self.program_id,
            "instruction_name": self.instruction_name,
            "discriminator_hex": self.discriminator_hex,
            "args": self.args,
            "accounts": [asdict(a) for a in self.accounts],
        }


class AnchorIDLRegistry:
    """Registry of Anchor Interface Definition Languages (IDLs) for dynamic decoding."""

    def __init__(self) -> None:
        self._idls: dict[str, dict[str, Any]] = {}
        self._ix_lookup: dict[tuple[str, bytes], dict[str, Any]] = {}
        self._account_lookup: dict[tuple[str, bytes], dict[str, Any]] = {}
        self._error_lookup: dict[tuple[str, int], dict[str, str]] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Registers popular Solana program IDLs (Pump.fun, SPL Token, etc.)."""
        pump_fun_idl = {
            "version": "0.1.0",
            "name": "pump",
            "instructions": [
                {
                    "name": "create",
                    "accounts": [
                        {"name": "mint", "isMut": True, "isSigner": True},
                        {"name": "mintAuthority", "isMut": False, "isSigner": False},
                        {"name": "bondingCurve", "isMut": True, "isSigner": False},
                        {"name": "associatedBondingCurve", "isMut": True, "isSigner": False},
                        {"name": "global", "isMut": False, "isSigner": False},
                        {"name": "mplTokenMetadata", "isMut": False, "isSigner": False},
                        {"name": "metadata", "isMut": True, "isSigner": False},
                        {"name": "user", "isMut": True, "isSigner": True},
                        {"name": "systemProgram", "isMut": False, "isSigner": False},
                        {"name": "tokenProgram", "isMut": False, "isSigner": False},
                        {"name": "associatedTokenProgram", "isMut": False, "isSigner": False},
                        {"name": "rent", "isMut": False, "isSigner": False},
                    ],
                    "args": [
                        {"name": "name", "type": "string"},
                        {"name": "symbol", "type": "string"},
                        {"name": "uri", "type": "string"},
                    ],
                },
                {
                    "name": "buy",
                    "accounts": [
                        {"name": "global", "isMut": False, "isSigner": False},
                        {"name": "feeRecipient", "isMut": True, "isSigner": False},
                        {"name": "mint", "isMut": False, "isSigner": False},
                        {"name": "bondingCurve", "isMut": True, "isSigner": False},
                        {"name": "associatedBondingCurve", "isMut": True, "isSigner": False},
                        {"name": "associatedUser", "isMut": True, "isSigner": False},
                        {"name": "user", "isMut": True, "isSigner": True},
                        {"name": "systemProgram", "isMut": False, "isSigner": False},
                        {"name": "tokenProgram", "isMut": False, "isSigner": False},
                        {"name": "rent", "isMut": False, "isSigner": False},
                    ],
                    "args": [
                        {"name": "amount", "type": "u64"},
                        {"name": "maxSolCost", "type": "u64"},
                    ],
                },
                {
                    "name": "sell",
                    "accounts": [
                        {"name": "global", "isMut": False, "isSigner": False},
                        {"name": "feeRecipient", "isMut": True, "isSigner": False},
                        {"name": "mint", "isMut": False, "isSigner": False},
                        {"name": "bondingCurve", "isMut": True, "isSigner": False},
                        {"name": "associatedBondingCurve", "isMut": True, "isSigner": False},
                        {"name": "associatedUser", "isMut": True, "isSigner": False},
                        {"name": "user", "isMut": True, "isSigner": True},
                        {"name": "systemProgram", "isMut": False, "isSigner": False},
                        {"name": "associatedTokenProgram", "isMut": False, "isSigner": False},
                        {"name": "tokenProgram", "isMut": False, "isSigner": False},
                    ],
                    "args": [
                        {"name": "amount", "type": "u64"},
                        {"name": "minSolOutput", "type": "u64"},
                    ],
                },
            ],
            "errors": [
                {"code": 6000, "name": "NotAuthorized", "msg": "The given account is not authorized to execute this instruction."},
                {"code": 6001, "name": "AlreadyInitialized", "msg": "The program has already been initialized."},
                {"code": 6002, "name": "TooMuchSolRequired", "msg": "Slippage tolerance exceeded; too much SOL required."},
                {"code": 6003, "name": "TooLittleSolReceived", "msg": "Slippage tolerance exceeded; too little SOL received."},
                {"code": 6004, "name": "BondingCurveComplete", "msg": "The bonding curve has completed."},
            ],
        }
        self.register_idl("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P", pump_fun_idl)

    def register_idl(self, program_id: str, idl: dict[str, Any]) -> None:
        """Registers an Anchor IDL dictionary for a program."""
        self._idls[program_id] = idl

        # Index instructions
        for ix in idl.get("instructions", []):
            name = ix.get("name", "")
            # IDL may specify explicit 8-byte discriminator array, or use Anchor global hash
            if "discriminator" in ix and isinstance(ix["discriminator"], list):
                disc = bytes(ix["discriminator"])
            else:
                disc = compute_instruction_discriminator(name)
            self._ix_lookup[(program_id, disc)] = ix

        # Index accounts
        for acc in idl.get("accounts", []):
            name = acc.get("name", "")
            if "discriminator" in acc and isinstance(acc["discriminator"], list):
                disc = bytes(acc["discriminator"])
            else:
                disc = compute_account_discriminator(name)
            self._account_lookup[(program_id, disc)] = acc

        # Index errors
        for err in idl.get("errors", []):
            code = err.get("code")
            if code is not None:
                self._error_lookup[(program_id, int(code))] = {
                    "name": err.get("name", f"CustomError_{code}"),
                    "msg": err.get("msg", ""),
                }

    def get_idl(self, program_id: str) -> dict[str, Any] | None:
        """Retrieves registered IDL for a program."""
        return self._idls.get(program_id)

    def decode_instruction(
        self,
        program_id: str,
        data: bytes,
        account_keys: list[str] | None = None,
    ) -> DecodedInstruction | None:
        """
        Decodes instruction data and account addresses against registered IDL.
        """
        if len(data) < 8:
            return None

        disc = data[:8]
        ix_def = self._ix_lookup.get((program_id, disc))
        if not ix_def:
            return None

        ix_name = ix_def.get("name", "unknown")
        args_data = data[8:]
        decoded_args, _ = self._decode_args(args_data, ix_def.get("args", []))

        # Reconstruct accounts
        decoded_accounts: list[DecodedInstructionAccount] = []
        expected_accounts = ix_def.get("accounts", [])
        for i, acc_meta in enumerate(expected_accounts):
            pubkey = account_keys[i] if (account_keys and i < len(account_keys)) else None
            decoded_accounts.append(
                DecodedInstructionAccount(
                    name=acc_meta.get("name", f"account_{i}"),
                    pubkey=pubkey,
                    is_writable=acc_meta.get("isMut", acc_meta.get("writable", False)),
                    is_signer=acc_meta.get("isSigner", acc_meta.get("signer", False)),
                )
            )

        return DecodedInstruction(
            program_id=program_id,
            instruction_name=ix_name,
            discriminator_hex=disc.hex(),
            args=decoded_args,
            accounts=decoded_accounts,
        )

    def decode_error(self, program_id: str, error_code: int) -> dict[str, str] | None:
        """Resolves custom error code against registered program IDL."""
        return self._error_lookup.get((program_id, error_code))

    def _decode_args(self, data: bytes, arg_defs: list[dict[str, Any]]) -> tuple[dict[str, Any], int]:
        """Decodes binary arguments using Borsh layout specifications."""
        offset = 0
        result: dict[str, Any] = {}

        for arg in arg_defs:
            name = arg.get("name", "arg")
            arg_type = arg.get("type")
            try:
                val, consumed = self._read_type(data[offset:], arg_type)
                result[name] = val
                offset += consumed
            except Exception:
                result[name] = f"<decoding_failed_at_offset_{offset}>"
                break

        return result, offset

    def _read_type(self, data: bytes, type_spec: Any) -> tuple[Any, int]:
        """Reads a single typed value from data stream."""
        if not data:
            return None, 0

        if isinstance(type_spec, str):
            t = type_spec.lower()
            if t == "u8":
                return struct.unpack_from("<B", data, 0)[0], 1
            elif t == "i8":
                return struct.unpack_from("<b", data, 0)[0], 1
            elif t == "bool":
                return bool(data[0]), 1
            elif t == "u16":
                return struct.unpack_from("<H", data, 0)[0], 2
            elif t == "i16":
                return struct.unpack_from("<h", data, 0)[0], 2
            elif t == "u32":
                return struct.unpack_from("<I", data, 0)[0], 4
            elif t == "i32":
                return struct.unpack_from("<i", data, 0)[0], 4
            elif t == "u64":
                return struct.unpack_from("<Q", data, 0)[0], 8
            elif t == "i64":
                return struct.unpack_from("<q", data, 0)[0], 8
            elif t in ("u128", "i128"):
                val = int.from_bytes(data[:16], byteorder="little", signed=(t == "i128"))
                return val, 16
            elif t in ("pubkey", "publickey"):
                return data[:32].hex(), 32
            elif t in ("string", "str"):
                if len(data) < 4:
                    return "", 0
                str_len = struct.unpack_from("<I", data, 0)[0]
                if len(data) < 4 + str_len:
                    return "", 4
                s = data[4 : 4 + str_len].decode("utf-8", errors="replace")
                return s, 4 + str_len
            elif t in ("bytes", "vec<u8>"):
                if len(data) < 4:
                    return "", 0
                vec_len = struct.unpack_from("<I", data, 0)[0]
                return data[4 : 4 + vec_len].hex(), 4 + vec_len

        return f"<unsupported_type:{type_spec}>", 0


_DEFAULT_REGISTRY = AnchorIDLRegistry()


def get_default_idl_registry() -> AnchorIDLRegistry:
    return _DEFAULT_REGISTRY
