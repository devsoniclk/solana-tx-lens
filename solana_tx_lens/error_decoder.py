import re
from typing import Any, Dict, Optional
from .models import ErrorInfo

ANCHOR_STANDARD_ERRORS = {
    100: ("InstructionMissing", "8-byte instruction identifier not provided"),
    101: ("InstructionFallbackNotFound", "Fallback instruction not found"),
    102: ("InstructionDidNotDeserialize", "Instruction data did not deserialize"),
    103: ("InstructionDidNotSerialize", "Instruction data did not serialize"),
    200: ("ConstraintMut", "A mut constraint was violated"),
    201: ("ConstraintHasOne", "A has_one constraint was violated"),
    202: ("ConstraintSigner", "A signer constraint was violated"),
    203: ("ConstraintRaw", "A raw constraint was violated"),
    204: ("ConstraintOwner", "An owner constraint was violated"),
    205: ("ConstraintRentExempt", "A rent exemption constraint was violated"),
    206: ("ConstraintSeeds", "A seeds constraint was violated"),
    207: ("ConstraintExecutable", "An executable constraint was violated"),
    300: ("RequireEqViolated", "require_eq expression violated"),
    301: ("RequireNeqViolated", "require_neq expression violated"),
    302: ("RequireGtViolated", "require_gt expression violated"),
    303: ("RequireGteViolated", "require_gte expression violated"),
    400: ("AccountDiscriminatorAlreadySet", "Account discriminator already set"),
    401: ("AccountDiscriminatorNotFound", "Account discriminator not found"),
    402: ("AccountDiscriminatorMismatch", "Account discriminator mismatch"),
    403: ("AccountDidNotDeserialize", "Account did not deserialize"),
    404: ("AccountDidNotSerialize", "Account did not serialize"),
    405: ("AccountNotEnoughKeys", "Not enough account keys provided"),
    406: ("AccountNotMutable", "Account is not mutable"),
    407: ("AccountOwnedByWrongProgram", "Account owned by wrong program"),
}

COMMON_DEX_ERRORS = {
    # Raydium / Orca / Pump custom common ranges
    6000: ("ZeroAmount", "Swap amount or input liquidity is zero"),
    6001: ("SlippageExceeded", "Slippage tolerance exceeded; output below min expected"),
    6002: ("InsufficientLiquidity", "Insufficient liquidity in pool to complete swap"),
    6003: ("InvalidPrice", "Pool price is outside allowed tick range"),
    6004: ("ExceededMaxInput", "Input amount exceeds user specified maximum"),
    6005: ("PoolFrozen", "Target liquidity pool is paused or frozen"),
}

SOLANA_NATIVE_ERRORS = {
    "ComputationalBudgetExceeded": "Transaction compute unit limit was exceeded",
    "InsufficientFundsForRent": "Account does not have enough lamports to be rent-exempt",
    "ProgramFailedToComplete": "Program execution failed to complete within limits",
    "InvalidAccountData": "Instruction passed invalid or corrupted account data",
    "MissingRequiredSignature": "An account required to sign did not sign the transaction",
}

CUSTOM_ERR_RE = re.compile(r"Custom\((\d+)\)")
HEX_ERR_RE = re.compile(r"custom program error: (0x[0-9a-fA-F]+)")


def decode_solana_error(error_payload: Any, program_id: Optional[str] = None) -> ErrorInfo:
    """
    Decodes a raw Solana RPC simulation error into a structured ErrorInfo object.
    Supports Anchor standard codes, DEX error codes, and native runtime errors.
    """
    err_str = str(error_payload)

    # 1. Check Native Errors
    for nat_key, nat_desc in SOLANA_NATIVE_ERRORS.items():
        if nat_key in err_str:
            return ErrorInfo(
                error_type="Native",
                code=0,
                name=nat_key,
                description=nat_desc,
                program_id=program_id,
            )

    # 2. Extract numeric custom code
    code: Optional[int] = None
    if isinstance(error_payload, int):
        code = error_payload
    elif isinstance(error_payload, dict):
        # Extract from InstructionError or nested Custom dict
        if "InstructionError" in error_payload:
            inst_err = error_payload["InstructionError"]
            if isinstance(inst_err, list) and len(inst_err) > 1 and isinstance(inst_err[1], dict):
                code = inst_err[1].get("Custom")
        elif "Custom" in error_payload:
            code = error_payload.get("Custom")
    elif isinstance(error_payload, str) and error_payload.strip().isdigit():
        code = int(error_payload.strip())
    else:
        m_cust = CUSTOM_ERR_RE.search(err_str)
        if m_cust:
            code = int(m_cust.group(1))
        elif "'Custom': " in err_str:
            m_dict = re.search(r"['\"]Custom['\"]\s*:\s*(\d+)", err_str)
            if m_dict:
                code = int(m_dict.group(1))
        else:
            m_hex = HEX_ERR_RE.search(err_str)
            if m_hex:
                code = int(m_hex.group(1), 16)
            elif err_str.strip().startswith("0x"):
                try:
                    code = int(err_str.strip(), 16)
                except ValueError:
                    pass

    if code is not None:
        # Check Anchor Standard
        if code in ANCHOR_STANDARD_ERRORS:
            name, desc = ANCHOR_STANDARD_ERRORS[code]
            return ErrorInfo(error_type="Anchor", code=code, name=name, description=desc, program_id=program_id)

        # Check Common DEX
        if code in COMMON_DEX_ERRORS:
            name, desc = COMMON_DEX_ERRORS[code]
            return ErrorInfo(error_type="DEX", code=code, name=name, description=desc, program_id=program_id)

        # Unregistered Custom Program Error
        return ErrorInfo(
            error_type="Custom",
            code=code,
            name=f"Custom({code})",
            description=f"Program-defined custom error code {code} (0x{code:x})",
            program_id=program_id,
        )

    return ErrorInfo(
        error_type="Unknown",
        code=-1,
        name="UnknownError",
        description=err_str,
        program_id=program_id,
    )
