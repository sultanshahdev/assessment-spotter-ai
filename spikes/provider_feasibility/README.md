# P01 provider spike
Python 3; no third-party dependencies. From repository root:
- Export HERE_API_KEY in your shell (never paste credentials in command history).
- Run python3 spikes/provider_feasibility/check_routing.py
- Run python3 spikes/provider_feasibility/check_weather.py

No .env auto-loading. Exit codes: routing 2 missing credentials, 1 request/validation/no routes, 0 successful nonempty responses; weather 1 failure, 0 validated arrays. Success does not establish licensing or three alternatives.
Routing uses provider default truck dimensions; no cargo weight is submitted. Encoded geometry hashes establish byte distinctness only, not meaningful corridor separation. Full geometry decoding/overlap analysis remains pending. No automatic retries or fabricated data.


## P01.2 TomTom
Run `python3 spikes/provider_feasibility/check_tomtom_routing.py > spikes/provider_feasibility/tomtom-routing-result.json`.
The probe uses TOMTOM_API_KEY from the environment first, then a Git-ignored repository `.env` containing `TOMTOM_API_KEY=...`. Never paste the key in command history or output. To enter it into the current Bash shell privately: `read -rsp 'TomTom API key: ' TOMTOM_API_KEY; export TOMTOM_API_KEY`.
It reads a literal assignment without executing `.env`; no extra dependency. Exit 2 missing key, 1 request/validation failure, 0 nonempty route responses (not a guarantee of three suitable truck routes). Uses the HERE journey constants and sanitized HTTP helper. Only allowlisted effective settings are emitted.
See [TomTom findings](tomtom-findings.md) and `tomtom-routing-result.json`; HERE findings/result remain historical evidence.
Offline checks: `python3 -m unittest discover -s spikes/provider_feasibility -p 'test_*.py' -v`.
