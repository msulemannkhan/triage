"""Seams over external services — abstract interfaces with real and fake impls.

The graph depends only on the interfaces, so the deterministic core runs in CI
against fakes with no live calls or API keys.
"""
