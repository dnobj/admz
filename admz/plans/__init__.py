"""
Execution plans — multi-step batched operations with single approval.

The plan engine lets an agent propose a sequence of catalog operations,
get them validated against the catalog and risk-classified, and then
execute them autonomously once approved.

Plans support:

- Dependencies between steps (``depends_on``)
- Failure policies (``stop``, ``skip_dependents``, ``continue``)
- Fleet parallelism (multi-device plans with no inter-device deps
  run devices concurrently)
- Pre-read for rollback on param.cgi writes
- Two-gate risk checks: semantic (LLM) + mechanical (catalog risk level)
"""
