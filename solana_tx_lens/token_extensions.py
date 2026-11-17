from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

TOKEN_2022_PROGRAM_ID = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


@dataclass
class TransferFeeConfig:
    fee_basis_points: int
    maximum_fee: int
    withholding_account: Optional[str] = None
    harvestable_lamports: int = 0


@dataclass
class TransferHookConfig:
    hook_program_id: str
    invoked: bool = False
    consumed_cus: int = 0
    success: bool = True
    error_message: Optional[str] = None


@dataclass
class ExtensionDetail:
    extension_type: str
    description: str
    risk_level: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    details: Dict[str, Any] = field(default_factory=dict)
    warning: Optional[str] = None


@dataclass
class TokenExtensionAuditReport:
    mint: str
    program_id: str
    is_token_2022: bool
    detected_extensions: List[ExtensionDetail] = field(default_factory=list)
    transfer_fee: Optional[TransferFeeConfig] = None
    transfer_hook: Optional[TransferHookConfig] = None
    gross_transfer_amount: float = 0.0
    net_transfer_amount: float = 0.0
    fee_deducted: float = 0.0
    risk_score: int = 0  # 0 to 100
    risk_rating: str = "LOW"  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


def calculate_transfer_fee(amount: int, fee_basis_points: int, maximum_fee: int) -> int:
    """Calculate the exact Token-2022 transfer fee with ceiling rounding and maximum cap."""
    if fee_basis_points <= 0 or amount <= 0:
        return 0
    raw_fee = (amount * fee_basis_points + 9999) // 10000
    return min(raw_fee, maximum_fee)


