"""Dependency-free form/input validation.

A small set of composable validators plus a :class:`Validator` that combines
them, so an app can validate a login form, a settings field or any input
without pulling in a validation library. The validators are pure and produce a
list of human-readable error messages — they never mutate state, so the same
validator can be reused for many fields.

Example::

    v = Validator(
        ("email", [required, email]),
        ("age", [integer, between(0, 120)]),
    )
    errors = v.validate({"email": "x@y.com", "age": 30})
    assert errors == {}
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any

__all__ = [
    "Validator",
    "ValidationError",
    "required",
    "optional",
    "email",
    "length",
    "min_length",
    "max_length",
    "integer",
    "number",
    "between",
    "min",
    "max",
    "matches",
    "one_of",
    "regex",
    "boolean",
]

#: A validator: takes a value and returns None (ok) or an error message.
ValidatorFn = Callable[[Any], str | None]

#: Well-known regex for email addresses (pragmatic, not RFC-perfect).
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ValidationError(Exception):
    """Raised by :meth:`Validator.validate_or_raise` when validation fails."""

    def __init__(self, errors: Mapping[str, str]) -> None:
        super().__init__(", ".join(f"{k}: {v}" for k, v in errors.items()))
        self.errors = dict(errors)


# --------------------------------------------------------------------------
# Individual validators (return None on success, a message on failure)
# --------------------------------------------------------------------------
def required(value: Any) -> str | None:
    """A value must be present (not None, not an empty string/list/dict)."""
    if value is None:
        return "is required"
    if isinstance(value, (str, list, dict, tuple, set)) and not value:
        return "is required"
    return None


def optional(value: Any) -> str | None:
    """Skip further validation when the value is absent/empty."""
    # Handled by Validator: optional fields are skipped. Never fails itself.
    return None


def email(value: Any) -> str | None:
    """A value must look like an email address."""
    if not isinstance(value, str) or not _EMAIL_RE.match(value.strip()):
        return "must be a valid email address"
    return None


def length(minimum: int | None = None, maximum: int | None = None) -> ValidatorFn:
    """A string's length must fall within [minimum, maximum]."""
    def _check(value: Any) -> str | None:
        if value is None:
            return None
        size = len(value)
        if minimum is not None and size < minimum:
            return f"must be at least {minimum} characters"
        if maximum is not None and size > maximum:
            return f"must be at most {maximum} characters"
        return None
    return _check


def min_length(n: int) -> ValidatorFn:
    """A string must be at least ``n`` characters long."""
    return length(minimum=n)


def max_length(n: int) -> ValidatorFn:
    """A string must be at most ``n`` characters long."""
    return length(maximum=n)


def integer(value: Any) -> str | None:
    """A value must be an integer (or a string of digits)."""
    if isinstance(value, bool):
        return "must be an integer"
    if isinstance(value, int):
        return None
    if isinstance(value, str):
        try:
            int(value.strip())
            return None
        except ValueError:
            pass
    return "must be an integer"


def number(value: Any) -> str | None:
    """A value must be a number (int or float)."""
    if isinstance(value, bool):
        return "must be a number"
    if isinstance(value, (int, float)):
        return None
    if isinstance(value, str):
        try:
            float(value.strip())
            return None
        except ValueError:
            pass
    return "must be a number"


def between(low: float, high: float) -> ValidatorFn:
    """A numeric value must lie within [low, high]."""
    def _check(value: Any) -> str | None:
        if value is None:
            return None
        try:
            num = float(value)
        except (TypeError, ValueError):
            return "must be a number"
        if not (low <= num <= high):
            return f"must be between {low} and {high}"
        return None
    return _check


def min(low: float) -> ValidatorFn:  # noqa: A001 - intentional name
    """A numeric value must be at least ``low``."""
    return between(low, float("inf"))


def max(high: float) -> ValidatorFn:  # noqa: A001 - intentional name
    """A numeric value must be at most ``high``."""
    return between(float("-inf"), high)


def matches(other: str) -> ValidatorFn:
    """A string must equal ``other`` (useful for "confirm password")."""
    def _check(value: Any) -> str | None:
        if value != other:
            return "does not match"
        return None
    return _check


def one_of(choices: Sequence[Any]) -> ValidatorFn:
    """A value must be one of ``choices``."""
    allowed = tuple(choices)

    def _check(value: Any) -> str | None:
        if value not in allowed:
            rendered = ", ".join(str(c) for c in allowed)
            return f"must be one of: {rendered}"
        return None
    return _check


def regex(pattern: str, message: str | None = None) -> ValidatorFn:
    """A string must match ``pattern``."""
    compiled = re.compile(pattern)

    def _check(value: Any) -> str | None:
        if not isinstance(value, str) or not compiled.fullmatch(value.strip()):
            return message or f"must match {pattern!r}"
        return None
    return _check


def boolean(value: Any) -> str | None:
    """A value must be a boolean (or a recognised boolean-like string)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and value.strip().lower() in ("true", "false", "1", "0", "yes", "no"):
        return None
    return "must be a boolean"


# --------------------------------------------------------------------------
# Validator
# --------------------------------------------------------------------------
class Validator:
    """Combines per-field validators and runs them over a data mapping.

    ``fields`` is an iterable of ``(name, [validator, ...])`` pairs. Fields whose
    value is missing/empty are skipped unless they include :func:`required`.
    """

    __slots__ = ("_fields",)

    def __init__(
        self,
        fields: Sequence[tuple[str, Sequence[ValidatorFn]]] = (),
    ) -> None:
        self._fields: list[tuple[str, list[ValidatorFn]]] = [
            (name, list(fns)) for name, fns in fields
        ]

    def add(self, name: str, *validators: ValidatorFn) -> None:
        """Register more validators for a field."""
        for existing in self._fields:
            if existing[0] == name:
                existing[1].extend(validators)
                return
        self._fields.append((name, list(validators)))

    def validate(self, data: Mapping[str, Any]) -> dict[str, str]:
        """Return a mapping of field name to first error message (empty when OK)."""
        errors: dict[str, str] = {}
        for name, validators in self._fields:
            value = data.get(name)
            present = value is not None and not (
                isinstance(value, (str, list, dict, tuple, set)) and not value
            )
            # Skip optional empty fields unless a 'required' is present.
            if not present and not any(fn is required for fn in validators):
                continue
            for fn in validators:
                if fn is optional:
                    continue
                message = fn(value)
                if message is not None:
                    errors[name] = message
                    break
        return errors

    def validate_or_raise(self, data: Mapping[str, Any]) -> None:
        """Like :meth:`validate` but raises :class:`ValidationError` on failure."""
        errors = self.validate(data)
        if errors:
            raise ValidationError(errors)
