"""Gmail integration: OAuth, scanning, and a mock fallback.

The package works in two modes:

* **real**  — when an OAuth ``credentials.json`` (and, after consent, a token)
  is present, it talks to the Gmail API.
* **mock**  — otherwise it returns deterministic sample emails so the whole
  pipeline (scan → discover businesses/years → history) is demonstrable now,
  before any Google credentials exist. This matches the user's request to
  "make placeholders for now but make it work as soon as I give credentials".
"""
