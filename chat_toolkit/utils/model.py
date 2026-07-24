from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResourceIndex:
    image: int = 0
    record: int = 0
    video: int = 0


@dataclass
class XmlifyOptions:
    max_forward_depth: int = 0
    indent: str = "  "
    resource_index: ResourceIndex | None = None


@dataclass
class XmlifyContext:
    xml_content: str
    resources: dict[str, dict[str, str]] = field(default_factory=dict)
    files: dict[str, dict[str, Any]] = field(default_factory=dict)
