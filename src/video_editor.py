"""
Video Editor — FFmpeg-based video + audio merging
Replaces Descript for the Forky G automated pipeline.
No API, no cost, no external dependencies beyond ffmpeg binary.
"""
import subprocess
import shutil
import sys
from pathlib import Path


def _check_ffmpeg():
    if not shutil.which("ffmpeg"):
        print("  ❌ ffmpeg not found. Install with: brew install ffmpeg (Mac) or apt-get install -y ffmpeg (Linux)")
        sys.exit(1)


def merge_video_audio(video_path: str, audio_path: str, output_path: str,
                      audio_volume: float = 1.0) -> str:
    """
    Merge a video file with an audio voiceover.
    - Copies video stream as-is (no quality loss)
    - Mixes voiceover at given volume
    - Output is trimmed to the shorter of video or audio
    """
    _check_ffmpeg()
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",                        # video: no re-encode, zero quality loss
        "-c:a", "aac", "-b:a", "192k",         # audio: AAC 192k (social media standard)
        "-af", f"volume={audio_volume}",
        "-shortest",                            # trim to shorter stream
        "-movflags", "+faststart",              # optimize for streaming
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg merge failed:\n{result.stderr}")
    print(f"  ✅ Video + audio merged → {output_path}")
    return output_path


def trim_video(input_path: str, output_path: str,
               start: float = 0, duration: float = None) -> str:
    """Trim a video to a specific start time and duration (seconds)."""
    _check_ffmpeg()
    cmd = ["ffmpeg", "-y", "-i", input_path, "-ss", str(start)]
    if duration:
        cmd += ["-t", str(duration)]
    cmd += ["-c:v", "copy", "-c:a", "copy", output_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg trim failed:\n{result.stderr}")
    print(f"  ✅ Video trimmed → {output_path}")
    return output_path


def add_background_music(video_path: str, music_path: str, output_path: str,
                          music_volume: float = 0.15,
                          voice_volume: float = 1.0) -> str:
    """
    Mix existing audio track with background music.
    Useful for reels with voiceover + ambient music.
    """
    _check_ffmpeg()
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", music_path,
        "-filter_complex",
        f"[0:a]volume={voice_volume}[voice];[1:a]volume={music_volume}[music];[voice][music]amix=inputs=2:duration=first[aout]",
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg music mix failed:\n{result.stderr}")
    print(f"  ✅ Background music added → {output_path}")
    return output_path


def get_duration(file_path: str) -> float:
    """Get video/audio duration in seconds."""
    _check_ffmpeg()
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return 0.0
    return float(result.stdout.strip())
