import re
from dataclasses import dataclass

from app.domain import SUPPORTED_MACHINE_IDS

_ALIASES: dict[str, tuple[str, ...]] = {
    "EPI_PumpStation1": ("epi_pumpstation1", "pumpstation1", "pump station 1", "pompe 1"),
    "EPI_PumpStation2": ("epi_pumpstation2", "pumpstation2", "pump station 2", "pompe 2"),
    "EPI_PickAndPlace": ("epi_pickandplace", "pickandplace", "pick and place"),
}


@dataclass(frozen=True)
class ScopeDecision:
    machine_ids: list[str]
    unsupported_mentions: list[str]


def resolve_scope(
    question: str,
    requested_machine_ids: list[str] | None,
    forecast_machine_ids: set[str] | None = None,
) -> ScopeDecision:
    lowered = question.casefold()
    unsupported: set[str] = set()
    forecast_ids = forecast_machine_ids or set()

    for match in re.findall(r"\b(?:EPI|TEC)_[A-Za-z0-9_-]+\b", question, flags=re.IGNORECASE):
        canonical_match = next(
            (machine for machine in SUPPORTED_MACHINE_IDS if machine.casefold() == match.casefold()), None
        )
        forecast_match = next(
            (machine for machine in forecast_ids if machine.casefold() == match.casefold()), None
        )
        if canonical_match is None and forecast_match is None:
            unsupported.add(match)
    if re.search(r"\bTEC\b", question, flags=re.IGNORECASE):
        unsupported.add("TEC")
    forecast_question = any(machine.casefold() in lowered for machine in forecast_ids)
    if not forecast_question and re.search(
        r"\b(?:EPI[ _-]?)?PV\b|photovoltaïque|compteur global|total\s*load", question, re.I
    ):
        unsupported.add("EPI_PV/EPI_TotalLoad")

    if requested_machine_ids is not None:
        selected = list(requested_machine_ids)
    else:
        selected = [
            machine_id
            for machine_id, aliases in _ALIASES.items()
            if any(alias in lowered for alias in aliases)
        ]
        if not selected and re.search(r"\b(?:les\s+)?(?:deux\s+)?pompes?\b|stations? de pompage", lowered):
            selected = ["EPI_PumpStation1", "EPI_PumpStation2"]
        if not selected and not forecast_question:
            selected = list(SUPPORTED_MACHINE_IDS)

    return ScopeDecision(machine_ids=selected, unsupported_mentions=sorted(unsupported))
