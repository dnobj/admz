"""Demo inference (#124) — read the environment, propose the demo inventory.

Deterministic collection + a deterministic, auditable clustering pass; the agent
narrates on top and a human confirms. Nothing here writes a demo.

Leaf-light on purpose: importing this package must stay cheap (the pure modules
below are stdlib-only), so callers in the ACS module can classify a rule without
dragging the demo stores in. Full plan: ``docs/plans/demo-inference.md``.
"""

from admz.demos.inference.observability import classify_rule

__all__ = ["classify_rule"]
