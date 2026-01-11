from faster_whisper import WhisperModel
from src.providers.interfaces import ITranscriptionProvider
from src.models.domain import TranscriptionResult
from src.config import settings
import numpy as np
import logging

logger = logging.getLogger(__name__)


class WhisperProvider(ITranscriptionProvider):
    """
    Whisper transcription using faster-whisper (optimized with CTranslate2).
    Supports GPU acceleration via CUDA.
    """
    
    def __init__(
        self,
        model_size: str = None,
        device: str = None,
        compute_type: str = None
    ):
        """
        Initialize Whisper model.
        
        Args:
            model_size: Model size (tiny, base, small, medium, large-v2, large-v3)
            device: Device to use (cuda or cpu)
            compute_type: Compute type (float16, int8, int8_float16)
        """
        self.model_size = model_size or settings.whisper_model
        self.device = device or settings.whisper_device
        self.compute_type = compute_type or settings.whisper_compute_type
        
        logger.info(
            f"Initializing Whisper model: {self.model_size} "
            f"on {self.device} with {self.compute_type}"
        )
        
        try:
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type
            )
            logger.info("Whisper model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise
    
    async def transcribe(
        self, 
        audio_data: np.ndarray, 
        sample_rate: int
    ) -> TranscriptionResult:
        """
        Transcribe audio data to text.
        
        Args:
            audio_data: Audio samples as numpy array (float32, mono)
            sample_rate: Sample rate of the audio
            
        Returns:
            TranscriptionResult with transcribed text and metadata
        """
        try:
            # faster-whisper expects float32 mono audio
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
            
            # Ensure mono
            if len(audio_data.shape) > 1:
                audio_data = audio_data.mean(axis=1)
            
            # Normalize if needed
            if np.abs(audio_data).max() > 1.0:
                audio_data = audio_data / np.abs(audio_data).max()
            
            # Transcribe
            segments, info = self.model.transcribe(
                audio_data,
                beam_size=5,
                vad_filter=settings.whisper_vad_enabled,
                vad_parameters=dict(
                    min_silence_duration_ms=settings.whisper_vad_min_silence_ms
                ) if settings.whisper_vad_enabled else None
            )
            
            # Collect all segments
            text_segments = []
            total_confidence = 0.0
            segment_count = 0
            
            for segment in segments:
                text_segments.append(segment.text.strip())
                total_confidence += segment.avg_logprob
                segment_count += 1
            
            # Combine text
            full_text = " ".join(text_segments).strip()
            
            # Calculate average confidence (convert log prob to probability)
            avg_confidence = np.exp(total_confidence / segment_count) if segment_count > 0 else 0.0
            
            # Calculate duration
            duration = len(audio_data) / sample_rate
            
            return TranscriptionResult(
                text=full_text,
                confidence=float(avg_confidence),
                language=info.language,
                duration=duration
            )
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return TranscriptionResult(
                text="",
                confidence=0.0,
                duration=0.0
            )
    
    async def transcribe_file(self, file_path: str) -> TranscriptionResult:
        """
        Transcribe audio from a file.
        
        Args:
            file_path: Path to audio file
            
        Returns:
            TranscriptionResult with text and metadata
        """
        try:
            segments, info = self.model.transcribe(
                file_path,
                beam_size=5,
                vad_filter=settings.whisper_vad_enabled,
                vad_parameters=dict(
                    min_silence_duration_ms=settings.whisper_vad_min_silence_ms
                ) if settings.whisper_vad_enabled else None
            )
            
            text_segments = []
            total_confidence = 0.0
            segment_count = 0
            total_duration = 0.0
            
            for segment in segments:
                text_segments.append(segment.text.strip())
                total_confidence += segment.avg_logprob
                segment_count += 1
                total_duration = max(total_duration, segment.end)
            
            full_text = " ".join(text_segments).strip()
            avg_confidence = np.exp(total_confidence / segment_count) if segment_count > 0 else 0.0
            
            return TranscriptionResult(
                text=full_text,
                confidence=float(avg_confidence),
                language=info.language,
                duration=total_duration
            )
            
        except Exception as e:
            logger.error(f"File transcription failed: {e}")
            return TranscriptionResult(
                text="",
                confidence=0.0,
                duration=0.0
            )
