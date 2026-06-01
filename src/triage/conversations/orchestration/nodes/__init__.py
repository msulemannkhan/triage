"""Graph nodes. Each is a factory binding its dependencies (LLM, enrichment)
and returning an async node callable, so the graph can be wired with fakes in
tests and real providers in production without changing the nodes.
"""
