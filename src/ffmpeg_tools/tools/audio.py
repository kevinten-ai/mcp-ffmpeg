"""Audio processing tools for FFmpeg MCP server."""

from __future__ import annotations

import ffmpeg

from ..utils import decode_ffmpeg_error


def register_audio_tools(mcp):
    """Register all audio-related tools with the MCP server."""

    @mcp.tool()
    def extract_audio_from_video(
        video_path: str, output_audio_path: str, audio_codec: str = "mp3"
    ) -> str:
        """Extracts audio from a video file and saves it.

        Args:
            video_path: The path to the input video file.
            output_audio_path: The path to save the extracted audio file.
            audio_codec: The audio codec to use for the output (e.g., 'mp3', 'aac', 'wav'). Defaults to 'mp3'.
        Returns:
            A status message indicating success or failure.
        """
        try:
            ffmpeg.input(video_path).output(
                output_audio_path, acodec=audio_codec
            ).run(capture_stdout=True, capture_stderr=True)
            return f"Audio extracted successfully to {output_audio_path}"
        except ffmpeg.Error as e:
            return f"Error extracting audio: {decode_ffmpeg_error(e)}"
        except FileNotFoundError:
            return f"Error: Input video file not found at {video_path}"
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"

    @mcp.tool()
    def convert_audio_properties(
        input_audio_path: str,
        output_audio_path: str,
        target_format: str,
        bitrate: str = None,
        sample_rate: int = None,
        channels: int = None,
    ) -> str:
        """Converts audio file format and ALL specified properties like bitrate, sample rate, and channels.

        Args:
            input_audio_path: Path to the source audio file.
            output_audio_path: Path to save the converted audio file.
            target_format: Desired output audio format (e.g., 'mp3', 'wav', 'aac').
            bitrate: Target audio bitrate (e.g., '128k', '192k'). Optional.
            sample_rate: Target audio sample rate in Hz (e.g., 44100, 48000). Optional.
            channels: Number of audio channels (1 for mono, 2 for stereo). Optional.
        Returns:
            A status message indicating success or failure.
        """
        try:
            stream = ffmpeg.input(input_audio_path)
            kwargs = {"format": target_format}
            if bitrate:
                kwargs["audio_bitrate"] = bitrate
            if sample_rate:
                kwargs["ar"] = sample_rate
            if channels:
                kwargs["ac"] = channels

            stream.output(output_audio_path, **kwargs).run(
                capture_stdout=True, capture_stderr=True
            )
            return f"Audio converted successfully to {output_audio_path} with format {target_format} and specified properties."
        except ffmpeg.Error as e:
            return f"Error converting audio properties: {decode_ffmpeg_error(e)}"
        except FileNotFoundError:
            return f"Error: Input audio file not found at {input_audio_path}"
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"

    @mcp.tool()
    def convert_audio_format(
        input_audio_path: str, output_audio_path: str, target_format: str
    ) -> str:
        """Converts an audio file to the specified target format.

        Args:
            input_audio_path: Path to the source audio file.
            output_audio_path: Path to save the converted audio file.
            target_format: Desired output audio format (e.g., 'mp3', 'wav', 'aac').
        Returns:
            A status message indicating success or failure.
        """
        try:
            ffmpeg.input(input_audio_path).output(
                output_audio_path, format=target_format
            ).run(capture_stdout=True, capture_stderr=True)
            return f"Audio format converted to {target_format} and saved to {output_audio_path}"
        except ffmpeg.Error as e:
            return f"Error converting audio format: {decode_ffmpeg_error(e)}"
        except FileNotFoundError:
            return f"Error: Input audio file not found at {input_audio_path}"
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"

    @mcp.tool()
    def set_audio_bitrate(
        input_audio_path: str, output_audio_path: str, bitrate: str
    ) -> str:
        """Sets the bitrate for an audio file.

        Args:
            input_audio_path: Path to the source audio file.
            output_audio_path: Path to save the audio file with the new bitrate.
            bitrate: Target audio bitrate (e.g., '128k', '192k', '320k').
        Returns:
            A status message indicating success or failure.
        """
        try:
            ffmpeg.input(input_audio_path).output(
                output_audio_path, audio_bitrate=bitrate
            ).run(capture_stdout=True, capture_stderr=True)
            return f"Audio bitrate set to {bitrate} and saved to {output_audio_path}"
        except ffmpeg.Error as e:
            return f"Error setting audio bitrate: {decode_ffmpeg_error(e)}"
        except FileNotFoundError:
            return f"Error: Input audio file not found at {input_audio_path}"
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"

    @mcp.tool()
    def set_audio_sample_rate(
        input_audio_path: str, output_audio_path: str, sample_rate: int
    ) -> str:
        """Sets the sample rate for an audio file.

        Args:
            input_audio_path: Path to the source audio file.
            output_audio_path: Path to save the audio file with the new sample rate.
            sample_rate: Target audio sample rate in Hz (e.g., 44100, 48000).
        Returns:
            A status message indicating success or failure.
        """
        try:
            ffmpeg.input(input_audio_path).output(
                output_audio_path, ar=sample_rate
            ).run(capture_stdout=True, capture_stderr=True)
            return f"Audio sample rate set to {sample_rate} Hz and saved to {output_audio_path}"
        except ffmpeg.Error as e:
            return f"Error setting audio sample rate: {decode_ffmpeg_error(e)}"
        except FileNotFoundError:
            return f"Error: Input audio file not found at {input_audio_path}"
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"

    @mcp.tool()
    def set_audio_channels(
        input_audio_path: str, output_audio_path: str, channels: int
    ) -> str:
        """Sets the number of channels for an audio file (1 for mono, 2 for stereo).

        Args:
            input_audio_path: Path to the source audio file.
            output_audio_path: Path to save the audio file with the new channel layout.
            channels: Number of audio channels (1 for mono, 2 for stereo).
        Returns:
            A status message indicating success or failure.
        """
        try:
            ffmpeg.input(input_audio_path).output(
                output_audio_path, ac=channels
            ).run(capture_stdout=True, capture_stderr=True)
            return f"Audio channels set to {channels} and saved to {output_audio_path}"
        except ffmpeg.Error as e:
            return f"Error setting audio channels: {decode_ffmpeg_error(e)}"
        except FileNotFoundError:
            return f"Error: Input audio file not found at {input_audio_path}"
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"
