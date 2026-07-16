"""Demos — the experience-center unit of work (ADR-0046; ADR-0041 Layer 4, phase 1).

A *demo* is the thing you show a customer: specific **devices** (each with a role)
+ the **config** that makes it work + the **signals** that prove it's running + the
**narrative** you say. It composes existing primitives rather than replacing them —
Scenario (ADR-0044) is its config layer, detections/events (ADR-0041) its signal
layer — and adds the one thing neither can answer alone: *is this demo ready?*
"""
