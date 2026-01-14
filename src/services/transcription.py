from typing import Dict, Optional
from datetime import datetime
import asyncio
import numpy as np
import logging
from collections import defaultdict

from src.providers.interfaces import ITranscriptionProvider
from src.repositories.utterance_repo import UtteranceRepository
from src.services.session_manager import SessionManager
from src.config import settings

logger = logging.getLogger(__name__)


class AudioBuffer:
    """Buffer to accumulate audio data before transcription."""
    
    def __init__(self, user_id: int, username: str, display_name: str):
        self.user_id = user_id
        self.username = username
        self.display_name = display_name
        self.audio_data: list[np.ndarray] = []
        self.started_at: Optional[datetime] = None
        self.last_audio_at: Optional[datetime] = None
    
    def add_audio(self, audio: np.ndarray, vad_threshold: float = 0.1) -> None:
        """
        Add audio chunk to buffer with voice activity detection.
        
        Args:
            audio: Audio data to add
            vad_threshold: RMS threshold for voice activity detection (default: 0.1)
        """
        if not self.started_at:
            self.started_at = datetime.utcnow()
            # Initialize last_audio_at on first audio chunk
            self.last_audio_at = datetime.utcnow()
        
        self.audio_data.append(audio)
        
        # Only update timestamp if audio contains actual speech
        # Calculate RMS (root mean square) to detect voice activity
        rms = np.sqrt(np.mean(audio ** 2))
        
        if rms > vad_threshold:
            # Audio contains speech, update timestamp
            self.last_audio_at = datetime.utcnow()
            logger.debug(f"Voice activity detected: RMS={rms:.6f} (threshold={vad_threshold})")
        else:
            logger.debug(f"Silence detected: RMS={rms:.6f} (threshold={vad_threshold})")
        # If RMS is below threshold, don't update timestamp
        # This allows silence detection to work properly
    
    def get_combined_audio(self) -> np.ndarray:
        """Combine all audio chunks into single array."""
        if not self.audio_data:
            return np.array([], dtype=np.float32)
        
        return np.concatenate(self.audio_data)
    
    def clear(self) -> None:
        """Clear the buffer."""
        self.audio_data = []
        self.started_at = None
        self.last_audio_at = None
    
    def duration(self) -> float:
        """Total audio duration in seconds."""
        if not self.audio_data:
            return 0.0
        
        total_samples = sum(len(chunk) for chunk in self.audio_data)
        return total_samples / settings.audio_sample_rate
    
    def is_ready(self) -> bool:
        """Check if buffer has enough audio to transcribe."""
        return self.duration() >= settings.audio_chunk_duration
    
    def is_stale(self, max_silence_seconds: float = None) -> bool:
        """Check if buffer has been silent for too long."""
        if not self.last_audio_at:
            return False
        
        if max_silence_seconds is None:
            from src.config import settings
            max_silence_seconds = settings.audio_silence_threshold
        
        silence_duration = (datetime.utcnow() - self.last_audio_at).total_seconds()
        return silence_duration >= max_silence_seconds


