"""AndroidManifest.xml generation.

Built with :mod:`xml.etree` rather than string templates: escaping is handled
for us and the result is guaranteed to be well-formed XML.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from xml.dom import minidom

from ..core.api.permissions import normalize
from ..core.config import ProjectConfig

__all__ = ["build_manifest", "ManifestBuilder"]

ANDROID_NS = "http://schemas.android.com/apk/res/android"

_ORIENTATION_MAP = {
    "portrait": "portrait",
    "landscape": "landscape",
    "sensor": "sensor",
    "user": "user",
}


class ManifestBuilder:
    """Turns a :class:`~pymobile.core.config.ProjectConfig` into a manifest."""

    def __init__(self, config: ProjectConfig, *, activity: str = "org.kivy.android.PythonActivity"):
        self.config = config
        self.activity = activity

    def _attr(self, element: ET.Element, name: str, value: str) -> None:
        """Set an ``android:`` namespaced attribute."""
        element.set(f"{{{ANDROID_NS}}}{name}", value)

    def build_tree(self) -> ET.Element:
        """Construct the manifest element tree."""
        config = self.config
        # register_namespace makes ElementTree emit the xmlns:android
        # declaration itself; setting it manually would duplicate the attribute.
        ET.register_namespace("android", ANDROID_NS)
        manifest = ET.Element("manifest")
        manifest.set("package", config.package)
        self._attr(manifest, "versionCode", str(config.version_code))
        self._attr(manifest, "versionName", config.version)

        uses_sdk = ET.SubElement(manifest, "uses-sdk")
        self._attr(uses_sdk, "minSdkVersion", str(config.min_sdk))
        self._attr(uses_sdk, "targetSdkVersion", str(config.target_sdk))

        for permission in sorted({normalize(p) for p in config.permissions}):
            node = ET.SubElement(manifest, "uses-permission")
            self._attr(node, "name", permission)

        application = ET.SubElement(manifest, "application")
        self._attr(application, "label", config.name)
        self._attr(application, "icon", "@mipmap/icon")
        self._attr(application, "allowBackup", "true")
        self._attr(application, "hardwareAccelerated", "true")

        activity = ET.SubElement(application, "activity")
        self._attr(activity, "name", self.activity)
        self._attr(activity, "label", config.name)
        self._attr(activity, "exported", "true")
        self._attr(activity, "launchMode", "singleTask")
        self._attr(activity, "screenOrientation", _ORIENTATION_MAP[config.orientation])
        self._attr(
            activity,
            "configChanges",
            "keyboard|keyboardHidden|orientation|screenSize|screenLayout|uiMode",
        )

        intent_filter = ET.SubElement(activity, "intent-filter")
        action = ET.SubElement(intent_filter, "action")
        self._attr(action, "name", "android.intent.action.MAIN")
        category = ET.SubElement(intent_filter, "category")
        self._attr(category, "name", "android.intent.category.LAUNCHER")

        return manifest

    def to_xml(self, *, pretty: bool = True) -> str:
        """Render the manifest as an XML document."""
        raw = ET.tostring(self.build_tree(), encoding="unicode")
        if not pretty:
            return f'<?xml version="1.0" encoding="utf-8"?>\n{raw}'
        parsed = minidom.parseString(raw)
        pretty_xml = parsed.toprettyxml(indent="    ")
        lines = [line for line in pretty_xml.splitlines() if line.strip()]
        return "\n".join(lines) + "\n"


def build_manifest(
    config: ProjectConfig,
    *,
    pretty: bool = True,
    activity: str = "org.kivy.android.PythonActivity",
) -> str:
    """Convenience wrapper around :class:`ManifestBuilder`.

    ``activity`` selects the launcher class; the native backend passes its own.
    """
    return ManifestBuilder(config, activity=activity).to_xml(pretty=pretty)
