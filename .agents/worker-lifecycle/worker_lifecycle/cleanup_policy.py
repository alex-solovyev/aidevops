"""Report-only cleanup decisions; no evidence collection or execution authority."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class CleanupEvidence:
    """Required assertions from future verified evidence collectors, not user flags.

    A path match or ended PID cannot establish generation, admission, coverage,
    or writer quiescence. No production collector currently provides these proofs.
    Defaults deliberately describe insufficient evidence.
    """

    generation_verified: bool = False
    admission_closed: bool = False
    ownership_complete: bool = False
    writers_quiescent: bool = False
    run_states: tuple[Literal["alive", "ended", "unknown"], ...] = ()
    inventory_complete: bool = False
    preservation: Literal["required", "verified", "unknown"] = "unknown"


@dataclass(frozen=True)
class CleanupDecision:
    action: Literal["hold", "archive-candidate", "remove-candidate"]
    reason: str

    @property
    def cleanup_authorized(self) -> Literal[False]:
        """A planning result must never act as an executor capability."""
        return False


def decide_cleanup(evidence: CleanupEvidence) -> CleanupDecision:
    """Apply one launcher-independent policy without reading or modifying state."""
    requirements = (
        (evidence.generation_verified, "generation-unverified"),
        (evidence.admission_closed, "admission-not-closed"),
        (evidence.ownership_complete, "ownership-incomplete"),
    )
    for satisfied, reason in requirements:
        if satisfied is not True:
            return CleanupDecision("hold", reason)
    if not evidence.run_states or any(state != "ended" for state in evidence.run_states):
        return CleanupDecision("hold", "runs-not-confirmed-ended")
    if evidence.writers_quiescent is not True:
        return CleanupDecision("hold", "writers-not-quiescent")
    if evidence.inventory_complete is not True:
        return CleanupDecision("hold", "inventory-incomplete")
    if evidence.preservation == "required":
        return CleanupDecision("archive-candidate", "local-results-require-preservation")
    if evidence.preservation == "verified":
        return CleanupDecision("remove-candidate", "results-preserved")
    return CleanupDecision("hold", "preservation-unknown")
