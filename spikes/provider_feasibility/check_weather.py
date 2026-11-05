"""Inspect two coordinate forecasts in UTC and explicit imperial units."""
import json
from http_client import get_json

VARIABLES = ["wind_speed_10m", "rain", "snowfall"]


def main():
    try:
        status, payload = get_json("https://api.open-meteo.com/v1/forecast", {
            "latitude": "32.7767,29.7604", "longitude": "-96.7970,-95.3698",
            "hourly": ",".join(VARIABLES), "wind_speed_unit": "mph",
            "precipitation_unit": "inch", "timezone": "GMT", "forecast_days": 3})
        forecasts = payload if isinstance(payload, list) else [payload]
        if len(forecasts) != 2:
            raise ValueError("Expected two coordinate forecasts")
        for forecast in forecasts:
            hourly = forecast["hourly"]
            times = hourly["time"]
            if not times or any(len(hourly[v]) != len(times) for v in VARIABLES):
                raise ValueError("Empty or misaligned hourly arrays")
            print(json.dumps({"http_status": status, "latitude": forecast["latitude"],
                "longitude": forecast["longitude"], "utc_offset_seconds": forecast["utc_offset_seconds"],
                "units": forecast["hourly_units"], "observations": len(times),
                "first": times[0], "last": times[-1],
                "nonnull": {v: sum(x is not None for x in hourly[v]) for v in VARIABLES}}))
        return 0
    except (ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
