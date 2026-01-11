from vosk import Model, KaldiRecognizer
from src.providers.interfaces import ITranscriptionProvider
from src.models.domain import TranscriptionResult
from src.config import settings
import numpy as np
import logging
import json
import wave
import io

logger = logging.getLogger(__name__)


class VoskProvider(ITranscriptionProvider):
    """
    Vosk transcription provider - lightweight, fast, offline speech recognition.
    Better for real-time transcription than Whisper.
    
    Download models from: https://alphacephei.com/vosk/models
    Recommended: vosk-model-en-us-0.22 (1.8GB) or vosk-model-small-en-us-0.15 (40MB)
    """
    
    def __init__(self, model_path: str = None):
        """
        Initialize Vosk model.
        
        Args:
            model_path: Path to Vosk model directory
        """
        self.model_path = model_path or getattr(settings, 'vosk_model_path', 'models/vosk-model-en-us-0.22')
        
        logger.info(f"Initializing Vosk model from: {self.model_path}")
        
        try:
            self.model = Model(self.model_path)
            logger.info("Vosk model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Vosk model: {e}")
            logger.error("Download a model from https://alphacephei.com/vosk/models")
            raise
    
    async def transcribe(self, audio_data: np.ndarray, sample_rate: int) -> TranscriptionResult:
        """
        Transcribe audio data to text using Vosk.
        
        Args:
            audio_data: Audio samples as numpy array (float32, mono, -1 to 1 range)
            sample_rate: Sample rate of the audio
            
        Returns:
            TranscriptionResult with text and metadata
        """
        try:
            # Vosk expects 16kHz audio, resample if needed
            if sample_rate != 16000:
                audio_data = self._resample(audio_data, sample_rate, 16000)
                sample_rate = 16000
            
            # Convert float32 to int16 PCM
            audio_int16 = (audio_data * 32767).astype(np.int16)
            
            # Create recognizer
            rec = KaldiRecognizer(self.model, sample_rate)
            rec.SetWords(True)  # Enable word-level timestamps
            
            # Process audio
            rec.AcceptWaveform(audio_int16.tobytes())
            
            # Get final result
            result_json = rec.FinalResult()
            result = json.loads(result_json)
            
            text = result.get('text', '').strip()
            
            # Vosk doesn't provide confidence, estimate from result structure
            confidence = 0.8 if text else 0.0
            
            return TranscriptionResult(
                text=text,
                confidence=confidence,
                language='en'
            )
            
        except Exception as e:
            logger.error(f"Vosk transcription failed: {e}", exc_info=True)
            return TranscriptionResult(text="", confidence=0.0, language='en')
    
    async def transcribe_file(self, file_path: str) -> TranscriptionResult:
        """
        Transcribe audio from a file using Vosk.
        
        Args:
            file_path: Path to audio file (WAV format)
            
        Returns:
            TranscriptionResult with text and metadata
        """
        try:
            with wave.open(file_path, 'rb') as wf:
                # Verify format
                if wf.getnchannels() != 1:
                    raise ValueError("Audio must be mono")
                
                sample_rate = wf.getframerate()
                
                # Read audio data
                audio_bytes = wf.readframes(wf.getnframes())
                audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
                
                # Convert to float32
                audio_float = audio_data.astype(np.float32) / 32768.0
                
                return await self.transcribe(audio_float, sample_rate)
                
        except Exception as e:
            logger.error(f"Failed to transcribe file: {e}", exc_info=True)
            return TranscriptionResult(text="", confidence=0.0, language='en')
    
    def _resample(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """
        Simple resampling using linear interpolation.
        For better quality, use librosa or scipy.
        """
        if orig_sr == target_sr:
            return audio
        
        # Simple linear interpolation
        duration = len(audio) / orig_sr
        target_length = int(duration * target_sr)
        
        indices = np.linspace(0, len(audio) - 1, target_length)
        resampled = np.interp(indices, np.arange(len(audio)), audio)
        
        return resampled.astype(np.float32)
