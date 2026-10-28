import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import config


class ParameterMetadataStore:
    def __init__(self):
        self.path = Path(config.PARAMETER_METADATA_PATH)
        self.url = getattr(config, "PARAMETER_METADATA_URL", "")
        self._metadata = None
        self._loaded_at = 0.0

    def enrich(self, parameters):
        metadata = self.load()
        enriched = []
        for param in parameters or []:
            item = dict(param)
            meta = metadata.get(str(item.get("name", "")), {})
            if meta:
                item.setdefault("display_name", meta.get("display_name", ""))
                item.setdefault("description", meta.get("description", ""))
                item.setdefault("units", meta.get("units", ""))
                item.setdefault("options", meta.get("options", ""))
                item.setdefault("range", meta.get("range", ""))
                item.setdefault("increment", meta.get("increment", ""))
                item.setdefault("user", meta.get("user", ""))
            enriched.append(item)
        return enriched

    def load(self):
        if self._metadata is not None:
            return self._metadata
        self._ensure_metadata_file()
        self._metadata = self._parse_metadata_file()
        self._loaded_at = time.time()
        return self._metadata

    def _ensure_metadata_file(self):
        if self.path.exists() and self.path.stat().st_size > 1024:
            return
        if not self.url:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urllib.request.urlopen(self.url, timeout=12) as response:
                self.path.write_bytes(response.read())
        except Exception:
            return

    def _parse_metadata_file(self):
        if not self.path.exists():
            return {}

        tree = ET.parse(str(self.path))
        root = tree.getroot()
        sections = list(root)

        def priority(section):
            name = section.tag.lower()
            if name == "libraries":
                return 1
            if name == "arduplane":
                return 3
            return 2

        metadata = {}
        for section in sorted(sections, key=priority):
            for param_node in list(section):
                name = str(param_node.tag or "").strip()
                if not name:
                    continue
                metadata[name] = self._parse_param_node(param_node)
        return metadata

    @staticmethod
    def _parse_param_node(node):
        values = {}
        for child in list(node):
            values[child.tag] = (child.text or "").strip()

        return {
            "display_name": values.get("DisplayName", ""),
            "description": values.get("Description", ""),
            "units": values.get("Units", ""),
            "options": values.get("Values", ""),
            "range": values.get("Range", ""),
            "increment": values.get("Increment", ""),
            "user": values.get("User", ""),
        }


parameter_metadata_store = ParameterMetadataStore()
