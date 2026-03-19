"""FFmpeg MCP tool modules."""

from .audio import register_audio_tools
from .compose import register_compose_tools
from .overlay import register_overlay_tools
from .video import register_video_tools

__all__ = [
    "register_audio_tools",
    "register_compose_tools",
    "register_overlay_tools",
    "register_video_tools",
]
