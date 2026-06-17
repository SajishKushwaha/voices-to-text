import json
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from ..config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AudioDiagnostics:
    input_format: str
    input_codec: str
    input_sample_rate: int | None
    input_channels: int | None
    input_duration: float
    input_size_bytes: int
    output_format: str
    output_codec: str
    output_sample_rate: int
    output_channels: int
    output_duration: float
    output_size_bytes: int
    enhancement_applied: bool
    quality_score: int
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AudioProcessingResult:
    audio_path: Path
    diagnostics: AudioDiagnostics


class AudioPreprocessingService:
    def preprocess(self, audio_path: Path, settings: Settings) -> AudioProcessingResult:
        ffmpeg_path = shutil.which(settings.ffmpeg_binary)
        ffprobe_path = shutil.which(settings.ffprobe_binary)

        if not ffmpeg_path or not ffprobe_path:
            raise ValueError("FFmpeg and FFprobe are required for transcription.")

        input_probe = self._probe_audio(audio_path, ffprobe_path)
        self._validate_input(audio_path, input_probe, settings)

        output_path = audio_path.with_suffix(".enhanced.wav")
        self._convert_to_wav(audio_path, output_path, ffmpeg_path, settings)
        output_probe = self._probe_audio(output_path, ffprobe_path)
        self._validate_output(output_path, output_probe, settings)

        diagnostics = self._build_diagnostics(
            audio_path=audio_path,
            output_path=output_path,
            input_probe=input_probe,
            output_probe=output_probe,
            settings=settings,
        )
        return AudioProcessingResult(audio_path=output_path, diagnostics=diagnostics)

    def _convert_to_wav(
        self,
        input_path: Path,
        output_path: Path,
        ffmpeg_path: str,
        settings: Settings,
    ) -> None:
        command = [
            ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-fflags",
            "+genpts",
            "-i",
            str(input_path),
            "-vn",
            "-map",
            "0:a:0",
            "-ac",
            "1",
            "-ar",
            str(settings.preprocessed_sample_rate),
            "-sample_fmt",
            "s16",
            "-af",
            settings.audio_filter,
            "-f",
            "wav",
            str(output_path),
        ]

        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=settings.audio_preprocessing_timeout_seconds,
            )
        except subprocess.CalledProcessError as error:
            logger.warning("FFmpeg preprocessing failed: %s", error.stderr.strip())
            raise ValueError("Audio could not be converted to clean WAV.") from error
        except subprocess.TimeoutExpired as error:
            raise ValueError("Audio preprocessing timed out.") from error

    def _probe_audio(self, audio_path: Path, ffprobe_path: str) -> dict:
        command = [
            ffprobe_path,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(audio_path),
        ]

        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            raise ValueError("Recording is corrupted or unreadable.") from error

        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise ValueError("Recording metadata could not be read.") from error

    def _validate_input(
        self,
        audio_path: Path,
        probe: dict,
        settings: Settings,
    ) -> None:
        stream = self._audio_stream(probe)
        duration = self._duration(probe)

        if not audio_path.exists() or audio_path.stat().st_size == 0:
            raise ValueError("Recording is empty.")

        if stream is None:
            raise ValueError("Recording does not contain an audio stream.")

        # MediaRecorder WebM files commonly omit duration metadata. A non-empty
        # audio stream must be decoded before deciding whether it is empty.
        if duration > 0 and duration > settings.max_audio_duration_seconds:
            raise ValueError("Recording is too long.")

    def _validate_output(
        self,
        audio_path: Path,
        probe: dict,
        settings: Settings,
    ) -> None:
        stream = self._audio_stream(probe)
        duration = self._duration(probe)

        if not audio_path.exists() or audio_path.stat().st_size == 0:
            raise ValueError("Enhanced WAV output is empty.")

        if stream is None:
            raise ValueError("Enhanced WAV does not contain audio.")

        if int(stream.get("sample_rate", 0)) != settings.preprocessed_sample_rate:
            raise ValueError("Enhanced WAV has an invalid sample rate.")

        if int(stream.get("channels", 0)) != 1:
            raise ValueError("Enhanced WAV must be mono.")

        if duration <= 0:
            raise ValueError("Enhanced recording is empty or silent after preprocessing.")

        if duration < settings.min_audio_duration_seconds:
            raise ValueError(
                f"Recording is too short. Please speak for at least "
                f"{settings.min_audio_duration_seconds:g} seconds."
            )

        if duration > settings.max_audio_duration_seconds:
            raise ValueError("Recording is too long.")

    def _build_diagnostics(
        self,
        audio_path: Path,
        output_path: Path,
        input_probe: dict,
        output_probe: dict,
        settings: Settings,
    ) -> AudioDiagnostics:
        input_stream = self._audio_stream(input_probe) or {}
        output_stream = self._audio_stream(output_probe) or {}
        input_duration_metadata = self._duration(input_probe)
        output_duration = self._duration(output_probe)
        input_duration = (
            input_duration_metadata if input_duration_metadata > 0 else output_duration
        )
        warnings: list[str] = []

        if input_duration_metadata <= 0:
            warnings.append(
                "Input duration metadata was unavailable; decoded WAV duration was used."
            )
        if input_duration < 2:
            warnings.append("Recording is very short.")
        if output_duration < input_duration * 0.45:
            warnings.append("Most of the recording was silence.")
        if self._sample_rate(input_stream) and self._sample_rate(input_stream) < 16000:
            warnings.append("Input sample rate is below 16kHz.")

        quality_score = self._quality_score(
            input_duration=input_duration,
            output_duration=output_duration,
            input_stream=input_stream,
            warnings=warnings,
        )

        return AudioDiagnostics(
            input_format=input_probe.get("format", {}).get("format_name", "unknown"),
            input_codec=input_stream.get("codec_name", "unknown"),
            input_sample_rate=self._sample_rate(input_stream),
            input_channels=self._channels(input_stream),
            input_duration=round(input_duration, 3),
            input_size_bytes=audio_path.stat().st_size,
            output_format="wav",
            output_codec=output_stream.get("codec_name", "pcm_s16le"),
            output_sample_rate=settings.preprocessed_sample_rate,
            output_channels=1,
            output_duration=round(output_duration, 3),
            output_size_bytes=output_path.stat().st_size,
            enhancement_applied=True,
            quality_score=quality_score,
            warnings=warnings,
        )

    def _quality_score(
        self,
        input_duration: float,
        output_duration: float,
        input_stream: dict,
        warnings: list[str],
    ) -> int:
        score = 100

        if input_duration < 2:
            score -= 25
        if output_duration < input_duration * 0.45:
            score -= 30
        if self._sample_rate(input_stream) and self._sample_rate(input_stream) < 16000:
            score -= 15
        if self._channels(input_stream) and self._channels(input_stream) > 2:
            score -= 10
        score -= min(len(warnings) * 5, 20)

        return max(0, min(100, score))

    def _audio_stream(self, probe: dict) -> dict | None:
        for stream in probe.get("streams", []):
            if stream.get("codec_type") == "audio":
                return stream

        return None

    def _duration(self, probe: dict) -> float:
        stream = self._audio_stream(probe) or {}
        duration = stream.get("duration") or probe.get("format", {}).get("duration") or 0
        try:
            return float(duration)
        except (TypeError, ValueError):
            return 0

    def _sample_rate(self, stream: dict) -> int | None:
        sample_rate = stream.get("sample_rate")
        return int(sample_rate) if sample_rate else None

    def _channels(self, stream: dict) -> int | None:
        channels = stream.get("channels")
        return int(channels) if channels else None
