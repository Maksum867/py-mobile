"""Internationalisation.

Everything needed to ship an app in several languages:

* :class:`Translations` — a tiny catalogue with ``%``/``{}`` interpolation and
  plural support, loadable from a JSON file per language;
* :func:`device_language` — the language the *phone* is set to, which is the
  piece the standard library cannot provide;
* :func:`t` — the module-level shorthand applications actually call.

``gettext`` and ``.mo`` catalogues keep working — the stdlib is packaged in
full — and :meth:`Translations.install_gettext` hands over to it when a
project already has a translator workflow. The built-in JSON format exists
because a mobile app usually needs a dozen strings, not a toolchain.

::

    from pymobile import t, translations

    translations.load({"greeting": "Привіт, {name}!"}, language="uk")
    translations.use(device_language(default="en"))

    Label(t("greeting", name="Оксана"))
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from ..logging import get_logger

__all__ = [
    "Translations",
    "translations",
    "t",
    "device_language",
    "normalise_language",
]

_log = get_logger("i18n")

#: Languages where "one" covers 1 only and everything else is plural.
_DEFAULT_PLURAL_KEYS = ("one", "other")


def normalise_language(tag: str) -> str:
    """Reduce a locale tag to a lowercase ``language`` or ``language-region``.

    ``uk_UA.UTF-8`` and ``uk-ua`` both become ``uk-ua``; ``C`` and ``POSIX``
    become ``en``.
    """
    if not tag:
        return ""
    cleaned = tag.split(".")[0].split("@")[0].replace("_", "-").strip().lower()
    if cleaned in ("c", "posix", ""):
        return "en"
    return cleaned


def device_language(*, default: str = "en") -> str:
    """The language the device (or the desktop shell) is configured to use.

    On Android the value comes from the platform bridge, so it follows the
    system setting and survives the user changing it. Elsewhere the usual
    environment variables are consulted, which is what makes the same code
    testable on a laptop.
    """
    from .bridge import get_bridge

    bridge = get_bridge()
    getter = getattr(bridge, "device_language", None)
    if callable(getter):
        try:
            tag = normalise_language(str(getter() or ""))
        except Exception:  # pragma: no cover - a broken bridge must not crash
            _log.debug("bridge could not report the device language", exc_info=True)
            tag = ""
        if tag:
            return tag

    for variable in ("PYMOBILE_LANGUAGE", "LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(variable)
        if value:
            # LANGUAGE may hold a colon-separated priority list.
            tag = normalise_language(value.split(":")[0])
            if tag:
                return tag
    return normalise_language(default)


class Translations:
    """A catalogue of message strings, one dictionary per language.

    Lookup falls back from the region to the bare language and finally to the
    default language, so ``pt-br`` quietly uses ``pt`` and an untranslated key
    still renders as English rather than blowing up mid-screen.
    """

    def __init__(self, *, default_language: str = "en") -> None:
        self.default_language = normalise_language(default_language)
        self._catalogues: dict[str, dict[str, Any]] = {}
        self._language = self.default_language
        self._missing: set[str] = set()
        self._listeners: list[Callable[[str], None]] = []

    # -- change notification ----------------------------------------------
    def subscribe(self, listener: Callable[[str], None]) -> Callable[[], None]:
        """Call ``listener(language)`` whenever the active language changes.

        Returns a function that removes the listener again. :class:`App` uses
        this to rebuild the visible screen, because ``t()`` is evaluated inside
        ``build()`` — the translated string is baked into the widget, so a new
        language needs a rebuild rather than a redraw.
        """
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def _notify(self) -> None:
        """Tell every listener the language changed; errors never propagate."""
        for listener in tuple(self._listeners):
            try:
                listener(self._language)
            except Exception:  # pragma: no cover - a bad listener must not break i18n
                _log.exception("language listener failed")

    # -- catalogue management ---------------------------------------------
    @property
    def language(self) -> str:
        """The language currently in use."""
        return self._language

    @property
    def languages(self) -> tuple[str, ...]:
        """Every language with a loaded catalogue."""
        return tuple(sorted(self._catalogues))

    def load(self, messages: Mapping[str, Any], *, language: str) -> None:
        """Add or extend the catalogue for ``language``."""
        tag = normalise_language(language)
        if not tag:
            raise ValueError("language must not be empty")
        self._catalogues.setdefault(tag, {}).update(messages)

    def load_file(self, path: str | Path, *, language: str | None = None) -> str:
        """Load a JSON catalogue; the language defaults to the file's stem.

        ``locales/uk.json`` therefore needs no arguments at all.
        """
        file = Path(path)
        tag = normalise_language(language or file.stem)
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except OSError as error:
            raise FileNotFoundError(f"cannot read catalogue {file}: {error}") from error
        except json.JSONDecodeError as error:
            raise ValueError(f"{file} is not valid JSON: {error}") from error
        if not isinstance(data, dict):
            raise ValueError(f"{file} must contain a JSON object of messages")
        self.load(data, language=tag)
        return tag

    def load_dir(self, directory: str | Path) -> tuple[str, ...]:
        """Load every ``*.json`` catalogue in a directory."""
        root = Path(directory)
        loaded = [self.load_file(path) for path in sorted(root.glob("*.json"))]
        return tuple(loaded)

    def use(self, language: str) -> str:
        """Switch the active language and return the tag actually selected.

        Any screen currently on display is rebuilt, so the new language shows
        up immediately instead of on the next navigation.
        """
        tag = normalise_language(language) or self.default_language
        if tag == self._language:
            return self._language
        self._language = tag
        self._missing.clear()
        _log.debug("language set to %s", self._language)
        self._notify()
        return self._language

    def clear(self) -> None:
        """Forget every catalogue (used by tests)."""
        self._catalogues.clear()
        self._missing.clear()
        self._language = self.default_language

    # -- lookup ------------------------------------------------------------
    def _chain(self, language: str) -> Iterable[str]:
        """Catalogues to consult, most specific first."""
        seen: list[str] = []
        for candidate in (language, language.split("-")[0], self.default_language):
            if candidate and candidate not in seen:
                seen.append(candidate)
        return seen

    def lookup(self, key: str, *, language: str | None = None) -> Any:
        """Return the raw entry for ``key``, or ``None`` when it is unknown."""
        for tag in self._chain(normalise_language(language or self._language)):
            catalogue = self._catalogues.get(tag)
            if catalogue is not None and key in catalogue:
                return catalogue[key]
        return None

    def has(self, key: str, *, language: str | None = None) -> bool:
        """Whether ``key`` resolves in the given (or current) language."""
        return self.lookup(key, language=language) is not None

    def get(
        self,
        key: str,
        /,
        *,
        count: int | None = None,
        language: str | None = None,
        default: str | None = None,
        **params: Any,
    ) -> str:
        """Translate ``key``, interpolating ``params``.

        A missing key returns ``default`` if given, otherwise the key itself —
        a screen with one untranslated string must still render. Each missing
        key is logged once, so a gap is visible during development without
        flooding the log from inside a render loop.
        """
        entry = self.lookup(key, language=language)
        if entry is None:
            if key not in self._missing:
                self._missing.add(key)
                _log.warning("missing translation for %r in %r", key, self._language)
            entry = key if default is None else default

        if isinstance(entry, Mapping):
            entry = self._plural(entry, count)

        text = str(entry)
        if count is not None:
            params.setdefault("count", count)
        if not params:
            return text
        try:
            return text.format(**params)
        except (KeyError, IndexError, ValueError):
            # A malformed placeholder must not take the screen down.
            _log.warning("could not interpolate %r with %r", key, sorted(params))
            return text

    def _plural(self, forms: Mapping[str, Any], count: int | None) -> Any:
        """Pick a plural form.

        The rule is the English/Germanic one — ``one`` for exactly 1, ``other``
        otherwise — with explicit ``zero``/``few``/``many`` honoured when the
        catalogue provides them, which covers Slavic languages such as
        Ukrainian without pulling in a CLDR dependency.
        """
        if count is None:
            return forms.get("other") or next(iter(forms.values()), "")
        if count == 0 and "zero" in forms:
            return forms["zero"]

        if any(key in forms for key in ("few", "many")):
            modulo10, modulo100 = count % 10, count % 100
            if modulo10 == 1 and modulo100 != 11 and "one" in forms:
                return forms["one"]
            if 2 <= modulo10 <= 4 and not 12 <= modulo100 <= 14 and "few" in forms:
                return forms["few"]
            if "many" in forms:
                return forms["many"]

        if count == 1 and "one" in forms:
            return forms["one"]
        # Anything other than 1 is plural here, so "other" must be preferred
        # over "one" — checking in catalogue order would return the singular.
        if "other" in forms:
            return forms["other"]
        for key in _DEFAULT_PLURAL_KEYS:
            if key in forms:
                return forms[key]
        return next(iter(forms.values()), "")

    # -- interoperability --------------------------------------------------
    def install_gettext(self, domain: str, localedir: str | Path) -> None:
        """Back this catalogue with standard ``.mo`` files.

        For projects that already run xgettext/msgfmt: the compiled catalogue
        for the active language is read through :mod:`gettext` and merged in,
        so ``t()`` keeps working unchanged.
        """
        import gettext as gettext_module

        try:
            translation = gettext_module.translation(
                domain, localedir=str(localedir), languages=[self._language], fallback=False
            )
        except OSError:
            _log.warning("no gettext catalogue for %r in %s", self._language, localedir)
            return
        catalogue = {
            key: value
            for key, value in translation._catalog.items()  # type: ignore[attr-defined]
            if isinstance(key, str) and key
        }
        self.load(catalogue, language=self._language)

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and self.has(key)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Translations language={self._language!r} loaded={self.languages}>"


#: The catalogue used by :func:`t`; applications normally need only this one.
translations = Translations()


def t(key: str, /, *, count: int | None = None, default: str | None = None, **params: Any) -> str:
    """Translate ``key`` using the global :data:`translations` catalogue."""
    return translations.get(key, count=count, default=default, **params)
