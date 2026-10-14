"""Video processing."""
import subprocess
import os
import shutil
from faster_whisper import WhisperModel
from pathlib import Path
from typing import Dict, Any, List

class VideoProcessor:
    def __init__(self, whisper_model_size: str = "base", device: str = "auto", compute_type: str = "default"):
        #docstring explaining the constructor
        """
        Initializes the faster-whisper model.
        - device: "cuda", "cpu", or "auto"
        - compute_type: "float16", "int8", or "default"
        """
        self.whisper_model = WhisperModel(
            whisper_model_size, 
            device=device, 
            compute_type=compute_type
        )

    def extract_audio(self, video_path: str, output_audio_path: str) -> str:
        """Extracts MP3 audio track from video file using FFmpeg."""
        input_path = Path(video_path)
        if not input_path.is_file():
            raise FileNotFoundError(f"Video file does not exist: {input_path.resolve()}")
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            raise FileNotFoundError(
                "FFmpeg was not found on PATH. Install FFmpeg or add its bin directory to PATH."
            )
        cmd = [
                ffmpeg,
                "-y",                   # Overwrite output file if exists
                "-i", str(input_path),  # Input video
                "-vn",                  # Disable video recording
                "-acodec", "libmp3lame",
                "-q:a", "2",
                output_audio_path
            ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            details = exc.stderr.strip() or "FFmpeg returned no diagnostic output."
            raise RuntimeError(f"FFmpeg failed to extract audio: {details}") from exc
        return output_audio_path
    
    def transcribe_audio(self, audio_path: str) -> List[Dict[str, Any]]:
        """Transcribes audio using Whisper and returns timestamps."""
        result = self.whisper_model.transcribe(audio_path)
        segments = []
        if isinstance(result, tuple):
            raw_segments, _ = result
            for segment in raw_segments:
                start = getattr(segment, "start", 0.0)
                end = getattr(segment, "end", 0.0)
                text = getattr(segment, "text", "").strip()
                if text:
                    segments.append({
                        "t_start": round(float(start), 2),
                        "t_end": round(float(end), 2),
                        "text": text
                    })
        elif isinstance(result, dict):
            for segment in result.get("segments", []):
                start = segment.get("start", 0.0)
                end = segment.get("end", 0.0)
                text = segment.get("text", "").strip()
                if text:
                    segments.append({
                        "t_start": round(float(start), 2),
                        "t_end": round(float(end), 2),
                        "text": text
                    })
        return segments 

    def extract_keyframes(self, video_path: str, output_dir: str, interval_sec: int = 10) -> List[str]:
        """Extracts keyframe images every N seconds using FFmpeg."""
        os.makedirs(output_dir, exist_ok=True)
        output_pattern = os.path.join(output_dir, "frame_%04d.jpg")
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            raise FileNotFoundError(
                "FFmpeg was not found on PATH. Install FFmpeg or add its bin directory to PATH."
            )
        cmd = [
            ffmpeg,
            "-y",
            "-i", video_path,
            "-vf", f"fps=1/{interval_sec}",
            output_pattern
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            details = exc.stderr.strip() or "FFmpeg returned no diagnostic output."
            raise RuntimeError(f"FFmpeg failed to extract keyframes: {details}") from exc
        
        frames = [os.path.join(output_dir, f) for f in sorted(os.listdir(output_dir)) if f.endswith(".jpg")]
        return frames

    def process(self, video_path: str, temp_dir: str) -> Dict[str, Any]:
        """Full pipeline processing for a video file."""
        audio_path = os.path.join(temp_dir, "extracted_audio.mp3")
        keyframes_dir = os.path.join(temp_dir, "keyframes")

        # Step 1: Extract Audio via FFmpeg
        self.extract_audio(video_path, audio_path)

        # Step 2: Transcribe via Whisper
        transcript_segments = self.transcribe_audio(audio_path)

        # Step 3: Extract Frames via FFmpeg
        frames = self.extract_keyframes(video_path, keyframes_dir)

        return {
            "source_type": "video",
            "transcripts": transcript_segments,
            "keyframes": frames
        }