"""Live device-event subsystem (ADR-0041 layers 2–3).

ADMZ subscribes to each device's VAPIX **event stream over WebSocket**
(``ws-data-stream``, JSON-RPC), normalizes every event to a uniform record,
stores it append-only, and (layer 3) fires event-pattern detections. This is
ADMZ's first push/streaming consumer — everything else is request/response +
polling.

Transport choice rationale (see ADR-0041): ACS Pro exposes no public outbound
event API, and a device's single MQTT broker is owned by ACS — so the
device-direct WebSocket stream is the only clean, documented path, and it's the
only one that surfaces raw device I/O and PTZ events.

The whole subsystem is **off by default**, gated on the ``event_ingest_enabled``
fleet setting.
"""

from admz.events.store import EventStore, event_store  # noqa: F401
