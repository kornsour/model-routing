"""python_template: a minimal, batteries-included Python project template.

Replace this package with your own code. The point of the template is the
surrounding paved road — packaging, linting, typing, tests, pre-commit, and the
centralized CI + Dependabot wiring — not this module.
"""

__version__ = "0.1.0"

__all__ = ["greet"]


def greet(name: str) -> str:
    """Return a friendly greeting."""
    return f"Hello, {name}!"
