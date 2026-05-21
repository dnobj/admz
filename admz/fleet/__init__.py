"""Fleet-wide background services: device health monitoring etc.

Distinct from :mod:`admz.snapshot.scheduler`, which manages
operator-defined recurring jobs (snapshot, drift). The fleet
services in this package are always-on (when enabled) background
loops that maintain ambient state — e.g. "which devices are
currently reachable?" — without operator action.
"""

from admz.fleet.health import (
    DeviceHealthRecord,
    DeviceHealthStatus,
    DeviceHealthStore,
    HealthMonitor,
    device_health_store,
)

__all__ = [
    "DeviceHealthRecord",
    "DeviceHealthStatus",
    "DeviceHealthStore",
    "HealthMonitor",
    "device_health_store",
]
