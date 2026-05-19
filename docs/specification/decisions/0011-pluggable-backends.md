# ADR-0011: Pluggable registry backends (SQLite default, Vault optional)

**Status:** Accepted, in production.
**Date:** Original design 2026-01; recorded as ADR 2026-05-18.

## Context

Different ADMZ deployments have different credential-storage needs:

- A single operator running ADMZ on a laptop wants zero-config: no
  external service to set up, no secret-management knowledge required.
- An enterprise deployment already runs HashiCorp Vault and wants
  ADMZ's credentials in Vault alongside the rest of the org's secrets,
  with AppRole-based auth and existing audit infrastructure.
- A future deployment might want AWS Secrets Manager, Azure Key Vault,
  or a custom backend.

Hard-coding either choice would alienate one of the personas.

## Decision

Define an abstract `DeviceRegistry` base class
(`admz/device_registry.py`) and select concrete implementations via
the `DEVICE_REGISTRY_BACKEND` environment variable.

```python
class DeviceRegistry(ABC):
    @abstractmethod
    def get_credentials(self, device_id, account_id, requester) -> dict: ...
    @abstractmethod
    def get_device_info(self, device_id) -> dict: ...
    @abstractmethod
    def list_devices(self) -> list: ...
    # ... + ~10 more abstract methods
```

Implementations:
- `admz.backends.sqlite_backend.SQLiteDeviceRegistry` — default,
  zero-config, local file, Fernet-encrypted password fields. Selected
  by `DEVICE_REGISTRY_BACKEND=sqlite` (the default).
- `admz.backends.vault_backend.VaultDeviceRegistry` — HashiCorp Vault
  KV-v2, AppRole / token auth, standard `secret/data/devices/...`
  paths. Selected by `DEVICE_REGISTRY_BACKEND=vault`.

The factory (`admz/factory.py::create_device_registry`) instantiates
the right one. The rest of ADMZ — MCP server, REST API, plan engine,
snapshot engine — depends on the abstract type and is unaware of which
backend is active.

The factory does **lazy imports** so installing without `hvac` (the
Vault client) doesn't break SQLite installs, and vice versa.

## Consequences

**Positive:**
- Adding a third backend (KMS, ASM, KeyVault) is a new file +
  factory branch. No core changes.
- Tests can use SQLite in-memory or a mock backend without standing
  up Vault.
- Different fleets in the same org can run ADMZ with their preferred
  backend, sharing the catalog + spec but not the credential store.

**Negative:**
- The abstract contract has to satisfy every backend's quirks. Some
  Vault concepts (lease TTLs, revocation) don't map cleanly to
  SQLite; either the interface adds optional methods OR the
  backend-specific feature stays hidden.
- Two backends to test. CI runs SQLite tests by default; Vault tests
  are skipped unless a Vault server is reachable (the test fixture
  guards them).
- The audit log (Phase 4D) and the protected-fleet-settings keys
  (ADR-0020) live in the SQLite-backed *shared* DB, separate from
  whatever the registry uses. So even Vault-backed deployments still
  have an `admz.db` file — for audit, sessions, settings — just no
  credentials in it.

## References

- ADR-0010 — Fernet (the SQLite-side encryption)
- ADR-0014 — config in git, creds in DB (this ADR is the DB side)
- Requirements: [credential-storage.md](../requirements/credential-storage.md), [extensibility.md](../requirements/extensibility.md)
- Code: `admz/device_registry.py`, `admz/factory.py`, `admz/backends/`
- Persona: [enterprise-fleet-operator](../personas/enterprise-fleet-operator.md)
