"""Overlay and subtitle tools for FFmpeg MCP server."""

from __future__ import annotations

import os

import ffmpeg

from ..utils import decode_ffmpeg_error


def register_overlay_tools(mcp):
    """Register all overlay-related tools with the MCP server."""

    @mcp.tool()
    def add_subtitles(
        video_path: str,
        srt_file_path: str,
        output_video_path: str,
        font_style: dict = None,
    ) -> str:
        """Burns subtitles from an SRT file onto a video, with optional styling.

        Args:
            video_path: Path to the input video file.
            srt_file_path: Path to the SRT subtitle file.
            output_video_path: Path to save the video with subtitles.
            font_style (dict, optional): A dictionary for subtitle styling.
                Supported keys: 'font_name', 'font_size', 'font_color', 'outline_color',
                'outline_width', 'shadow_color', 'shadow_offset_x', 'shadow_offset_y',
                'alignment', 'margin_v', 'margin_l', 'margin_r'.
                Default is None, which uses FFmpeg's default subtitle styling.
        Returns:
            A status message indicating success or failure.
        """
        try:
            if not os.path.exists(video_path):
                return f"Error: Input video file not found at {video_path}"
            if not os.path.exists(srt_file_path):
                return f"Error: SRT subtitle file not found at {srt_file_path}"

            input_stream = ffmpeg.input(video_path)

            style_args = []
            if font_style:
                style_map = {
                    "font_name": "FontName",
                    "font_size": "FontSize",
                    "font_color": "PrimaryColour",
                    "outline_color": "OutlineColour",
                    "outline_width": "Outline",
                    "shadow_color": "ShadowColour",
                    "alignment": "Alignment",
                    "margin_v": "MarginV",
                    "margin_l": "MarginL",
                    "margin_r": "MarginR",
                }
                for key, ass_key in style_map.items():
                    if key in font_style:
                        style_args.append(f"{ass_key}={font_style[key]}")
                if "shadow_offset_x" in font_style or "shadow_offset_y" in font_style:
                    shadow_val = font_style.get(
                        "shadow_offset_x", font_style.get("shadow_offset_y", 1)
                    )
                    style_args.append(f"Shadow={shadow_val}")

            vf_filter = f"subtitles='{srt_file_path}'"
            if style_args:
                vf_filter += f":force_style='{','.join(style_args)}'"

            try:
                input_stream.output(
                    output_video_path, vf=vf_filter, acodec="copy"
                ).run(capture_stdout=True, capture_stderr=True)
                return f"Subtitles added successfully (audio copied) to {output_video_path}"
            except ffmpeg.Error as e_acopy:
                try:
                    input_stream.output(output_video_path, vf=vf_filter).run(
                        capture_stdout=True, capture_stderr=True
                    )
                    return f"Subtitles added successfully (audio re-encoded) to {output_video_path}"
                except ffmpeg.Error as e_recode:
                    return (
                        f"Error adding subtitles. Audio copy attempt: {decode_ffmpeg_error(e_acopy)}. "
                        f"Full re-encode attempt: {decode_ffmpeg_error(e_recode)}"
                    )

        except ffmpeg.Error as e:
            return f"Error adding subtitles: {decode_ffmpeg_error(e)}"
        except FileNotFoundError:
            return "Error: A specified file was not found."
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"

    @mcp.tool()
    def add_text_overlay(
        video_path: str, output_video_path: str, text_elements: list[dict]
    ) -> str:
        """Adds one or more text overlays to a video at specified times and positions.

        Args:
            video_path: Path to the input main video file.
            output_video_path: Path to save the video with text overlays.
            text_elements: A list of dictionaries, where each dictionary defines a text overlay.
                Required keys: 'text', 'start_time', 'end_time'.
                Optional keys: 'font_size' (24), 'font_color' ('white'), 'x_pos' ('center'),
                'y_pos' ('h-th-10'), 'box' (False), 'box_color' ('black@0.5'),
                'box_border_width' (0), 'font_file'.
        Returns:
            A status message indicating success or failure.
        """
        try:
            if not os.path.exists(video_path):
                return f"Error: Input video file not found at {video_path}"
            if not text_elements:
                return "Error: No text elements provided for overlay."

            input_stream = ffmpeg.input(video_path)
            drawtext_filters = []

            for element in text_elements:
                text = element.get("text")
                start_time = element.get("start_time")
                end_time = element.get("end_time")

                if text is None or start_time is None or end_time is None:
                    return "Error: Text element is missing required keys (text, start_time, end_time)."

                safe_text = (
                    text.replace("\\", "\\\\")
                    .replace("'", "\\'")
                    .replace(":", "\\:")
                    .replace(",", "\\,")
                )

                filter_params = [
                    f"text='{safe_text}'",
                    f"fontsize={element.get('font_size', 24)}",
                    f"fontcolor={element.get('font_color', 'white')}",
                    f"x={element.get('x_pos', '(w-text_w)/2')}",
                    f"y={element.get('y_pos', 'h-text_h-10')}",
                    f"enable=between(t\\,{start_time}\\,{end_time})",
                ]

                if element.get("box", False):
                    filter_params.append("box=1")
                    filter_params.append(
                        f"boxcolor={element.get('box_color', 'black@0.5')}"
                    )
                    if "box_border_width" in element:
                        filter_params.append(
                            f"boxborderw={element['box_border_width']}"
                        )

                if "font_file" in element:
                    font_path = (
                        element["font_file"]
                        .replace("\\", "\\\\")
                        .replace("'", "\\'")
                        .replace(":", "\\:")
                    )
                    filter_params.append(f"fontfile='{font_path}'")

                drawtext_filters.append(f"drawtext={':'.join(filter_params)}")

            final_vf = ",".join(drawtext_filters)

            try:
                input_stream.output(
                    output_video_path, vf=final_vf, acodec="copy"
                ).run(capture_stdout=True, capture_stderr=True)
                return f"Text overlays added successfully (audio copied) to {output_video_path}"
            except ffmpeg.Error as e_acopy:
                try:
                    input_stream.output(output_video_path, vf=final_vf).run(
                        capture_stdout=True, capture_stderr=True
                    )
                    return f"Text overlays added successfully (audio re-encoded) to {output_video_path}"
                except ffmpeg.Error as e_recode:
                    return (
                        f"Error adding text overlays. Audio copy attempt: {decode_ffmpeg_error(e_acopy)}. "
                        f"Full re-encode attempt: {decode_ffmpeg_error(e_recode)}"
                    )

        except ffmpeg.Error as e:
            return f"Error processing text overlays: {decode_ffmpeg_error(e)}"
        except FileNotFoundError:
            return "Error: Input video file not found."
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"

    @mcp.tool()
    def add_image_overlay(
        video_path: str,
        output_video_path: str,
        image_path: str,
        position: str = "top_right",
        opacity: float = None,
        start_time: str = None,
        end_time: str = None,
        width: str = None,
        height: str = None,
    ) -> str:
        """Adds an image overlay (watermark/logo) to a video.

        Args:
            video_path: Path to the input video file.
            output_video_path: Path to save the video with the image overlay.
            image_path: Path to the image file for the overlay.
            position: Position of the overlay.
                Options: 'top_left', 'top_right', 'bottom_left', 'bottom_right', 'center'.
                Or specify custom coordinates like 'x=10:y=10'.
            opacity: Opacity of the overlay (0.0 to 1.0). If None, image's own alpha is used.
            start_time: Start time for the overlay (HH:MM:SS or seconds). If None, starts from beginning.
            end_time: End time for the overlay (HH:MM:SS or seconds). If None, lasts till end.
            width: Width for the overlay image (e.g., '100', 'iw*0.1'). Original if None.
            height: Height for the overlay image (e.g., '50', 'ih*0.1'). Original if None.
        Returns:
            A status message indicating success or failure.
        """
        try:
            if not os.path.exists(video_path):
                return f"Error: Input video file not found at {video_path}"
            if not os.path.exists(image_path):
                return f"Error: Overlay image file not found at {image_path}"

            main_input = ffmpeg.input(video_path)
            overlay_input = ffmpeg.input(image_path)
            processed_overlay = overlay_input

            if width or height:
                scale_params = {}
                if width:
                    scale_params["width"] = width
                if height:
                    scale_params["height"] = height
                if width and not height:
                    scale_params["height"] = "-1"
                if height and not width:
                    scale_params["width"] = "-1"
                processed_overlay = processed_overlay.filter("scale", **scale_params)

            if opacity is not None and 0.0 <= opacity <= 1.0:
                processed_overlay = processed_overlay.filter("format", "rgba")
                processed_overlay = processed_overlay.filter(
                    "colorchannelmixer", aa=str(opacity)
                )

            position_map = {
                "top_left": ("10", "10"),
                "top_right": ("main_w-overlay_w-10", "10"),
                "bottom_left": ("10", "main_h-overlay_h-10"),
                "bottom_right": ("main_w-overlay_w-10", "main_h-overlay_h-10"),
                "center": ("(main_w-overlay_w)/2", "(main_h-overlay_h)/2"),
            }

            if position in position_map:
                overlay_x, overlay_y = position_map[position]
            elif ":" in position:
                overlay_x, overlay_y = "0", "0"
                for part in position.split(":"):
                    if part.startswith("x="):
                        overlay_x = part.split("=")[1]
                    if part.startswith("y="):
                        overlay_y = part.split("=")[1]
            else:
                overlay_x, overlay_y = "0", "0"

            overlay_kwargs = {"x": overlay_x, "y": overlay_y}

            if start_time is not None or end_time is not None:
                actual_start = start_time if start_time is not None else "0"
                if end_time is not None:
                    overlay_kwargs["enable"] = f"between(t,{actual_start},{end_time})"
                else:
                    overlay_kwargs["enable"] = f"gte(t,{actual_start})"

            try:
                video_with_overlay = ffmpeg.filter(
                    [main_input, processed_overlay], "overlay", **overlay_kwargs
                )
                ffmpeg.output(
                    video_with_overlay, main_input.audio, output_video_path, acodec="copy"
                ).run(capture_stdout=True, capture_stderr=True)
                return f"Image overlay added successfully (audio copied) to {output_video_path}"
            except ffmpeg.Error as e_acopy:
                try:
                    video_with_overlay = ffmpeg.filter(
                        [main_input, processed_overlay], "overlay", **overlay_kwargs
                    )
                    ffmpeg.output(
                        video_with_overlay, main_input.audio, output_video_path
                    ).run(capture_stdout=True, capture_stderr=True)
                    return f"Image overlay added successfully (audio re-encoded) to {output_video_path}"
                except ffmpeg.Error as e_recode:
                    return (
                        f"Error adding image overlay. Audio copy attempt: {decode_ffmpeg_error(e_acopy)}. "
                        f"Full re-encode attempt: {decode_ffmpeg_error(e_recode)}"
                    )

        except ffmpeg.Error as e:
            return f"Error processing image overlay: {decode_ffmpeg_error(e)}"
        except FileNotFoundError:
            return f"Error: An input file was not found (video: '{video_path}', image: '{image_path}'). Please check paths."
        except Exception as e:
            return f"An unexpected error occurred in add_image_overlay: {str(e)}"
