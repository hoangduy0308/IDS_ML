"""Canonical IDS product package.

Phase 1 keeps implementation under ``ids`` and leaves ``scripts`` as
compatibility-only entrypoints until the downstream migration beads move
domain logic behind these package roots.
"""

__all__ = ["core", "runtime", "console", "ops"]
