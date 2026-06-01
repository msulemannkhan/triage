"""The decision layer: pure, deterministic policy. No I/O, no LLM.

Consumes structured ``Understanding`` + ``EnrichmentResult`` and produces a
``RoutingDecision`` with a rules-fired rationale. This is where "controlled AI"
becomes literal: every decision that matters is made here, in plain Python.
"""
