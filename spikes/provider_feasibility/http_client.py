"""Small JSON transport; never print authenticated URLs or provider error bodies."""
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


def get_json(endpoint, params):
    try:
        with urlopen(endpoint + "?" + urlencode(params), timeout=20) as response:
            status = response.status
            data = json.load(response)
        if not isinstance(data, (dict, list)):
            raise ValueError("Expected JSON object or list")
        return status, data
    except HTTPError as exc:
        raise ValueError(f"HTTP {exc.code}: authentication (401/403), quota (429), or provider request failure") from None
    except (URLError, TimeoutError, OSError):
        raise ValueError("Network failure or request timeout") from None
    except (json.JSONDecodeError, UnicodeError):
        raise ValueError("Invalid JSON response") from None
