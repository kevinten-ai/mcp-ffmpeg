"""Composition tools (concatenation, B-roll, transitions, silence removal) for FFmpeg MCP server."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile

import ffmpeg

from ..utils import (
    decode_ffmpeg_error,
    get_media_properties,
    parse_time_to_seconds,
)


def register_compose_tools(mcp):
    """Register all composition-related tools with the MCP server."""

    @mcp.tool()
    def concatenate_videos(
        video_paths: list[str],
        output_video_path: str,
        transition_effect: str = None,
        transition_duration: float = None,
    ) -> str:
        """Concatenates multiple video files into a single output file.
        Supports optional xfade transition when concatenating exactly two videos.

        Args:
            video_paths: A list of paths to the video files to concatenate.
            output_video_path: The path to save the concatenated video file.
            transition_effect: The xfade transition type (e.g., 'dissolve', 'fade', 'wipeleft').
                Only applied if exactly two videos are provided. Defaults to None.
            transition_duration: The duration of the xfade transition in seconds.
                Required if transition_effect is specified.
        Returns:
            A status message indicating success or failure.
        """
        if not video_paths:
            return "Error: No video paths provided for concatenation."
        if len(video_paths) < 1:
            return "Error: At least one video is required."

        if transition_effect and transition_duration is None:
            return "Error: transition_duration is required when transition_effect is specified."
        if transition_effect and transition_duration <= 0:
            return "Error: transition_duration must be positive."

        valid_transitions = {
            "dissolve", "fade", "fadeblack", "fadewhite", "fadegrays", "distance",
            "wipeleft", "wiperight", "wipeup", "wipedown",
            "slideleft", "slideright", "slideup", "slidedown",
            "smoothleft", "smoothright", "smoothup", "smoothdown",
            "circlecrop", "rectcrop", "circleopen", "circleclose",
            "vertopen", "vertclose", "horzopen", "horzclose",
            "diagtl", "diagtr", "diagbl", "diagbr",
            "hlslice", "hrslice", "vuslice", "vdslice",
            "pixelize", "radial", "hblur",
        }
        if transition_effect and transition_effect not in valid_transitions:
            return f"Error: Invalid transition_effect '{transition_effect}'. Valid options: {', '.join(sorted(valid_transitions))}"

        for vp in video_paths:
            if not os.path.exists(vp):
                return f"Error: Input video file not found at {vp}"

        # Single video case
        if len(video_paths) == 1:
            try:
                ffmpeg.input(video_paths[0]).output(
                    output_video_path, vcodec="libx264", acodec="aac"
                ).run(capture_stdout=True, capture_stderr=True)
                return f"Single video processed and saved to {output_video_path}"
            except ffmpeg.Error as e:
                return f"Error processing single video: {decode_ffmpeg_error(e)}"

        # xfade transition for exactly two videos
        if transition_effect and len(video_paths) == 2:
            return _concat_with_xfade(
                video_paths[0], video_paths[1], output_video_path,
                transition_effect, transition_duration,
            )

        if transition_effect and len(video_paths) > 2:
            return f"Error: xfade transition ('{transition_effect}') is currently only supported for exactly two videos. Found {len(video_paths)} videos."

        # Standard concatenation
        return _concat_standard(video_paths, output_video_path)

    @mcp.tool()
    def remove_silence(
        media_path: str,
        output_media_path: str,
        silence_threshold_db: float = -30.0,
        min_silence_duration_ms: int = 500,
    ) -> str:
        """Removes silent segments from an audio or video file.

        Args:
            media_path: Path to the input audio or video file.
            output_media_path: Path to save the media file with silences removed.
            silence_threshold_db: The noise level (in dBFS) below which is considered silence.
            min_silence_duration_ms: Minimum duration (in milliseconds) of silence to be removed.
        Returns:
            A status message indicating success or failure.
        """
        if not os.path.exists(media_path):
            return f"Error: Input media file not found at {media_path}"
        if min_silence_duration_ms <= 0:
            return "Error: Minimum silence duration must be positive."

        min_silence_s = min_silence_duration_ms / 1000.0

        try:
            # Detect silence
            process = (
                ffmpeg.input(media_path)
                .filter("silencedetect", n=f"{silence_threshold_db}dB", d=min_silence_s)
                .output("-", format="null")
                .run_async(pipe_stderr=True)
            )
            _, stderr_bytes = process.communicate()
            stderr_str = stderr_bytes.decode("utf8")

            silence_starts = [float(x) for x in re.findall(r"silence_start: (\d+\.?\d*)", stderr_str)]
            silence_ends = [float(x) for x in re.findall(r"silence_end: (\d+\.?\d*)", stderr_str)]

            if not silence_starts:
                try:
                    ffmpeg.input(media_path).output(output_media_path, c="copy").run(
                        capture_stdout=True, capture_stderr=True
                    )
                    return f"No significant silences detected. Original media copied to {output_media_path}."
                except ffmpeg.Error as e:
                    return f"No significant silences detected, but error copying: {decode_ffmpeg_error(e)}"

            probe = ffmpeg.probe(media_path)
            total_duration = float(probe["format"]["duration"])

            # Build non-silent segments
            sound_segments = []
            current_pos = 0.0
            for i in range(len(silence_starts)):
                start_silence = silence_starts[i]
                end_silence = silence_ends[i] if i < len(silence_ends) else total_duration
                if start_silence > current_pos:
                    sound_segments.append((current_pos, start_silence))
                current_pos = end_silence

            if current_pos < total_duration:
                sound_segments.append((current_pos, total_duration))

            if not sound_segments:
                return "Error: No sound segments were identified to keep."

            # Build select filter expressions
            video_select = "+".join(f"between(t,{s},{e})" for s, e in sound_segments)
            audio_select = "+".join(f"between(t,{s},{e})" for s, e in sound_segments)

            input_media = ffmpeg.input(media_path)
            has_video = any(s["codec_type"] == "video" for s in probe["streams"])
            has_audio = any(s["codec_type"] == "audio" for s in probe["streams"])

            output_streams = []
            if has_video:
                output_streams.append(
                    input_media.video.filter("select", video_select).filter("setpts", "PTS-STARTPTS")
                )
            if has_audio:
                output_streams.append(
                    input_media.audio.filter("aselect", audio_select).filter("asetpts", "PTS-STARTPTS")
                )

            if not output_streams:
                return "Error: The input media does not seem to have video or audio streams."

            ffmpeg.output(*output_streams, output_media_path).run(
                capture_stdout=True, capture_stderr=True
            )
            return f"Silent segments removed. Output saved to {output_media_path}"

        except ffmpeg.Error as e:
            return f"Error removing silence: {decode_ffmpeg_error(e)}"
        except Exception as e:
            return f"An unexpected error occurred while removing silence: {str(e)}"

    @mcp.tool()
    def add_b_roll(
        main_video_path: str, broll_clips: list[dict], output_video_path: str
    ) -> str:
        """Inserts B-roll clips into a main video as overlays.

        Args:
            main_video_path: Path to the main video file.
            broll_clips: A list of dicts, each with keys:
                Required: 'clip_path' (str), 'insert_at_timestamp' (str/float).
                Optional: 'duration' (str/float), 'position' ('fullscreen'|'top-left'|'top-right'|
                'bottom-left'|'bottom-right'|'center'), 'scale' (float),
                'transition_in'/'transition_out' ('fade'), 'transition_duration' (float),
                'audio_mix' (float, 0.0-1.0).
            output_video_path: The path to save the output video.
        Returns:
            A status message indicating success or failure.
        """
        if not os.path.exists(main_video_path):
            return f"Error: Main video file not found at {main_video_path}"
        if not broll_clips:
            try:
                ffmpeg.input(main_video_path).output(output_video_path, c="copy").run(
                    capture_stdout=True, capture_stderr=True
                )
                return f"No B-roll clips provided. Main video copied to {output_video_path}"
            except ffmpeg.Error as e:
                return f"No B-roll clips, but error copying main video: {decode_ffmpeg_error(e)}"

        valid_positions = {"fullscreen", "top-left", "top-right", "bottom-left", "bottom-right", "center"}

        try:
            temp_dir = tempfile.mkdtemp()
            try:
                main_props = get_media_properties(main_video_path)
                if not main_props["has_video"]:
                    return f"Error: Main video {main_video_path} has no video stream."

                main_w = main_props["width"]
                main_h = main_props["height"]

                processed_clips = []
                sorted_clips = sorted(
                    broll_clips,
                    key=lambda x: parse_time_to_seconds(x["insert_at_timestamp"]),
                )

                for i, broll_item in enumerate(sorted_clips):
                    clip_path = broll_item["clip_path"]
                    if not os.path.exists(clip_path):
                        return f"Error: B-roll clip not found at {clip_path}"

                    broll_props = get_media_properties(clip_path)
                    if not broll_props["has_video"]:
                        continue

                    start_time = parse_time_to_seconds(broll_item["insert_at_timestamp"])
                    duration = parse_time_to_seconds(
                        broll_item.get("duration", str(broll_props["duration"]))
                    )
                    position = broll_item.get("position", "fullscreen")

                    if position not in valid_positions:
                        return f"Error: Invalid position '{position}' for B-roll {clip_path}"

                    temp_clip = os.path.join(temp_dir, f"processed_broll_{i}.mp4")
                    scale_factor = broll_item.get("scale", 1.0 if position == "fullscreen" else 0.5)

                    scale_filter_parts = []
                    if position == "fullscreen":
                        scale_filter_parts.append(f"scale={main_w}:{main_h}")
                    else:
                        scale_filter_parts.append(f"scale=iw*{scale_factor}:ih*{scale_factor}")

                    transition_in = broll_item.get("transition_in")
                    transition_out = broll_item.get("transition_out")
                    transition_duration = float(broll_item.get("transition_duration", 0.5))

                    if transition_in == "fade":
                        scale_filter_parts.append(f"fade=t=in:st=0:d={transition_duration}")
                    if transition_out == "fade":
                        fade_out_start = max(0, float(broll_props["duration"]) - transition_duration)
                        scale_filter_parts.append(f"fade=t=out:st={fade_out_start}:d={transition_duration}")

                    try:
                        subprocess.run(
                            [
                                "ffmpeg", "-i", clip_path,
                                "-vf", ",".join(scale_filter_parts),
                                "-c:v", "libx264", "-c:a", "aac", "-y", temp_clip,
                            ],
                            check=True, capture_output=True,
                        )
                    except subprocess.CalledProcessError as e:
                        return f"Error processing B-roll {i}: {e.stderr.decode('utf8') if e.stderr else str(e)}"

                    # Calculate overlay coordinates
                    pos_map = {
                        "top-left": ("10", "10"),
                        "top-right": ("W-w-10", "10"),
                        "bottom-left": ("10", "H-h-10"),
                        "bottom-right": ("W-w-10", "H-h-10"),
                        "center": ("(W-w)/2", "(H-h)/2"),
                        "fullscreen": ("0", "0"),
                    }
                    ox, oy = pos_map.get(position, ("0", "0"))

                    processed_clips.append({
                        "path": temp_clip,
                        "start_time": start_time,
                        "duration": duration,
                        "overlay_x": ox,
                        "overlay_y": oy,
                    })

                if not processed_clips:
                    try:
                        shutil.copy(main_video_path, output_video_path)
                        return f"No valid B-roll clips to overlay. Main video copied to {output_video_path}"
                    except Exception as e:
                        return f"No valid B-roll clips, but error copying main video: {str(e)}"

                # Build filter complex
                filter_parts = []
                main_overlay = "[0:v]"

                for i, clip in enumerate(processed_clips):
                    overlay_index = i + 1
                    end_time = clip["start_time"] + clip["duration"]
                    overlay_filter = (
                        f"{main_overlay}[{overlay_index}:v]overlay="
                        f"x={clip['overlay_x']}:y={clip['overlay_y']}:"
                        f"enable='between(t,{clip['start_time']},{end_time})'"
                    )

                    if i < len(processed_clips) - 1:
                        label = f"[v{i}]"
                        overlay_filter += label
                        main_overlay = label
                    else:
                        overlay_filter += "[v]"

                    filter_parts.append(overlay_filter)

                filter_complex = ";".join(filter_parts)

                input_files = ["-i", main_video_path]
                for clip in processed_clips:
                    input_files.extend(["-i", clip["path"]])

                audio_output = ["-map", "0:a"] if main_props["has_audio"] else []

                cmd = [
                    "ffmpeg", *input_files,
                    "-filter_complex", filter_complex,
                    "-map", "[v]", *audio_output,
                    "-c:v", "libx264", "-c:a", "aac", "-y",
                    output_video_path,
                ]

                try:
                    subprocess.run(cmd, check=True, capture_output=True)
                    return f"B-roll clips added successfully as overlays. Output at {output_video_path}"
                except subprocess.CalledProcessError as e:
                    return f"Error in final B-roll composition: {e.stderr.decode('utf8') if e.stderr else str(e)}"

            finally:
                shutil.rmtree(temp_dir)

        except ffmpeg.Error as e:
            return f"Error adding B-roll overlays: {decode_ffmpeg_error(e)}"
        except ValueError as e:
            return f"Error with input values (e.g., time format): {str(e)}"
        except RuntimeError as e:
            return f"Runtime error during B-roll processing: {str(e)}"
        except Exception as e:
            return f"An unexpected error occurred in add_b_roll: {str(e)}"

    @mcp.tool()
    def add_basic_transitions(
        video_path: str,
        output_video_path: str,
        transition_type: str,
        duration_seconds: float,
    ) -> str:
        """Adds basic fade transitions to the beginning or end of a video.

        Args:
            video_path: Path to the input video file.
            output_video_path: Path to save the video with the transition.
            transition_type: Type of transition. Options: 'fade_in', 'fade_out'.
            duration_seconds: Duration of the fade effect in seconds.
        Returns:
            A status message indicating success or failure.
        """
        if not os.path.exists(video_path):
            return f"Error: Input video file not found at {video_path}"
        if duration_seconds <= 0:
            return "Error: Transition duration must be positive."

        try:
            props = get_media_properties(video_path)
            total_duration = props["duration"]

            if duration_seconds > total_duration:
                return f"Error: Transition duration ({duration_seconds}s) cannot exceed video duration ({total_duration}s)."

            input_stream = ffmpeg.input(video_path)
            video_stream = input_stream.video
            audio_stream = input_stream.audio

            if transition_type in ("fade_in", "crossfade_from_black"):
                processed_video = video_stream.filter(
                    "fade", type="in", start_time=0, duration=duration_seconds
                )
            elif transition_type in ("fade_out", "crossfade_to_black"):
                fade_start = total_duration - duration_seconds
                processed_video = video_stream.filter(
                    "fade", type="out", start_time=fade_start, duration=duration_seconds
                )
            else:
                return f"Error: Unsupported transition_type '{transition_type}'. Supported: 'fade_in', 'fade_out'."

            output_streams = []
            if props["has_video"]:
                output_streams.append(processed_video)
            if props["has_audio"]:
                output_streams.append(audio_stream)

            if not output_streams:
                return "Error: No suitable video or audio streams found to apply transition."

            try:
                ffmpeg.output(*output_streams, output_video_path, acodec="copy").run(
                    capture_stdout=True, capture_stderr=True
                )
                return f"Transition '{transition_type}' applied successfully (audio copied). Output: {output_video_path}"
            except ffmpeg.Error as e_acopy:
                try:
                    ffmpeg.output(*output_streams, output_video_path).run(
                        capture_stdout=True, capture_stderr=True
                    )
                    return f"Transition '{transition_type}' applied successfully (audio re-encoded). Output: {output_video_path}"
                except ffmpeg.Error as e_recode:
                    return (
                        f"Error applying transition. Audio copy failed: {decode_ffmpeg_error(e_acopy)}. "
                        f"Full re-encode failed: {decode_ffmpeg_error(e_recode)}."
                    )

        except ffmpeg.Error as e:
            return f"Error applying basic transition: {decode_ffmpeg_error(e)}"
        except ValueError as e:
            return f"Error with input values: {str(e)}"
        except RuntimeError as e:
            return f"Runtime error during transition processing: {str(e)}"
        except Exception as e:
            return f"An unexpected error occurred in add_basic_transitions: {str(e)}"


def _concat_with_xfade(
    video1_path: str,
    video2_path: str,
    output_path: str,
    transition_effect: str,
    transition_duration: float,
) -> str:
    """Concatenate two videos with an xfade transition."""
    temp_dir = tempfile.mkdtemp()
    try:
        props1 = get_media_properties(video1_path)
        props2 = get_media_properties(video2_path)

        if not props1["has_video"] or not props2["has_video"]:
            return "Error: xfade transition requires both inputs to be videos."
        if transition_duration >= props1["duration"]:
            return f"Error: Transition duration ({transition_duration}s) cannot be equal or longer than the first video's duration ({props1['duration']})."

        has_audio = props1["has_audio"] and props2["has_audio"]

        target_w = max(props1["width"], props2["width"], 640)
        target_h = max(props1["height"], props2["height"], 360)
        target_fps = max(props1["avg_fps"], props2["avg_fps"], 30)
        if target_fps <= 0:
            target_fps = 30

        # Normalize both videos
        norm_paths = []
        for i, vpath in enumerate([video1_path, video2_path]):
            norm_path = os.path.join(temp_dir, f"norm_video{i}.mp4")
            try:
                subprocess.run(
                    [
                        "ffmpeg", "-i", vpath,
                        "-vf", f"scale={target_w}:{target_h}",
                        "-r", str(target_fps),
                        "-c:v", "libx264", "-c:a", "aac", "-y", norm_path,
                    ],
                    check=True, capture_output=True,
                )
            except subprocess.CalledProcessError as e:
                return f"Error normalizing video {i}: {e.stderr.decode('utf8') if e.stderr else str(e)}"
            norm_paths.append(norm_path)

        norm_props1 = get_media_properties(norm_paths[0])
        if transition_duration >= norm_props1["duration"]:
            return f"Error: Transition duration ({transition_duration}s) is too long for the normalized first video ({norm_props1['duration']}s)."

        offset = norm_props1["duration"] - transition_duration
        filter_complex = f"[0:v][1:v]xfade=transition={transition_effect}:duration={transition_duration}:offset={offset}"

        cmd = ["ffmpeg", "-i", norm_paths[0], "-i", norm_paths[1], "-filter_complex"]

        if has_audio:
            filter_complex += f",[0:a][1:a]acrossfade=d={transition_duration}:c1=tri:c2=tri"
            cmd.extend([filter_complex, "-map", "[v]", "-map", "[a]"])
        else:
            filter_complex += "[v]"
            cmd.extend([filter_complex, "-map", "[v]"])

        cmd.extend(["-c:v", "libx264", "-c:a", "aac", "-y", output_path])

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return f"Videos concatenated successfully with '{transition_effect}' transition to {output_path}"
        except subprocess.CalledProcessError as e:
            return f"Error during xfade process: {e.stderr.decode('utf8') if e.stderr else str(e)}"

    except Exception as e:
        return f"An unexpected error occurred during xfade concatenation: {str(e)}"
    finally:
        shutil.rmtree(temp_dir)


def _concat_standard(video_paths: list[str], output_path: str) -> str:
    """Standard concatenation for multiple videos using concat demuxer."""
    temp_dir = tempfile.mkdtemp()
    try:
        first_props = get_media_properties(video_paths[0])
        target_w = first_props["width"] if first_props["width"] > 0 else 1280
        target_h = first_props["height"] if first_props["height"] > 0 else 720
        target_fps = first_props["avg_fps"] if first_props["avg_fps"] > 0 else 30
        if target_fps <= 0:
            target_fps = 30

        normalized_paths = []
        for i, vpath in enumerate(video_paths):
            norm_path = os.path.join(temp_dir, f"norm_{i}.mp4")
            try:
                subprocess.run(
                    [
                        "ffmpeg", "-i", vpath,
                        "-vf", f"scale={target_w}:{target_h}",
                        "-r", str(target_fps),
                        "-c:v", "libx264", "-c:a", "aac", "-y", norm_path,
                    ],
                    check=True, capture_output=True,
                )
                normalized_paths.append(norm_path)
            except subprocess.CalledProcessError as e:
                return f"Error normalizing video {i}: {e.stderr.decode('utf8') if e.stderr else str(e)}"

        concat_list_path = os.path.join(temp_dir, "concat_list.txt")
        with open(concat_list_path, "w") as f:
            for path in normalized_paths:
                f.write(f"file '{path}'\n")

        try:
            subprocess.run(
                [
                    "ffmpeg", "-f", "concat", "-safe", "0",
                    "-i", concat_list_path, "-c", "copy", "-y", output_path,
                ],
                check=True, capture_output=True,
            )
            return f"Videos concatenated successfully to {output_path}"
        except subprocess.CalledProcessError as e:
            return f"Error during concatenation: {e.stderr.decode('utf8') if e.stderr else str(e)}"

    except Exception as e:
        return f"An unexpected error occurred during standard concatenation: {str(e)}"
    finally:
        shutil.rmtree(temp_dir)
