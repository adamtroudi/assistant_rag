import json
import hashlib
import math
from itertools import combinations
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import fmean
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.schemas import PlatformForecastInput

BERLIN = ZoneInfo("Europe/Berlin")


class ForecastValidationError(ValueError):
    pass


class ForecastPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timestamp_utc: AwareDatetime
    value: float | None

    @model_validator(mode="after")
    def ensure_utc(self) -> "ForecastPoint":
        if self.timestamp_utc.utcoffset() != timedelta(0):
            raise ValueError("timestamp_utc doit être exprimé en UTC (+00:00 ou Z)")
        return self


class ForecastSeries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    forecast_id: str = Field(min_length=1, max_length=200)
    forecast_version: str = Field(min_length=1, max_length=100)
    machine_id: str
    horizon_days: Literal[7, 15, 30]
    start_utc: AwareDatetime
    end_utc: AwareDatetime
    quantity: str = Field(min_length=1, max_length=100)
    unit: Literal["kW", "kWh"]
    points: list[ForecastPoint]

    @model_validator(mode="after")
    def validate_contract(self) -> "ForecastSeries":
        if self.start_utc.utcoffset() != timedelta(0) or self.end_utc.utcoffset() != timedelta(0):
            raise ValueError("start_utc et end_utc doivent être exprimés en UTC")
        if self.end_utc - self.start_utc != timedelta(days=self.horizon_days):
            raise ValueError("les bornes UTC ne correspondent pas exactement à horizon_days")
        timestamps = [point.timestamp_utc for point in self.points]
        if len(timestamps) != len(set(timestamps)):
            raise ValueError("horodatages de prévision dupliqués")
        if any(not self.start_utc <= stamp < self.end_utc for stamp in timestamps):
            raise ValueError("un point est hors des bornes [start_utc, end_utc)")
        return self


class ForecastEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    forecasts: list[ForecastSeries]


