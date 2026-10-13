"""Shadow sinks."""
from ai.shadow.sinks.base import ShadowSink
from ai.shadow.sinks.jsonl import JsonlShadowSink
from ai.shadow.sinks.sqlite import SqliteShadowSink

__all__ = ["ShadowSink", "JsonlShadowSink", "SqliteShadowSink"]
