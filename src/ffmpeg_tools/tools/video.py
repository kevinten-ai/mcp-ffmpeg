"""Video processing tools for FFmpeg MCP server."""

from __future__ import annotations

import os

import ffmpeg

from ..utils import decode_ffmpeg_error, run_ffmpeg_with_fallback


def register_video_tools(mcp):
    """Register all video-related tools with the MCP server."""

    @mcp.tool()
    def trim_video(
        video_path: str, output_video_path: str, start_time: str, end_time: str
    ) -> str:
        """Trims a video to the specified start and end times.

        Args:
            video_path: The path to the input video file.
            output_video_path: The path to save the trimmed video file.
            start_time: The start time for trimming (HH:MM:SS or seconds).
            end_time: The end time for trimming (HH:MM:SS or seconds).
        Returns:
            A status message indicating success or failure.
        """
        try:
            input_stream = ffmpeg.input(video_path, ss=start_time, to=end_time)
            input_stream.output(output_video_path, c="copy").run(
                capture_stdout=True, capture_stderr=True
            )
            return f"Video trimmed successfully (codec copy) to {output_video_path}"
        except ffmpeg.Error as e:
            error_copy = decode_ffmpeg_error(e)
            try:
                ffmpeg.input(video_path, ss=start_time, to=end_time).output(
                    output_video_path
                ).run(capture_stdout=True, capture_stderr=True)
                return f"Video trimmed successfully (re-encoded) to {output_video_path}"
            except ffmpeg.Error as e2:
                return f"Error trimming video. Copy attempt: {error_copy}. Re-encode attempt: {decode_ffmpeg_error(e2)}"
        except FileNotFoundError:
            return f"Error: Input video file not found at {video_path}"
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"

    @mcp.tool()
    def convert_video_properties(
        input_video_path: str,
        output_video_path: str,
        target_format: str,
        resolution: str = None,
        video_codec: str = None,
        video_bitrate: str = None,
        frame_rate: int = None,
        audio_codec: str = None,
        audio_bitrate: str = None,
        audio_sample_rate: int = None,
        audio_channels: int = None,
    ) -> str:
        """Converts video file format and ALL specified properties like resolution, codecs, bitrates, and frame rate.

        Args:
            input_video_path: Path to the source video file.
            output_video_path: Path to save the converted video file.
            target_format: Desired output video format (e.g., 'mp4', 'mov', 'avi').
            resolution: Target resolution (e.g., '1920x1080' or '720' for height). Optional.
            video_codec: Target video codec (e.g., 'libx264', 'libx265'). Optional.
            video_bitrate: Target video bitrate (e.g., '1M', '2500k'). Optional.
            frame_rate: Target frame rate (e.g., 24, 30, 60). Optional.
            audio_codec: Target audio codec (e.g., 'aac', 'mp3'). Optional.
            audio_bitrate: Target audio bitrate (e.g., '128k', '192k'). Optional.
            audio_sample_rate: Target audio sample rate in Hz (e.g., 44100, 48000). Optional.
            audio_channels: Number of audio channels (1 for mono, 2 for stereo). Optional.
        Returns:
            A status message indicating success or failure.
        """
        try:
            stream = ffmpeg.input(input_video_path)
            kwargs = {"format": target_format}
            vf_filters = []

            if resolution and resolution.lower() != "preserve":
                if "x" in resolution:
                    vf_filters.append(f"scale={resolution}")
                else:
                    vf_filters.append(f"scale=-2:{resolution}")

            if vf_filters:
                kwargs["vf"] = ",".join(vf_filters)
            if video_codec:
                kwargs["vcodec"] = video_codec
            if video_bitrate:
                kwargs["video_bitrate"] = video_bitrate
            if frame_rate:
                kwargs["r"] = frame_rate
            if audio_codec:
                kwargs["acodec"] = audio_codec
            if audio_bitrate:
                kwargs["audio_bitrate"] = audio_bitrate
            if audio_sample_rate:
                kwargs["ar"] = audio_sample_rate
            if audio_channels:
                kwargs["ac"] = audio_channels

            stream.output(output_video_path, **kwargs).run(
                capture_stdout=True, capture_stderr=True
            )
            return f"Video converted successfully to {output_video_path} with format {target_format} and specified properties."
        except ffmpeg.Error as e:
            return f"Error converting video properties: {decode_ffmpeg_error(e)}"
        except FileNotFoundError:
            return f"Error: Input video file not found at {input_video_path}"
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"

    @mcp.tool()
    def change_aspect_ratio(
        video_path: str,
        output_video_path: str,
        target_aspect_ratio: str,
        resize_mode: str = "pad",
        padding_color: str = "black",
    ) -> str:
        """Changes the aspect ratio of a video, using padding or cropping.

        Args:
            video_path: Path to the input video file.
            output_video_path: Path to save the video with the new aspect ratio.
            target_aspect_ratio: Target aspect ratio (e.g., '16:9', '4:3', '1:1').
            resize_mode: 'pad' to add letterbox/pillarbox, or 'crop' to crop. Defaults to 'pad'.
            padding_color: Color for padding (e.g., 'black', 'white'). Defaults to 'black'.
        Returns:
            A status message indicating success or failure.
        """
        try:
            probe = ffmpeg.probe(video_path)
            video_stream_info = next(
                (s for s in probe["streams"] if s["codec_type"] == "video"), None
            )
            if not video_stream_info:
                return "Error: No video stream found in the input file."

            original_width = int(video_stream_info["width"])
            original_height = int(video_stream_info["height"])
            num, den = map(int, target_aspect_ratio.split(":"))
            target_ar = num / den
            original_ar = original_width / original_height

            if resize_mode == "pad":
                if abs(original_ar - target_ar) < 1e-4:
                    try:
                        ffmpeg.input(video_path).output(output_video_path, c="copy").run(
                            capture_stdout=True, capture_stderr=True
                        )
                        return f"Video aspect ratio already matches. Copied to {output_video_path}."
                    except ffmpeg.Error:
                        ffmpeg.input(video_path).output(output_video_path).run(
                            capture_stdout=True, capture_stderr=True
                        )
                        return f"Video aspect ratio already matches. Re-encoded to {output_video_path}."

                if original_ar > target_ar:
                    final_w = int(original_height * target_ar)
                    final_h = original_height
                else:
                    final_w = original_width
                    final_h = int(original_width / target_ar)
                vf_filter = (
                    f"scale={final_w}:{final_h}:force_original_aspect_ratio=decrease,"
                    f"pad={final_w}:{final_h}:(ow-iw)/2:(oh-ih)/2:{padding_color}"
                )

            elif resize_mode == "crop":
                if abs(original_ar - target_ar) < 1e-4:
                    try:
                        ffmpeg.input(video_path).output(output_video_path, c="copy").run(
                            capture_stdout=True, capture_stderr=True
                        )
                        return f"Video aspect ratio already matches. Copied to {output_video_path}."
                    except ffmpeg.Error:
                        ffmpeg.input(video_path).output(output_video_path).run(
                            capture_stdout=True, capture_stderr=True
                        )
                        return f"Video aspect ratio already matches. Re-encoded to {output_video_path}."

                if original_ar > target_ar:
                    new_width = int(original_height * target_ar)
                    vf_filter = f"crop={new_width}:{original_height}:(iw-{new_width})/2:0"
                else:
                    new_height = int(original_width / target_ar)
                    vf_filter = f"crop={original_width}:{new_height}:0:(ih-{new_height})/2"
            else:
                return f"Error: Invalid resize_mode '{resize_mode}'. Must be 'pad' or 'crop'."

            try:
                ffmpeg.input(video_path).output(
                    output_video_path, vf=vf_filter, acodec="copy"
                ).run(capture_stdout=True, capture_stderr=True)
                return f"Video aspect ratio changed (audio copy) to {target_aspect_ratio} using {resize_mode}. Saved to {output_video_path}"
            except ffmpeg.Error as e_acopy:
                try:
                    ffmpeg.input(video_path).output(
                        output_video_path, vf=vf_filter
                    ).run(capture_stdout=True, capture_stderr=True)
                    return f"Video aspect ratio changed (audio re-encoded) to {target_aspect_ratio} using {resize_mode}. Saved to {output_video_path}"
                except ffmpeg.Error as e_recode:
                    return (
                        f"Error changing aspect ratio. Audio copy attempt failed: {decode_ffmpeg_error(e_acopy)}. "
                        f"Full re-encode attempt also failed: {decode_ffmpeg_error(e_recode)}."
                    )

        except ffmpeg.Error as e:
            return f"Error changing aspect ratio: {decode_ffmpeg_error(e)}"
        except FileNotFoundError:
            return f"Error: Input video file not found at {video_path}"
        except ValueError:
            return "Error: Invalid target_aspect_ratio format. Expected 'num:den' (e.g., '16:9')."
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"

    @mcp.tool()
    def convert_video_format(
        input_video_path: str, output_video_path: str, target_format: str
    ) -> str:
        """Converts a video file to the specified target format, attempting to copy codecs first.

        Args:
            input_video_path: Path to the source video file.
            output_video_path: Path to save the converted video file.
            target_format: Desired output video format (e.g., 'mp4', 'mov', 'avi').
        Returns:
            A status message indicating success or failure.
        """
        return run_ffmpeg_with_fallback(
            input_video_path,
            output_video_path,
            {"format": target_format, "vcodec": "copy", "acodec": "copy"},
            {"format": target_format},
        )

    @mcp.tool()
    def set_video_resolution(
        input_video_path: str, output_video_path: str, resolution: str
    ) -> str:
        """Sets the resolution of a video, attempting to copy the audio stream.

        Args:
            input_video_path: Path to the source video file.
            output_video_path: Path to save the video with the new resolution.
            resolution: Target video resolution (e.g., '1920x1080', '1280x720', or '720' for height).
        Returns:
            A status message indicating success or failure.
        """
        vf = f"scale={resolution}" if "x" in resolution else f"scale=-2:{resolution}"
        return run_ffmpeg_with_fallback(
            input_video_path,
            output_video_path,
            {"vf": vf, "acodec": "copy"},
            {"vf": vf},
        )

    @mcp.tool()
    def set_video_codec(
        input_video_path: str, output_video_path: str, video_codec: str
    ) -> str:
        """Sets the video codec of a video, attempting to copy the audio stream.

        Args:
            input_video_path: Path to the source video file.
            output_video_path: Path to save the video with the new video codec.
            video_codec: Target video codec (e.g., 'libx264', 'libx265', 'vp9').
        Returns:
            A status message indicating success or failure.
        """
        return run_ffmpeg_with_fallback(
            input_video_path,
            output_video_path,
            {"vcodec": video_codec, "acodec": "copy"},
            {"vcodec": video_codec},
        )

    @mcp.tool()
    def set_video_bitrate(
        input_video_path: str, output_video_path: str, video_bitrate: str
    ) -> str:
        """Sets the video bitrate of a video, attempting to copy the audio stream.

        Args:
            input_video_path: Path to the source video file.
            output_video_path: Path to save the video with the new video bitrate.
            video_bitrate: Target video bitrate (e.g., '1M', '2500k').
        Returns:
            A status message indicating success or failure.
        """
        return run_ffmpeg_with_fallback(
            input_video_path,
            output_video_path,
            {"video_bitrate": video_bitrate, "acodec": "copy"},
            {"video_bitrate": video_bitrate},
        )

    @mcp.tool()
    def set_video_frame_rate(
        input_video_path: str, output_video_path: str, frame_rate: int
    ) -> str:
        """Sets the frame rate of a video, attempting to copy the audio stream.

        Args:
            input_video_path: Path to the source video file.
            output_video_path: Path to save the video with the new frame rate.
            frame_rate: Target video frame rate (e.g., 24, 30, 60).
        Returns:
            A status message indicating success or failure.
        """
        return run_ffmpeg_with_fallback(
            input_video_path,
            output_video_path,
            {"r": frame_rate, "acodec": "copy"},
            {"r": frame_rate},
        )

    @mcp.tool()
    def set_video_audio_track_codec(
        input_video_path: str, output_video_path: str, audio_codec: str
    ) -> str:
        """Sets the audio codec of a video's audio track, attempting to copy the video stream.

        Args:
            input_video_path: Path to the source video file.
            output_video_path: Path to save the video with the new audio codec.
            audio_codec: Target audio codec (e.g., 'aac', 'mp3').
        Returns:
            A status message indicating success or failure.
        """
        return run_ffmpeg_with_fallback(
            input_video_path,
            output_video_path,
            {"acodec": audio_codec, "vcodec": "copy"},
            {"acodec": audio_codec},
        )

    @mcp.tool()
    def set_video_audio_track_bitrate(
        input_video_path: str, output_video_path: str, audio_bitrate: str
    ) -> str:
        """Sets the audio bitrate of a video's audio track, attempting to copy the video stream.

        Args:
            input_video_path: Path to the source video file.
            output_video_path: Path to save the video with the new audio bitrate.
            audio_bitrate: Target audio bitrate (e.g., '128k', '192k').
        Returns:
            A status message indicating success or failure.
        """
        return run_ffmpeg_with_fallback(
            input_video_path,
            output_video_path,
            {"audio_bitrate": audio_bitrate, "vcodec": "copy"},
            {"audio_bitrate": audio_bitrate},
        )

    @mcp.tool()
    def set_video_audio_track_sample_rate(
        input_video_path: str, output_video_path: str, audio_sample_rate: int
    ) -> str:
        """Sets the audio sample rate of a video's audio track, attempting to copy the video stream.

        Args:
            input_video_path: Path to the source video file.
            output_video_path: Path to save the video with the new audio sample rate.
            audio_sample_rate: Target audio sample rate in Hz (e.g., 44100, 48000).
        Returns:
            A status message indicating success or failure.
        """
        return run_ffmpeg_with_fallback(
            input_video_path,
            output_video_path,
            {"ar": audio_sample_rate, "vcodec": "copy"},
            {"ar": audio_sample_rate},
        )

    @mcp.tool()
    def set_video_audio_track_channels(
        input_video_path: str, output_video_path: str, audio_channels: int
    ) -> str:
        """Sets the number of audio channels of a video's audio track, attempting to copy the video stream.

        Args:
            input_video_path: Path to the source video file.
            output_video_path: Path to save the video with the new audio channel layout.
            audio_channels: Number of audio channels (1 for mono, 2 for stereo).
        Returns:
            A status message indicating success or failure.
        """
        return run_ffmpeg_with_fallback(
            input_video_path,
            output_video_path,
            {"ac": audio_channels, "vcodec": "copy"},
            {"ac": audio_channels},
        )

    @mcp.tool()
    def change_video_speed(
        video_path: str, output_video_path: str, speed_factor: float
    ) -> str:
        """Changes the playback speed of a video (and its audio).

        Args:
            video_path: Path to the input video file.
            output_video_path: Path to save the speed-adjusted video file.
            speed_factor: The factor by which to change the speed (e.g., 2.0 for 2x speed, 0.5 for half speed).
                          Must be positive.
        Returns:
            A status message indicating success or failure.
        """
        if speed_factor <= 0:
            return "Error: Speed factor must be positive."
        if not os.path.exists(video_path):
            return f"Error: Input video file not found at {video_path}"

        try:
            atempo_value = speed_factor
            atempo_filters = []

            if speed_factor < 0.5:
                while atempo_value < 0.5:
                    atempo_filters.append(0.5)
                    atempo_value *= 2
                if atempo_value < 0.99:
                    atempo_filters.append(atempo_value)
            elif speed_factor > 2.0:
                while atempo_value > 2.0:
                    atempo_filters.append(2.0)
                    atempo_value /= 2
                if atempo_value > 1.01:
                    atempo_filters.append(atempo_value)
            else:
                atempo_filters.append(speed_factor)

            input_stream = ffmpeg.input(video_path)
            video = input_stream.video.setpts(f"{1.0 / speed_factor}*PTS")

            audio = input_stream.audio
            for val in atempo_filters:
                audio = audio.filter("atempo", val)

            ffmpeg.output(video, audio, output_video_path).run(
                capture_stdout=True, capture_stderr=True
            )
            return f"Video speed changed by factor {speed_factor} and saved to {output_video_path}"
        except ffmpeg.Error as e:
            return f"Error changing video speed: {decode_ffmpeg_error(e)}"
        except Exception as e:
            return f"An unexpected error occurred while changing video speed: {str(e)}"