class ForecastFileAdapter:
    """Adapter for the documented internal contract, not an assumed XGBoost format."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def select(
        self,
        machine_ids: list[str],
        horizon_days: int | None,
        forecast_id: str | None,
    ) -> tuple[list[ForecastSeries], list[str]]:
        if not self.path.is_file():
            return [], [f"prévision indisponible: fichier absent ({self.path})"]
        try:
            envelope = ForecastEnvelope.model_validate_json(self.path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ForecastValidationError(f"forecast_results.json ne respecte pas le contrat interne: {exc}") from exc
        selected = [
            forecast
            for forecast in envelope.forecasts
            if forecast.machine_id in machine_ids
            and (horizon_days is None or forecast.horizon_days == horizon_days)
            and (forecast_id is None or forecast.forecast_id == forecast_id)
        ]
        warnings: list[str] = []
        if not selected:
            warnings.append("prévision indisponible pour les filtres demandés")
        return selected, warnings


def summarize_forecast(forecast: ForecastSeries) -> dict[str, object]:
    values = [point.value for point in forecast.points if point.value is not None]
    summary: dict[str, object] = {
        "forecast_id": forecast.forecast_id,
        "forecast_version": forecast.forecast_version,
        "machine_id": forecast.machine_id,
        "horizon_days": forecast.horizon_days,
        "start_utc": forecast.start_utc.isoformat(),
        "end_utc": forecast.end_utc.isoformat(),
        "start_local": forecast.start_utc.astimezone(BERLIN).isoformat(),
        "end_local": forecast.end_utc.astimezone(BERLIN).isoformat(),
        "quantity": forecast.quantity,
        "unit": forecast.unit,
        "point_count": len(forecast.points),
        "missing_count": len(forecast.points) - len(values),
    }
    if values:
        summary.update(min=min(values), max=max(values), mean=fmean(values))
        # A power series cannot be added to obtain energy without interval semantics.
        if forecast.unit == "kWh":
            summary["sum"] = sum(values)
    return summary


def adapt_platform_forecast(
    payload: PlatformForecastInput,
    default_unit: Literal["W", "kW", "kWh"] = "W",
    naive_timezone: str = "UTC",
) -> tuple[ForecastSeries, list[str]]:
    """Validate the platform XGBoost shape and convert it to the internal contract."""

    if payload.n_points != len(payload.forecast):
        raise ForecastValidationError(
            f"n_points={payload.n_points} mais forecast contient {len(payload.forecast)} points"
        )
    expected_points = payload.horizon_days * 24 * 60
    if expected_points % payload.frequency_minutes != 0:
        raise ForecastValidationError("frequency_minutes ne divise pas exactement l'horizon")
    expected_points //= payload.frequency_minutes
    if payload.n_points != expected_points:
        raise ForecastValidationError(
            f"n_points={payload.n_points}, attendu={expected_points} pour "
            f"{payload.horizon_days} jours à {payload.frequency_minutes} minutes"
        )

    try:
        source_timezone = ZoneInfo(payload.timezone or naive_timezone)
    except Exception as exc:
        raise ForecastValidationError(
            f"fuseau de prévision invalide: {payload.timezone or naive_timezone}"
        ) from exc

    value_key = f"predicted_{payload.value_col}"
    warnings: list[str] = []
    naive_seen = False
    points: list[ForecastPoint] = []
    for index, raw_point in enumerate(payload.forecast):
        if "timestamp" not in raw_point:
            raise ForecastValidationError(f"forecast[{index}].timestamp est absent")
        if value_key not in raw_point:
            raise ForecastValidationError(f"forecast[{index}].{value_key} est absent")
        try:
            timestamp = datetime.fromisoformat(str(raw_point["timestamp"]).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ForecastValidationError(f"timestamp invalide au point {index}") from exc
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=source_timezone)
            naive_seen = True
        timestamp_utc = timestamp.astimezone(timezone.utc)

        raw_value = raw_point[value_key]
        value: float | None
        if raw_value is None:
            value = None
        elif isinstance(raw_value, bool):
            raise ForecastValidationError(f"valeur booléenne interdite au point {index}")
        else:
            try:
                value = float(raw_value)
            except (TypeError, ValueError) as exc:
                raise ForecastValidationError(f"valeur non numérique au point {index}") from exc
            if not math.isfinite(value):
                raise ForecastValidationError(f"valeur non finie au point {index}")
        points.append(ForecastPoint(timestamp_utc=timestamp_utc, value=value))

    if naive_seen:
        warnings.append(
            f"horodatages sans offset interprétés dans le fuseau {source_timezone.key} puis convertis en UTC"
        )
    timestamps = [point.timestamp_utc for point in points]
    if timestamps != sorted(timestamps):
        raise ForecastValidationError("les points de prévision ne sont pas ordonnés")
    expected_step = timedelta(minutes=payload.frequency_minutes)
    if any(right - left != expected_step for left, right in zip(timestamps, timestamps[1:])):
        raise ForecastValidationError("la cadence des horodatages ne correspond pas à frequency_minutes")

    source_unit = payload.unit or default_unit
    if payload.unit is None:
        warnings.append(f"unité absente du fichier; valeur configurée utilisée: {source_unit}")
    if source_unit == "W":
        for point in points:
            if point.value is not None:
                point.value /= 1000.0
        internal_unit: Literal["kW", "kWh"] = "kW"
        warnings.append("prévisions converties de W vers kW avant calcul des KPI")
    else:
        internal_unit = source_unit

    canonical = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    forecast_id = payload.forecast_id or f"xgboost-{content_hash[:16]}"
    forecast_version = payload.forecast_version or "platform-xgboost-adapter-v1"
    if payload.forecast_id is None:
        warnings.append("forecast_id absent; identifiant déterministe dérivé du contenu")
    if payload.forecast_version is None:
        warnings.append("version du modèle XGBoost absente du fichier")

    start_utc = points[0].timestamp_utc
    end_utc = start_utc + timedelta(days=payload.horizon_days)
    series = ForecastSeries(
        forecast_id=forecast_id,
        forecast_version=forecast_version,
        machine_id=payload.machine,
        horizon_days=payload.horizon_days,
        start_utc=start_utc,
        end_utc=end_utc,
        quantity=payload.value_col,
        unit=internal_unit,
        points=points,
    )
    return series, warnings


def compare_forecasts(forecasts: list[ForecastSeries]) -> list[dict[str, object]]:
    """Compute pairwise KPI deltas without delegating arithmetic to the LLM."""

    comparisons: list[dict[str, object]] = []
    summaries = [(forecast, summarize_forecast(forecast)) for forecast in forecasts]
    for (left, left_summary), (right, right_summary) in combinations(summaries, 2):
        if left.unit != right.unit or left.quantity != right.quantity:
            continue
        deltas = {
            key: float(left_summary[key]) - float(right_summary[key])
            for key in ("min", "max", "mean", "sum")
            if key in left_summary and key in right_summary
        }
        comparisons.append(
            {
                "left_forecast_id": left.forecast_id,
                "left_machine_id": left.machine_id,
                "right_forecast_id": right.forecast_id,
                "right_machine_id": right.machine_id,
                "quantity": left.quantity,
                "unit": left.unit,
                "left_minus_right": deltas,
            }
        )
    return comparisons


def utc_to_berlin(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("un datetime UTC conscient du fuseau est requis")
    return value.astimezone(BERLIN)
