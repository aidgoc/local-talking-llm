"""IP-based geolocation using ipinfo.io (free, no API key needed)."""

import requests


def get_location() -> dict | None:
    """Get approximate location via IP geolocation.

    Returns dict with city, region, country, timezone, or None on failure.
    """
    try:
        resp = requests.get("https://ipinfo.io/json", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "city": data.get("city", ""),
                "region": data.get("region", ""),
                "country": data.get("country", ""),
                "timezone": data.get("timezone", ""),
                "loc": data.get("loc", ""),  # lat,lon
            }
    except (requests.ConnectionError, requests.Timeout, OSError):
        pass
    return None
