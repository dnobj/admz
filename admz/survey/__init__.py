"""
ADMZ survey / contributor mode.

Opt-in, default-OFF capability that lets a deployed ADMZ install **survey the
Axis devices it can reach** (read-only API discovery + optional read-only
validation), redact everything site-sensitive, and submit the result to the
central ``axis-api-atlas`` as a GitHub pull request for maintainer review.

Modules:

* :mod:`.secrets`   -- encrypt/decrypt the GitHub PAT at rest (registry Fernet key).
* :mod:`.redact`    -- the trust boundary: identity whitelist, serial hashing, preview.
* :mod:`.diff`      -- compare a live snapshot against the installed atlas (what's new).
* :mod:`.collector` -- per-device read-only discovery (wraps the atlas refresh tool).
* :mod:`.bundle`    -- assemble a contribution bundle (uses axis_api_atlas.contrib).
* :mod:`.github`    -- submit a bundle as a PR (or write it offline). [Workstream D]

Invariants (enforced across the package):
  - credentials never enter a bundle (redaction + the atlas secret-scan gate);
  - discovery is read-only; validation is read-only (Tier 0) or lab-only (Tier 1);
  - nothing is submitted without the operator's explicit opt-in + preview.
"""

COLLECTOR_VERSION = "1.0.0"