def inspect_token_extensions(
    mint: str,
    program_id: str = TOKEN_2022_PROGRAM_ID,
    account_data_extensions: Optional[List[Dict[str, Any]]] = None,
    simulation_logs: Optional[List[str]] = None,
    transfer_amount: float = 0.0,
    decimals: int = 6,
) -> TokenExtensionAuditReport:
    """
    Audits Token-2022 extensions, transfer fees, transfer hooks, and permanent delegates.
    Analyzes transaction execution logs for transfer hook invocations and fee deductions.
    """
    is_t22 = program_id == TOKEN_2022_PROGRAM_ID
    extensions_list: List[ExtensionDetail] = []
    transfer_fee_cfg: Optional[TransferFeeConfig] = None
    transfer_hook_cfg: Optional[TransferHookConfig] = None
    recommendations: List[str] = []
    risk_points = 0

    if not is_t22:
        return TokenExtensionAuditReport(
            mint=mint,
            program_id=program_id,
            is_token_2022=False,
            recommendations=["Legacy SPL Token Program (Tokenkeg) in use; no Token-2022 extensions active."],
        )

    ext_data = account_data_extensions or []

    for ext in ext_data:
        ext_type = ext.get("type", "").lower()
        if ext_type in ("transferfeeconfig", "transfer_fee", "transferfee"):
            bps = ext.get("fee_basis_points", 0)
            max_fee = ext.get("maximum_fee", 0)
            withholding = ext.get("withholding_account")
            transfer_fee_cfg = TransferFeeConfig(
                fee_basis_points=bps,
                maximum_fee=max_fee,
                withholding_account=withholding,
            )
            risk = "MEDIUM" if bps > 100 else "LOW"
            if bps > 500:
                risk = "HIGH"
                risk_points += 30
                recommendations.append(f"Excessive transfer fee of {bps / 100:.2f}% detected (>5.0%). Verify fee destination.")
            else:
                risk_points += 10
            extensions_list.append(
                ExtensionDetail(
                    extension_type="TransferFee",
                    description=f"Transfer fee of {bps} bps ({bps/100:.2f}%) capped at {max_fee} raw units",
                    risk_level=risk,
                    details={"fee_basis_points": bps, "maximum_fee": max_fee, "withholding_account": withholding},
                )
            )

        elif ext_type in ("transferhook", "transfer_hook"):
            hook_prog = ext.get("program_id", "")
            transfer_hook_cfg = TransferHookConfig(hook_program_id=hook_prog)
            risk_points += 25
            extensions_list.append(
                ExtensionDetail(
                    extension_type="TransferHook",
                    description=f"CPI Transfer Hook dispatched to program {hook_prog}",
                    risk_level="HIGH",
                    details={"hook_program_id": hook_prog},
                    warning="Transfer hooks execute custom arbitrary CPI logic on every transfer and can revert or increase compute units.",
                )
            )
            recommendations.append(f"Verify transfer hook program {hook_prog} security and compute budget overhead.")

        elif ext_type in ("permanentdelegate", "permanent_delegate"):
            delegate = ext.get("delegate", "")
            risk_points += 50
            extensions_list.append(
                ExtensionDetail(
                    extension_type="PermanentDelegate",
                    description=f"Permanent delegate active: {delegate}",
                    risk_level="CRITICAL",
                    details={"delegate": delegate},
                    warning="Permanent delegate can transfer or burn tokens without the token owner's signature or consent.",
                )
            )
            recommendations.append("CRITICAL: Permanent delegate can seize funds. Unsuitable for trustless DEX trades.")

        elif ext_type in ("defaultaccountstate", "default_account_state"):
            state = ext.get("state", "Frozen")
            if state.lower() == "frozen":
                risk_points += 35
                extensions_list.append(
                    ExtensionDetail(
                        extension_type="DefaultAccountState",
                        description="New token accounts default to Frozen state",
                        risk_level="HIGH",
                        details={"default_state": state},
                        warning="Recipient accounts cannot transfer tokens until unfrozen by the freeze authority.",
                    )
                )
                recommendations.append("Token accounts require explicit unfreezing before outbound transfers.")

        elif ext_type in ("nontransferable", "non_transferable"):
            risk_points += 60
            extensions_list.append(
                ExtensionDetail(
                    extension_type="NonTransferable",
                    description="Soulbound token: transfers are strictly prohibited",
                    risk_level="CRITICAL",
                    details={},
                    warning="Token cannot be transferred or sold under any conditions.",
                )
            )
            recommendations.append("Token is soulbound; transfers will fail at runtime.")

        elif ext_type in ("interestbearingconfig", "interest_bearing"):
            rate = ext.get("current_rate", 0)
            extensions_list.append(
                ExtensionDetail(
                    extension_type="InterestBearing",
                    description=f"Continuously compounding interest bearing token at rate {rate} bps",
                    risk_level="LOW",
                    details={"current_rate": rate},
                )
            )

        elif ext_type in ("confidentialtransfer", "confidential_transfer"):
            extensions_list.append(
                ExtensionDetail(
                    extension_type="ConfidentialTransfer",
                    description="Zero-knowledge ElGamal confidential transfers enabled",
                    risk_level="MEDIUM",
                    details={},
                )
            )

    # Inspect logs if provided to detect runtime transfer hook execution
    if simulation_logs:
        for log in simulation_logs:
            if "TransferHook" in log or "transfer_hook" in log.lower():
                if transfer_hook_cfg:
                    transfer_hook_cfg.invoked = True
                else:
                    transfer_hook_cfg = TransferHookConfig(hook_program_id="UnknownHookFromLogs", invoked=True)
            if "Program return: TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb" in log:
                pass
            if transfer_hook_cfg and "failed" in log.lower() and transfer_hook_cfg.invoked:
                transfer_hook_cfg.success = False
                transfer_hook_cfg.error_message = log

    # Fee math
    gross = transfer_amount
    net = transfer_amount
    fee = 0.0
    if transfer_fee_cfg and transfer_amount > 0:
        factor = 10**decimals
        raw_amount = int(transfer_amount * factor)
        raw_fee = calculate_transfer_fee(raw_amount, transfer_fee_cfg.fee_basis_points, transfer_fee_cfg.maximum_fee)
        fee = raw_fee / factor
        net = max(0.0, gross - fee)

    # Risk rating
    risk_score = min(100, risk_points)
    if risk_score >= 60:
        rating = "CRITICAL"
    elif risk_score >= 35:
        rating = "HIGH"
    elif risk_score >= 15:
        rating = "MEDIUM"
    else:
        rating = "LOW"

    if not recommendations:
        recommendations.append("Token-2022 configuration standard; no anomalous risks detected.")

    return TokenExtensionAuditReport(
        mint=mint,
        program_id=program_id,
        is_token_2022=True,
        detected_extensions=extensions_list,
        transfer_fee=transfer_fee_cfg,
        transfer_hook=transfer_hook_cfg,
        gross_transfer_amount=gross,
        net_transfer_amount=net,
        fee_deducted=fee,
        risk_score=risk_score,
        risk_rating=rating,
        recommendations=recommendations,
    )
