"""FFmpeg MCP Server — provides video/audio editing tools via Model Context Protocol."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .tools import (
    register_audio_tools,
    register_compose_tools,
    register_overlay_tools,
    register_video_tools,
)

mcp = FastMCP("ffmpeg-tools")


@mcp.tool()
def health_check() -> str:
    """Returns a simple health status to confirm the server is running."""
    return "Server is healthy!"


# Register all tool modules
register_audio_tools(mcp)
register_video_tools(mcp)
register_overlay_tools(mcp)
register_compose_tools(mcp)


def main():
    """Run the MCP server."""
    mcp.run()
