# mcp-ffmpeg

FFmpeg video/audio editing tools via Model Context Protocol (MCP).

Provides 30+ tools for video processing, audio editing, overlays, transitions, and composition — all accessible to AI assistants through MCP.

## Features

- **Video Processing**: format conversion, resolution scaling, codec switching, frame rate adjustment, bitrate control
- **Audio Processing**: format conversion, bitrate/sample rate/channel adjustments, audio extraction
- **Editing**: trimming, speed changes, aspect ratio conversion, silence removal
- **Overlays**: text overlays with timing, image watermarks, subtitle burning (SRT)
- **Composition**: video concatenation with xfade transitions, B-roll insertion, fade in/out effects

## Quick Start

### Prerequisites

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/download.html)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (recommended)

### Install & Run

```bash
git clone https://github.com/kevinten-ai/mcp-ffmpeg.git
cd mcp-ffmpeg
uv sync
uv run python main.py
```

## MCP Client Configuration

### Claude Code

Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "ffmpeg-tools": {
      "command": "uv",
      "args": ["--directory", "/path/to/mcp-ffmpeg", "run", "python", "main.py"]
    }
  }
}
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ffmpeg-tools": {
      "command": "uv",
      "args": ["--directory", "/path/to/mcp-ffmpeg", "run", "python", "main.py"]
    }
  }
}
```

## Available Tools

### Video
`trim_video` `convert_video_format` `convert_video_properties` `change_aspect_ratio` `set_video_resolution` `set_video_codec` `set_video_bitrate` `set_video_frame_rate` `change_video_speed`

### Audio
`extract_audio_from_video` `convert_audio_format` `convert_audio_properties` `set_audio_bitrate` `set_audio_sample_rate` `set_audio_channels`

### Video Audio Track
`set_video_audio_track_codec` `set_video_audio_track_bitrate` `set_video_audio_track_sample_rate` `set_video_audio_track_channels`

### Overlays
`add_text_overlay` `add_image_overlay` `add_subtitles`

### Composition
`concatenate_videos` `add_b_roll` `add_basic_transitions` `remove_silence`

### System
`health_check`

## Project Structure

```
mcp-ffmpeg/
├── main.py                        # Entry point
├── pyproject.toml                 # Project config & dependencies
├── src/ffmpeg_tools/
│   ├── __init__.py
│   ├── server.py                  # MCP server setup & tool registration
│   ├── utils.py                   # Shared utilities (probe, clip prep, etc.)
│   └── tools/
│       ├── audio.py               # Audio processing tools
│       ├── video.py               # Video processing tools
│       ├── overlay.py             # Text/image/subtitle overlay tools
│       └── compose.py             # Concatenation, B-roll, transitions
└── tests/
    ├── test_video_functions.py    # Test suite
    └── sample_files/              # Test media files
```

## Testing

```bash
uv run pytest tests/ -v
```

## License

MIT License — see [LICENSE](LICENSE) for details.

Based on [video-audio-mcp](https://github.com/misbahsy/video-audio-mcp) by misbahsy.
