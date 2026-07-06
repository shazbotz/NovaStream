"""Domain layer: models, interfaces (ports), and errors.

Nothing in this package may import from ``kernel``, ``services``,
``plugins``, or any third-party adapter library. This is the one layer
every other layer is allowed to depend on - see
architecture-design-phase1-v3.md §1 for the full dependency-direction rule.
"""
