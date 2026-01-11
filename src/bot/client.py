import discord
from discord.ext import commands
import numpy as np
import logging
from typing import Optional
from datetime import datetime

from src.services.transcription import TranscriptionService
from src.services.session_manager import SessionManager
from src.repositories.message_repo import MessageRepository
from src.config import settings

logger = logging.getLogger(__name__)


class VoiceSink(discord.sinks.Sink):
    """Custom audio sink to capture voice data per user."""
    
    def __init__(self, transcription_service: TranscriptionService, channel_id: int):
        super().__init__()
        self.transcription_service = transcription_service
        self.channel_id = channel_id
    
    def write(self, data: dict, user: discord.User):
        """
        Called when audio data is received from a user.
        
        Args:
            data: Audio data dict with 'data' key containing bytes
            user: Discord user who spoke
        """
        if not data or 'data' not in data:
            return
        
        try:
            # Convert audio bytes to numpy array
            audio_bytes = data['data']
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
            
            # Convert to float32 in range [-1, 1]
            audio_float = audio_array.astype(np.float32) / 32768.0
            
            # Add to transcription service
            import asyncio
            loop = asyncio.get_event_loop()
            loop.create_task(
                self.transcription_service.add_audio(
                    channel_id=self.channel_id,
                    user_id=user.id,
                    username=user.name,
                    display_name=user.display_name or user.name,
                    audio_data=audio_float
                )
            )
        except Exception as e:
            logger.error(f"Error processing audio data: {e}")
    
    def cleanup(self):
        """Called when recording is stopped."""
        pass


class DiscordBot(commands.Bot):
    """Discord bot for social dynamics analysis."""
    
    def __init__(
        self,
        transcription_service: TranscriptionService,
        session_manager: SessionManager,
        message_repo: MessageRepository
    ):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        intents.members = True
        
        super().__init__(
            command_prefix=settings.command_prefix,
            intents=intents
        )
        
        self.transcription_service = transcription_service
        self.session_manager = session_manager
        self.message_repo = message_repo
        
        # Track which channels we're recording
        self._recording_channels = set()
    
    async def setup_hook(self):
        """Called when bot is starting up."""
        logger.info("Bot is setting up...")
        
        # Start background services
        await self.transcription_service.start_monitor()
        await self.session_manager.start_timeout_monitor()
    
    async def on_ready(self):
        """Called when bot is connected and ready."""
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        logger.info(f'Connected to {len(self.guilds)} guilds')
        
        # Set presence
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="voice conversations"
            )
        )
    
    async def on_message(self, message: discord.Message):
        """Handle incoming text messages."""
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Store message
        try:
            # Check if there's an active voice session in this channel
            session_id = None
            if isinstance(message.channel, discord.TextChannel):
                # Look for voice channels in the same guild
                for vc in message.guild.voice_channels:
                    if vc.id in self._recording_channels:
                        session_id = self.session_manager.get_active_session(vc.id)
                        break
            
            self.message_repo.create_message(
                message_id=message.id,
                channel_id=message.channel.id,
                user_id=message.author.id,
                username=message.author.name,
                display_name=message.author.display_name or message.author.name,
                content=message.content,
                timestamp=message.created_at,
                session_id=session_id,
                reply_to_message_id=message.reference.message_id if message.reference else None
            )
        except Exception as e:
            logger.error(f"Failed to store message: {e}")
        
        # Process commands
        await self.process_commands(message)
    
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):
        """Handle voice state changes (join/leave/move)."""
        # User joined a channel
        if before.channel is None and after.channel is not None:
            await self._handle_user_join(member, after.channel)
        
        # User left a channel
        elif before.channel is not None and after.channel is None:
            await self._handle_user_leave(member, before.channel)
        
        # User moved channels
        elif before.channel != after.channel:
            await self._handle_user_leave(member, before.channel)
            await self._handle_user_join(member, after.channel)
    
    async def _handle_user_join(self, member: discord.Member, channel: discord.VoiceChannel):
        """Handle user joining a voice channel."""
        logger.info(f"{member.name} joined {channel.name}")
        
        # Get or create session
        session_id = self.session_manager.get_active_session(channel.id)
        if not session_id:
            session_id = self.session_manager.start_session(
                channel_id=channel.id,
                channel_name=channel.name,
                guild_id=channel.guild.id
            )
        
        # Add participant
        self.session_manager.add_participant(
            channel_id=channel.id,
            user_id=member.id,
            username=member.name,
            display_name=member.display_name or member.name
        )
        
        # Start recording if not already
        if channel.id not in self._recording_channels and channel.guild.voice_client:
            await self._start_recording(channel)
    
    async def _handle_user_leave(self, member: discord.Member, channel: discord.VoiceChannel):
        """Handle user leaving a voice channel."""
        logger.info(f"{member.name} left {channel.name}")
        
        # Flush their audio buffer
        await self.transcription_service.flush_buffer(channel.id, member.id)
        
        # Remove participant
        self.session_manager.remove_participant(channel.id, member.id)
        
        # Stop recording if channel is empty
        if len(channel.members) == 1 and channel.guild.voice_client in channel.members:
            await self._stop_recording(channel)
    
    async def _start_recording(self, channel: discord.VoiceChannel):
        """Start recording a voice channel."""
        if channel.id in self._recording_channels:
            return
        
        try:
            # Connect if not connected
            vc = channel.guild.voice_client
            if not vc or not vc.is_connected():
                vc = await channel.connect()
            
            # Create sink
            sink = VoiceSink(self.transcription_service, channel.id)
            
            # Start recording
            vc.start_recording(
                sink,
                self._recording_callback,
                channel.id
            )
            
            self._recording_channels.add(channel.id)
            logger.info(f"Started recording channel: {channel.name}")
            
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
    
    async def _stop_recording(self, channel: discord.VoiceChannel):
        """Stop recording a voice channel."""
        if channel.id not in self._recording_channels:
            return
        
        try:
            vc = channel.guild.voice_client
            if vc and vc.is_connected():
                vc.stop_recording()
                await vc.disconnect()
            
            # Flush all buffers
            await self.transcription_service.flush_all_buffers(channel.id)
            
            self._recording_channels.discard(channel.id)
            logger.info(f"Stopped recording channel: {channel.name}")
            
        except Exception as e:
            logger.error(f"Failed to stop recording: {e}")
    
    async def _recording_callback(self, sink: VoiceSink, channel_id: int):
        """Called when recording is stopped."""
        logger.debug(f"Recording callback for channel {channel_id}")
    
    async def close(self):
        """Clean shutdown."""
        logger.info("Shutting down bot...")
        
        # Stop recording all channels
        for channel_id in list(self._recording_channels):
            # Get channel
            for guild in self.guilds:
                channel = guild.get_channel(channel_id)
                if channel:
                    await self._stop_recording(channel)
                    break
        
        # Stop background services
        await self.transcription_service.stop_monitor()
        await self.session_manager.stop_timeout_monitor()
        
        await super().close()
