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

from ..log import get_logger
from .formatting import (
    Localized,
    format_currency,
    format_date,
    format_datetime,
    format_number,
    format_percent,
    format_time,
    supported_format_languages,
)

__all__ = [
    "Translations",
    "translations",
    "t",
    "device_language",
    "normalise_language",
    "plural_category",
    "format_number",
    "format_percent",
    "format_currency",
    "format_date",
    "format_time",
    "format_datetime",
    "supported_format_languages",
]

_log = get_logger("i18n")

#: Languages where "one" covers 1 only and everything else is plural.
_DEFAULT_PLURAL_KEYS = ("one", "other")


# CLDR cardinal plural rules for whole numbers, keyed by base language. The
# category depends on the LANGUAGE, not on which forms a catalogue happens to
# contain: Polish 21 is "many" (21 plików), Ukrainian 21 is "one" (21 файл).
def _east_slavic(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "one"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "few"
    return "many"


def _south_slavic(n: int) -> str:
    category = _east_slavic(n)
    return "other" if category == "many" else category


def _polish(n: int) -> str:
    if n == 1:
        return "one"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "few"
    return "many"


def _czech(n: int) -> str:
    return "one" if n == 1 else "few" if 2 <= n <= 4 else "other"


def _lithuanian(n: int) -> str:
    if n % 10 == 1 and not 11 <= n % 100 <= 19:
        return "one"
    if 2 <= n % 10 <= 9 and not 11 <= n % 100 <= 19:
        return "few"
    return "other"


def _latvian(n: int) -> str:
    if n % 10 == 0 or 11 <= n % 100 <= 19:
        return "zero"
    return "one" if n % 10 == 1 and n % 100 != 11 else "other"


def _romanian(n: int) -> str:
    if n == 1:
        return "one"
    return "few" if n == 0 or 2 <= n % 100 <= 19 else "other"


def _slovenian(n: int) -> str:
    return {1: "one", 2: "two", 3: "few", 4: "few"}.get(n % 100, "other")


def _arabic(n: int) -> str:
    if n in (0, 1, 2):
        return ("zero", "one", "two")[n]
    if 3 <= n % 100 <= 10:
        return "few"
    return "many" if 11 <= n % 100 <= 99 else "other"


def _hebrew(n: int) -> str:
    return "one" if n == 1 else "two" if n == 2 else "other"


def _irish(n: int) -> str:
    if n in (1, 2):
        return ("one", "two")[n - 1]
    return "few" if 3 <= n <= 6 else "many" if 7 <= n <= 10 else "other"


def _welsh(n: int) -> str:
    return {0: "zero", 1: "one", 2: "two", 3: "few", 6: "many"}.get(n, "other")


def _zero_or_one(n: int) -> str:
    return "one" if n in (0, 1) else "other"


def _icelandic(n: int) -> str:
    return "one" if n % 10 == 1 and n % 100 != 11 else "other"


def _no_plural(n: int) -> str:
    return "other"


def _english(n: int) -> str:
    return "one" if n == 1 else "other"


_PLURAL_RULES: dict[str, Callable[[int], str]] = {
    **dict.fromkeys(("uk", "ru", "be"), _east_slavic),
    **dict.fromkeys(("hr", "sr", "bs", "sh"), _south_slavic),
    "pl": _polish,
    **dict.fromkeys(("cs", "sk"), _czech),
    "lt": _lithuanian,
    "lv": _latvian,
    **dict.fromkeys(("ro", "mo"), _romanian),
    "sl": _slovenian,
    "ar": _arabic,
    **dict.fromkeys(("he", "iw"), _hebrew),
    "ga": _irish,
    "cy": _welsh,
    **dict.fromkeys(("fr", "pt", "hi", "bn", "fa", "gu", "kn", "mr", "zu", "am"), _zero_or_one),
    **dict.fromkeys(("is", "mk"), _icelandic),
    **dict.fromkeys(
        ("zh", "ja", "ko", "vi", "th", "id", "ms", "lo", "my", "km", "yue"), _no_plural
    ),
}


def plural_category(count: float, language: str) -> str:
    """The CLDR plural category (zero/one/two/few/many/other) of ``count``.

    Languages without a rule here use the English one. Fractions are
    "other" (the category every one of these languages uses for them, bar a
    few "many" cases that catalogues rarely distinguish).
    """
    if isinstance(count, float) and not count.is_integer():
        return "other"
    rule = _PLURAL_RULES.get(normalise_language(language).split("-")[0], _english)
    return rule(abs(int(count)))


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

    def load_dict(self, catalogues: Mapping[str, Mapping[str, Any]]) -> tuple[str, ...]:
        """Load multiple language catalogues from a dict.

        Convenience method for in-code translations without external files::

            translations.load_dict({
                "en": {"greeting": "Hello"},
                "uk": {"greeting": "Привіт"},
            })

        Returns the normalised language tags that were loaded.
        """
        if not isinstance(catalogues, Mapping):
            raise TypeError(
                f"catalogues must be a mapping, got {type(catalogues).__name__!r}"
            )
        loaded: list[str] = []
        for lang, messages in catalogues.items():
            if not isinstance(messages, Mapping):
                raise TypeError(
                    f"messages for {lang!r} must be mapping, "
                    f"got {type(messages).__name__!r}"
                )
            self.load(messages, language=lang)
            loaded.append(normalise_language(lang))
        return tuple(loaded)

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
        return self._lookup(key, language)[0]

    def _lookup(self, key: str, language: str | None) -> tuple[Any, str]:
        """The entry for ``key`` and the language of the catalogue it came from."""
        requested = normalise_language(language or self._language)
        for tag in self._chain(requested):
            catalogue = self._catalogues.get(tag)
            if catalogue is not None and key in catalogue:
                return catalogue[key], tag
        return None, requested

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
        entry, found_in = self._lookup(key, language)
        if entry is None:
            if key not in self._missing:
                self._missing.add(key)
                _log.warning("missing translation for %r in %r", key, self._language)
            entry = key if default is None else default

        if isinstance(entry, Mapping):
            entry = self._plural(entry, count, found_in)

        text = str(entry)
        if count is not None:
            params.setdefault("count", count)
        if not params:
            return text
        # Parameters are wrapped so a catalogue can ask for locale formats:
        # "{sum:currency:UAH}", "{day:date:long}", "{n:number:2}". The formats
        # follow the language of the catalogue the entry came from.
        wrapped = {name: Localized(value, found_in) for name, value in params.items()}
        try:
            return text.format(**wrapped)
        except (KeyError, IndexError, ValueError, TypeError):
            # A malformed placeholder must not take the screen down.
            _log.warning("could not interpolate %r with %r", key, sorted(params))
            return text

    def _plural(self, forms: Mapping[str, Any], count: int | None, language: str = "en") -> Any:
        """Pick the plural form of ``count`` by the CLDR rule of ``language``.

        ``language`` is the catalogue the entry was found in, so a key that
        falls back to the default language is also pluralised by its rule.
        An explicit ``zero`` form is honoured for 0 in every language. When
        the catalogue lacks the category, ``other`` is used, then ``many``.
        """
        if count is None:
            return forms.get("other") or next(iter(forms.values()), "")
        if count == 0 and "zero" in forms:
            return forms["zero"]
        category = plural_category(count, language)
        for key in (category, "other", "many", *_DEFAULT_PLURAL_KEYS):
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
