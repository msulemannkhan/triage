"""Data access via repository interfaces (abstract interface + concrete impls).

Services depend on the abstraction, never on storage details — so SQL (or, here,
a static fixture) stays out of the domain logic and tests can substitute an
in-memory implementation.
"""
