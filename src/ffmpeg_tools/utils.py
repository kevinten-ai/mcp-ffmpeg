"""Shared utility functions for FFmpeg MCP tools."""

from __future__ import annotations

import os

import ffmpeg


def run_ffmpeg_with_fallback(
    input_path: str,
    output_path: str,
    primary_kwargs: dict,
    fallback_kwargs: dict,
) -> str:
    """Run ffmpeg command with primary kwargs, falling back to other kwargs on error."""
    try:
        ffmpeg.input(input_path).output(output_path, **primary_kwargs).run(
            capture_stdout=True, capture_stderr=True
        )
        return f"Operation successful (primary method) and saved to {output_path}"
    except ffmpeg.Error as e_primary:
        try:
            ffmpeg.input(input_path).output(output_path, **fallback_kwargs).run(
                capture_stdout=True, capture_stderr=True
            )
            return f"Operation successful (fallback method) and saved to {output_path}"
        except ffmpeg.Error as e_fallback:
            err_primary = e_primary.stderr.decode("utf8") if e_primary.stderr else str(e_primary)
            err_fallback = e_fallback.stderr.decode("utf8") if e_fallback.stderr else str(e_fallback)
            return f"Error. Primary method failed: {err_primary}. Fallback method also failed: {err_fallback}"
    except FileNotFoundError:
        return f"Error: Input file not found at {input_path}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"


def parse_time_to_seconds(time_str: str | int | float) -> float:
    """Convert HH:MM:SS.mmm or seconds string to float seconds."""
    if isinstance(time_str, (int, float)):
        return float(time_str)
    if ":" in time_str:
        parts = time_str.split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        else:
            raise ValueError(f"Invalid time format: {time_str}")
    return float(time_str)


def get_media_properties(media_path: str) -> dict:
    """Probe media file and return key properties."""
    try:
        probe = ffmpeg.probe(media_path)
        video_info = next(
            (s for s in probe["streams"] if s["codec_type"] == "video"), None
        )
        audio_info = next(
            (s for s in probe["streams"] if s["codec_type"] == "audio"), None
        )

        props = {
            "duration": float(probe["format"].get("duration", 0.0)),
            "has_video": video_info is not None,
            "has_audio": audio_info is not None,
            "width": int(video_info["width"]) if video_info and "width" in video_info else 0,
            "height": int(video_info["height"]) if video_info and "height" in video_info else 0,
            "avg_fps": 0,
            "sample_rate": int(audio_info["sample_rate"]) if audio_info and "sample_rate" in audio_info else 44100,
            "channels": int(audio_info["channels"]) if audio_info and "channels" in audio_info else 2,
            "channel_layout": audio_info.get("channel_layout", "stereo") if audio_info else "stereo",
        }

        if (
            video_info
            and "avg_frame_rate" in video_info
            and video_info["avg_frame_rate"] != "0/0"
        ):
            num, den = map(int, video_info["avg_frame_rate"].split("/"))
            props["avg_fps"] = num / den if den > 0 else 30
        else:
            props["avg_fps"] = 30

        return props
    except ffmpeg.Error as e:
        raise RuntimeError(
            f"Error probing file {media_path}: {e.stderr.decode('utf8') if e.stderr else str(e)}"
        )
    except Exception as e:
        raise RuntimeError(f"Unexpected error probing file {media_path}: {str(e)}")


def prepare_clip_for_concat(
    source_path: str,
    start_time_sec: float,
    end_time_sec: float,
    target_props: dict,
    temp_dir: str,
    segment_index: int,
) -> str:
    """Prepare a clip segment (trim, scale, set common properties) for concatenation.

    Returns path to the temporary processed clip.
    """
    try:
        temp_output_path = os.path.join(temp_dir, f"segment_{segment_index}.mp4")
        input_stream = ffmpeg.input(source_path, ss=start_time_sec, to=end_time_sec)

        processed_video = None
        processed_audio = None

        if target_props["has_video"]:
            v = input_stream.video
            v = v.filter(
                "scale",
                width=str(target_props["width"]),
                height=str(target_props["height"]),
                force_original_aspect_ratio="decrease",
            )
            v = v.filter(
                "pad",
                width=str(target_props["width"]),
                height=str(target_props["height"]),
                x="(ow-iw)/2",
                y="(oh-ih)/2",
                color="black",
            )
            v = v.filter("setsar", "1/1")
            v = v.filter("setpts", "PTS-STARTPTS")
            processed_video = v

        if target_props["has_audio"]:
            a = input_stream.audio
            a = a.filter("asetpts", "PTS-STARTPTS")
            a = a.filter(
                "aformat",
                sample_fmts="s16",
                sample_rates=str(target_props["sample_rate"]),
                channel_layouts=target_props["channel_layout"],
            )
            processed_audio = a

        output_params = {
            "vcodec": "libx264",
            "pix_fmt": "yuv420p",
            "r": target_props["avg_fps"],
            "acodec": "aac",
            "ar": target_props["sample_rate"],
            "ac": target_props["channels"],
            "strict": "-2",
        }

        streams = []
        if processed_video:
            streams.append(processed_video)
        if processed_audio:
            streams.append(processed_audio)

        if not streams:
            raise ValueError(
                f"No video or audio streams to process for segment {segment_index} from {source_path}"
            )

        ffmpeg.output(*streams, temp_output_path, **output_params).run(
            capture_stdout=True, capture_stderr=True
        )
        return temp_output_path

    except ffmpeg.Error as e:
        err_msg = e.stderr.decode("utf8") if e.stderr else str(e)
        raise RuntimeError(
            f"Error preparing segment {segment_index} from {source_path}: {err_msg}"
        )
    except Exception as e:
        raise RuntimeError(
            f"Unexpected error preparing segment {segment_index} from {source_path}: {str(e)}"
        )


def decode_ffmpeg_error(e: ffmpeg.Error) -> str:
    """Extract readable error message from ffmpeg.Error."""
    return e.stderr.decode("utf8") if e.stderr else str(e)
