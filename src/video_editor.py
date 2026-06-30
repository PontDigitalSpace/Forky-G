"""
Video Editor — FFmpeg-based video production pipeline
Handles merging, trimming, color grading, cropping, concatenation and audio normalization.
"""
import subprocess
import shutil
import sys
import os
from pathlib import Path


def _check_ffmpeg():
    if not shutil.which("ffmpeg"):
        print("  ❌ ffmpeg not found.")
        sys.exit(1)


def get_duration(file_path: str) -> float:
    """Get video/audio duration in seconds."""
    result = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ], capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def get_dimensions(file_path: str) -> tuple:
    """Get video width and height."""
    result = subprocess.run([
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0",
        file_path
    ], capture_output=True, text=True)
    try:
        w, h = result.stdout.strip().split(",")
        return int(w), int(h)
    except Exception:
        return 1920, 1080


def trim_clip(input_path: str, output_path: str,
              start: float = 0, duration: float = 5.0) -> str:
    """Trim a clip to exact start + duration."""
    _check_ffmpeg()
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", input_path,
        "-t", str(duration),
        "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-profile:v", "high", "-level", "4.0", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg trim failed:\n{result.stderr[-300:]}")
    return output_path


def crop_916(input_path: str, output_path: str) -> str:
    """Crop and scale video to 9:16 vertical (1080x1920) for reels."""
    _check_ffmpeg()
    w, h = get_dimensions(input_path)

    # If already vertical, just scale
    if h > w:
        vf = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
    else:
        # Landscape → crop center to 9:16
        vf = "crop=ih*9/16:ih,scale=1080:1920"

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-profile:v", "high", "-level", "4.0", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg crop failed:\n{result.stderr[-300:]}")
    return output_path


def grade_video(input_path: str, output_path: str,
                style: str = "warm_gold") -> str:
    """
    Apply color grading to match La Medusa brand.
    warm_gold: warm amber tones, BRIGHT and inviting — matches the restaurant aesthetic
    without crushing the already dim candlelit footage.
    """
    _check_ffmpeg()

    if style == "warm_gold":
        # Warm amber but bright: lift blacks/shadows, positive brightness, gentle
        # contrast, keep a warm tint (less blue) without going dark.
        vf = (
            "curves=r='0/0.05 0.5/0.62 1/1':g='0/0.04 0.5/0.56 1/0.97':b='0/0.03 0.5/0.50 1/0.88',"
            "eq=brightness=0.06:contrast=1.03:saturation=1.10,"
            "unsharp=5:5:0.6:5:5:0"
        )
    else:
        vf = "eq=brightness=0:contrast=1:saturation=1"

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-profile:v", "high", "-level", "4.0", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg grade failed:\n{result.stderr[-300:]}")
    return output_path


def slow_motion(input_path: str, output_path: str, factor: float = 2.0) -> str:
    """Apply slow motion effect (factor=2.0 means half speed)."""
    _check_ffmpeg()
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", f"setpts={factor}*PTS",
        "-af", f"atempo={1/factor}",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-profile:v", "high", "-level", "4.0", "-pix_fmt", "yuv420p",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg slow motion failed:\n{result.stderr[-300:]}")
    return output_path


def normalize_audio(input_path: str, output_path: str,
                    target_lufs: float = -14.0) -> str:
    """
    Normalize audio to target LUFS for social media.
    Standard: -14 LUFS for Instagram/TikTok/Facebook.
    """
    _check_ffmpeg()
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-af", f"loudnorm=I={target_lufs}:TP=-2:LRA=11",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg normalize failed:\n{result.stderr[-300:]}")
    return output_path


def concat_clips(clip_paths: list, output_path: str) -> str:
    """
    Concatenate multiple video clips into one seamless video.
    All clips must be same resolution (use crop_916 first).
    """
    _check_ffmpeg()

    # Write concat list file
    list_file = output_path + "_concat_list.txt"
    with open(list_file, "w") as f:
        for clip in clip_paths:
            f.write(f"file '{os.path.abspath(clip)}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_file,
        "-vf", "format=yuv420p",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-profile:v", "high", "-level", "4.0", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
        "-movflags", "+faststart",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Cleanup list file
    Path(list_file).unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg concat failed:\n{result.stderr[-300:]}")
    print(f"  ✅ Concatenated {len(clip_paths)} clips → {output_path}")
    return output_path


def merge_video_audio(video_path: str, audio_path: str, output_path: str) -> str:
    """
    Merge video with voiceover audio.
    Uses audio duration (not video) to avoid cutting voiceover.
    Normalizes to -14 LUFS for social media.
    """
    _check_ffmpeg()

    audio_dur = get_duration(audio_path)
    video_dur = get_duration(video_path)

    if audio_dur > video_dur:
        # Loop video to match audio length
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1",
            "-i", video_path,
            "-i", audio_path,
            "-t", str(audio_dur),
            "-filter_complex", "[1:a]loudnorm=I=-14:TP=-2:LRA=11[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-profile:v", "high", "-level", "4.0", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            output_path
        ]
    else:
        # Video longer than audio — KEEP the full video and PAD the audio with
        # silence so the audio track equals the video length exactly (apad + -shortest
        # ends precisely at the video). Never trim the video to the short voiceover.
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-filter_complex", "[1:a]loudnorm=I=-14:TP=-2:LRA=11,apad[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-shortest",
            "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-profile:v", "high", "-level", "4.0", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            output_path
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg merge failed:\n{result.stderr[-300:]}")
    print(f"  ✅ Video + voiceover merged → {output_path}")
    return output_path


def image_to_video(image_path: str, output_path: str,
                   duration: float = 5.0, zoom: bool = True) -> str:
    """
    Convert a static image to a video clip with optional slow zoom.
    Used when only a photo is available for a scene.
    """
    _check_ffmpeg()

    if zoom:
        # Ken Burns effect — slow zoom in
        vf = (
            f"scale=1920:1080,"
            f"zoompan=z='min(zoom+0.0015,1.5)':d={int(duration*25)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920"
        )
    else:
        vf = "scale=1080:1920"

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-profile:v", "high", "-level", "4.0", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-r", "25",
        "-shortest",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg image_to_video failed:\n{result.stderr[-300:]}")
    return output_path
