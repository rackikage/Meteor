"""Meteor API — HTTP interface for the runtime.

Meteor Doctrine #4: Runtime is the product. The API layer exposes the runtime
to external clients. It never contains business logic — that lives in the
runtime orchestration layer.

Meteor Doctrine #8: Contracts outlive implementations. The API is versioned (v1).
Breaking changes require a new version (v2), not modifications to v1.
"""
