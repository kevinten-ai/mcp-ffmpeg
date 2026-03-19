from . import server


def main():
    """Main entry point for the FFmpeg MCP server."""
    server.main()


__all__ = ["main", "server"]
