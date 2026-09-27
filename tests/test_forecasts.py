import json
from datetime import datetime, timedelta, timezone

import pytest

from app.services.forecasts import (
    ForecastFileAdapter,
    ForecastValidationError,
    adapt_platform_forecast,
    utc_to_berlin,
)
from app.schemas import PlatformForecastInput


def test_malformed_forecast_is_rejected(tmp_path):
    path = tmp_path / "forecast_results.json"
    path.write_text(
        json.dumps(
            {
                "forecasts": [
                    {
                        "forecast_id": "bad",
                        "forecast_version": "v1",
                        "machine_id": "EPI_PumpStation1",
                        "horizon_days": 7,
                        "start_utc": "2026-01-01T00:00:00Z",
                        "end_utc": "2026-01-02T00:00:00Z",
                        "quantity": "active_power",
                        "unit": "W",
                        "points": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ForecastValidationError):
        ForecastFileAdapter(path).select(["EPI_PumpStation1"], 7, None)


def test_berlin_conversion_preserves_winter_and_summer_offsets():
    winter = utc_to_berlin(datetime(2026, 1, 15, 12, tzinfo=timezone.utc))
    summer = utc_to_berlin(datetime(2026, 7, 15, 12, tzinfo=timezone.utc))
    assert winter.isoformat().endswith("+01:00")
    assert summer.isoformat().endswith("+02:00")
    assert winter.hour == 13
    assert summer.hour == 14


def test_platform_xgboost_output_is_validated_and_converted_to_kw():
    start = datetime(2025, 1, 1)
    points = [
        {
            "timestamp": (start + timedelta(minutes=5 * index)).isoformat(),
            "predicted_P_total": 1000.0 + index,
        }
        for index in range(7 * 24 * 12)
    ]
    payload = PlatformForecastInput(
        machine="EPI_TotalLoad_synthetic_test",
        value_col="P_total",
        frequency_minutes=5,
        horizon_days=7,
        n_points=len(points),
        forecast=points,
    )

    series, warnings = adapt_platform_forecast(payload, "W", "UTC")

    assert series.machine_id == "EPI_TotalLoad_synthetic_test"
    assert series.unit == "kW"
    assert series.points[0].value == 1.0
    assert series.end_utc - series.start_utc == timedelta(days=7)
    assert any("dérivé" in warning for warning in warnings)


def test_platform_xgboost_output_rejects_wrong_point_count():
    payload = PlatformForecastInput(
        machine="EPI_TotalLoad_synthetic_test",
        value_col="P_total",
        frequency_minutes=5,
        horizon_days=7,
        n_points=2016,
        forecast=[{"timestamp": "2025-01-01T00:00:00", "predicted_P_total": 1}],
    )
    with pytest.raises(ForecastValidationError):
        adapt_platform_forecast(payload)