class TranscriptionService:
    """
    Service for handling audio transcription from Discord voice.
    Manages audio buffering and coordinates with transcription provider.
    """
    
    def __init__(
        self,
        transcription_provider: ITranscriptionProvider,
        utterance_repo: UtteranceRepository,
        session_manager: SessionManager,
        vector_service: 'VectorService' = None
    ):
        self.transcription_provider = transcription_provider
        self.utterance_repo = utterance_repo
        self.session_manager = session_manager
        self.vector_service = vector_service
        
        # Audio buffers per user per channel
        self._buffers: Dict[int, Dict[int, AudioBuffer]] = defaultdict(dict)  # channel_id -> {user_id -> buffer}
        
        # Processing locks to prevent concurrent transcription of same buffer
        self._processing_locks: Dict[tuple, asyncio.Lock] = {}
        
        # Background task for monitoring stale buffers
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Lock for provider swapping to ensure thread safety
        self._provider_swap_lock = asyncio.Lock()
    
    async def add_audio(
        self,
        channel_id: int,
        user_id: int,
        username: str,
        display_name: str,
        audio_data: np.ndarray
    ) -> None:
        """
        Add audio data for a user in a channel.
        
        Args:
            channel_id: Discord channel ID
            user_id: User who spoke
            username: Username
            display_name: Display name
            audio_data: Audio samples (float32, mono)
        """
        logger.debug(f"Received {len(audio_data)} audio samples for user {username} ({user_id}) in channel {channel_id}")
        
        # Get or create buffer
        if user_id not in self._buffers[channel_id]:
            self._buffers[channel_id][user_id] = AudioBuffer(
                user_id=user_id,
                username=username,
                display_name=display_name
            )
            logger.debug(f"Created new audio buffer for user {username} ({user_id})")
        
        buffer = self._buffers[channel_id][user_id]
        buffer.add_audio(audio_data)
        
        # Record activity in session
        self.session_manager.record_activity(channel_id)
        
        # Log current buffer state
        logger.debug(f"Buffer state for {username}: duration={buffer.duration():.2f}s, is_ready={buffer.is_ready()}, is_stale={buffer.is_stale()}")
        
        # Check if buffer is ready for transcription (reached chunk duration)
        if buffer.is_ready():
            logger.debug(f"Buffer ready for transcription for user {username} ({user_id}) - duration: {buffer.duration():.2f}s")
            await self._process_buffer(channel_id, user_id)
        # Also check if buffer is stale (silence detected)
        elif buffer.is_stale():
            logger.debug(f"Buffer is stale (silence detected) for user {username} ({user_id}) - duration: {buffer.duration():.2f}s")
            await self._process_buffer(channel_id, user_id)
        else:
            logger.debug(f"Buffer not ready yet for user {username} ({user_id}) - duration: {buffer.duration():.2f}s")
    
    async def _process_buffer(self, channel_id: int, user_id: int) -> None:
        """Process and transcribe a user's audio buffer."""
        buffer = self._buffers[channel_id].get(user_id)
        
        if not buffer or len(buffer.audio_data) == 0:
            return
        
        # Get or create lock for this buffer
        lock_key = (channel_id, user_id)
        if lock_key not in self._processing_locks:
            self._processing_locks[lock_key] = asyncio.Lock()
        
        async with self._processing_locks[lock_key]:
            # Get session
            session_id = self.session_manager.get_active_session(channel_id)
            if not session_id:
                logger.warning(f"No active session for channel {channel_id}, skipping transcription")
                return
            
            # Get audio data
            audio = buffer.get_combined_audio()
            started_at = buffer.started_at
            ended_at = datetime.utcnow()
            
            # Clear buffer
            buffer.clear()
            
            # Skip if audio is too short
            duration = len(audio) / settings.audio_sample_rate
            if duration < settings.audio_min_duration:
                logger.debug(f"Skipping short audio clip ({duration:.2f}s)")
                return
            
            # Skip if audio is mostly silence (low RMS)
            overall_rms = np.sqrt(np.mean(audio ** 2))
            if overall_rms < 0.02:
                logger.debug(f"Skipping silent buffer (RMS={overall_rms:.6f}) for user {user_id}")
                return
            
            try:
                # Transcribe
                logger.debug(f"Transcribing {duration:.2f}s of audio for user {user_id}")
                result = await self.transcription_provider.transcribe(
                    audio_data=audio,
                    sample_rate=settings.audio_sample_rate
                )
                
                # Skip empty transcriptions
                if not result.text or result.text.strip() == "":
                    logger.debug("Transcription resulted in empty text")
                    return
                
                # Store utterance
                utterance_id = self.utterance_repo.create_utterance(
                    session_id=session_id,
                    user_id=user_id,
                    username=buffer.username,
                    display_name=buffer.display_name,
                    text=result.text,
                    started_at=started_at,
                    ended_at=ended_at,
                    confidence=result.confidence,
                    audio_duration=duration
                )
                
                logger.info(
                    f"Transcribed utterance #{utterance_id}: "
                    f"{buffer.username}: \"{result.text[:50]}...\" "
                    f"({result.confidence:.2f} confidence)"
                )
                
                # Store embedding in vector database (if enabled)
                if self.vector_service:
                    await self.vector_service.store_utterance(
                        utterance_id=utterance_id,
                        text=result.text,
                        user_id=user_id,
                        username=buffer.username,
                        session_id=session_id,
                        timestamp=started_at,
                        confidence=result.confidence
                    )
                
            except Exception as e:
                logger.error(f"Failed to process audio buffer: {e}", exc_info=True)
    
    async def flush_buffer(self, channel_id: int, user_id: int) -> None:
        """Force process a buffer even if not full (e.g., user left)."""
        if channel_id in self._buffers and user_id in self._buffers[channel_id]:
            buffer = self._buffers[channel_id][user_id]
            if len(buffer.audio_data) > 0:
                await self._process_buffer(channel_id, user_id)
    
    async def flush_all_buffers(self, channel_id: int) -> None:
        """Flush all buffers for a channel."""
        if channel_id in self._buffers:
            for user_id in list(self._buffers[channel_id].keys()):
                await self.flush_buffer(channel_id, user_id)
    
    async def start_monitor(self) -> None:
        """Start monitoring for stale buffers."""
        if self._monitor_task:
            logger.warning("Buffer monitor already running")
            return
        
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Started buffer monitor")
    
    async def stop_monitor(self) -> None:
        """Stop the monitor."""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
            logger.info("Stopped buffer monitor")
    
    async def _monitor_loop(self) -> None:
        """Monitor loop to check for stale buffers."""
        logger.info("Buffer monitor loop started")
        while True:
            try:
                await asyncio.sleep(1)  # Check every second
                
                # Check all buffers for staleness
                for channel_id in list(self._buffers.keys()):
                    for user_id in list(self._buffers[channel_id].keys()):
                        buffer = self._buffers[channel_id][user_id]
                        
                        # Debug: Log buffer state
                        if len(buffer.audio_data) > 0:
                            silence_duration = (datetime.utcnow() - buffer.last_audio_at).total_seconds() if buffer.last_audio_at else 0
                            logger.debug(
                                f"Monitor check - user {user_id}: "
                                f"duration={buffer.duration():.2f}s, "
                                f"silence={silence_duration:.2f}s, "
                                f"is_stale={buffer.is_stale()}, "
                                f"chunks={len(buffer.audio_data)}"
                            )
                        
                        # If buffer is stale and has data, process it
                        if buffer.is_stale() and len(buffer.audio_data) > 0:
                            logger.debug(f"Processing stale buffer for user {user_id} in channel {channel_id}")
                            await self._process_buffer(channel_id, user_id)
                            
            except asyncio.CancelledError:
                logger.info("Buffer monitor loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in buffer monitor: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    async def swap_provider(self, new_provider: ITranscriptionProvider) -> dict:
        """
        Hot-swap the transcription provider without restarting.
        
        This method:
        1. Processes all in-flight buffers with the current provider
        2. Swaps to the new provider
        3. New audio will use the new provider
        
        Args:
            new_provider: The new transcription provider instance
            
        Returns:
            dict with swap statistics (buffers_processed, provider_name)
        """
        async with self._provider_swap_lock:
            old_provider_name = type(self.transcription_provider).__name__
            new_provider_name = type(new_provider).__name__
            
            logger.info(f"Starting provider swap: {old_provider_name} -> {new_provider_name}")
            
            # Process all in-flight buffers with the current provider
            buffers_processed = 0
            for channel_id in list(self._buffers.keys()):
                for user_id in list(self._buffers[channel_id].keys()):
                    buffer = self._buffers[channel_id][user_id]
                    
                    # Process buffer if it has any audio data
                    if len(buffer.audio_data) > 0:
                        logger.info(f"Processing in-flight buffer for user {user_id} with {old_provider_name}")
                        await self._process_buffer(channel_id, user_id)
                        buffers_processed += 1
            
            # Swap the provider
            self.transcription_provider = new_provider
            
            logger.info(
                f"Provider swap complete: {old_provider_name} -> {new_provider_name}. "
                f"Processed {buffers_processed} in-flight buffer(s)."
            )
            
            return {
                'old_provider': old_provider_name,
                'new_provider': new_provider_name,
                'buffers_processed': buffers_processed
            }
    
    def get_current_provider(self) -> str:
        """Get the name of the current transcription provider."""
        return type(self.transcription_provider).__name__
