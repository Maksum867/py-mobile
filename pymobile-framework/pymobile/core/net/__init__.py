"""Networking: a dependency-free HTTP client."""

from __future__ import annotations

from .http import DEFAULT_TIMEOUT, HttpClient, Response

__all__ = ["HttpClient", "Response", "DEFAULT_TIMEOUT"]
