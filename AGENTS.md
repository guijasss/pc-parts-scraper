# AGENTS.md

## Purpose

This file defines the engineering expectations for any human or AI agent
working in this repository.

The goals are:

-   keep the codebase readable, testable, and maintainable
-   prefer explicitness over cleverness
-   follow Python best practices and relevant PEP guidance
-   write type-safe code with strong null handling
-   make changes that are minimal, correct, and well-tested

When modifying this repository, follow these instructions unless a more
specific local document overrides them.

------------------------------------------------------------------------

## General Principles

-   Prefer small, focused changes over broad refactors.
-   Preserve existing behavior unless explicitly required otherwise.
-   Favor clarity over brevity.
-   Avoid hidden side effects.
-   Maintain consistency across the codebase.

------------------------------------------------------------------------

## Python Style

-   Follow PEP 8 for formatting.
-   Follow PEP 257 for docstrings.
-   Use type hints (PEP 484).
-   Use modern typing (PEP 585, PEP 604).
-   Prefer f-strings over older formatting.

------------------------------------------------------------------------

## Typing and Null Safety

-   All public functions must have type hints.
-   Avoid `Any` unless necessary.
-   Use `T | None` for optional values.
-   Always check for None before use.

Example:

``` python
def normalize_name(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip()
```

------------------------------------------------------------------------

## Function Design

-   Keep functions small and single-purpose.
-   Prefer pure functions.
-   Use guard clauses to reduce nesting.
-   Avoid complex parameter lists.

------------------------------------------------------------------------

## Error Handling

-   Raise specific exceptions.
-   Do not silently swallow errors.
-   Provide clear error messages.

Example:

``` python
try:
    data = json.loads(raw)
except json.JSONDecodeError as exc:
    raise ValueError("Invalid JSON") from exc
```

------------------------------------------------------------------------

## Testing

-   Write tests for all new behavior.
-   Prefer unit tests.
-   Cover edge cases and null scenarios.

------------------------------------------------------------------------

## Final Notes

-   Keep changes minimal and focused.
-   Improve code quality when touching existing code.
