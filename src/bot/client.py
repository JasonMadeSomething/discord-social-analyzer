import discord
from discord.ext import commands
import discord.sinks
import numpy as np
import logging
from typing import Optional
from datetime import datetime
import asyncio

from src.services.transcription import TranscriptionService
from src.services.session_manager import SessionManager
from src.repositories.message_repo import MessageRepository
from src.config import settings

logger = logging.getLogger(__name__)


class AudioSink(discord.sinks.Sink):
    """Custom audio sink to capture voice data per user."""
    
    def __init__(self, transcription_service: TranscriptionService, channel_id: int, bot_loop):
        super().__init__()
        self.transcription_service = transcription_service
        self.channel_id = channel_id
        self.bot_loop = bot_loop  # Store the bot's event loop
        self._tasks = set()
    
    @discord.sinks.Filters.container
    def write(self, data, user):
        """
        Called when audio data is received from a user.
        
        Args:
            data: Audio data (PCM bytes)
            user: User ID (integer)
        """
        # Call parent write to maintain Pycord's internal audio storage
        super().write(data, user)
        
        logger.debug(f"AudioSink.write() called for user ID {user}")
        
        if not data:
            logger.debug("No audio data in write() call")
            return
        
        try:
            # Get the actual user object from the voice client
            user_obj = None
            if self.vc and hasattr(self.vc, 'guild'):
                user_obj = self.vc.guild.get_member(user)
            
            if not user_obj:
                logger.warning(f"Could not find user object for ID {user}")
                return
            
            # Convert PCM audio bytes to numpy array
            # Pycord sends raw PCM data
            audio_array = np.frombuffer(data, dtype=np.int16)
            logger.debug(f"Received {len(audio_array)} audio samples from {user_obj.name}")
            
            # Convert stereo to mono if needed (Discord typically sends stereo)
            # Simple approach: take left channel (every other sample)
            if len(audio_array) > 1:
                audio_mono = audio_array[::2]
            else:
                audio_mono = audio_array
            
            # Convert to float32 in range [-1, 1]
            audio_float = audio_mono.astype(np.float32) / 32768.0
            
            # Schedule the coroutine on the bot's event loop (thread-safe)
            asyncio.run_coroutine_threadsafe(
                self.transcription_service.add_audio(
                    channel_id=self.channel_id,
                    user_id=user_obj.id,
                    username=user_obj.name,
                    display_name=user_obj.display_name or user_obj.name,
                    audio_data=audio_float
                ),
                self.bot_loop
            )
            
        except Exception as e:
            logger.error(f"Error processing audio data: {e}", exc_info=True)
    
    def format_audio(self, audio):
        """Format audio data. Required by parent Sink class but we don't need it."""
        pass
    
    def cleanup(self):
        """Called when recording is stopped."""
        super().cleanup()
        # Wait for any pending tasks
        if self._tasks:
            logger.debug(f"Waiting for {len(self._tasks)} audio processing tasks to complete")


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
        if channel.id not in self._recording_channels:
            await self._start_recording(channel)
    
    async def _handle_user_leave(self, member: discord.Member, channel: discord.VoiceChannel):
        """Handle user leaving a voice channel."""
        logger.info(f"{member.name} left {channel.name}")
        
        # Flush their audio buffer
        await self.transcription_service.flush_buffer(channel.id, member.id)
        
        # Remove participant
        self.session_manager.remove_participant(channel.id, member.id)
        
        # Stop recording if channel is empty (only bot remains)
        remaining_members = [m.name for m in channel.members]
        remaining_member_ids = [m.id for m in channel.members]
        logger.info(f"Remaining members in {channel.name}: {remaining_members}")
        logger.info(f"Remaining member IDs: {remaining_member_ids}")
        logger.info(f"Bot user ID: {self.user.id}")
        logger.info(f"Bot in channel: {self.user.id in remaining_member_ids}")
        logger.info(f"Member count: {len(channel.members)}")
        
        # Check if only the bot remains in the channel
        if len(channel.members) == 1 and self.user.id in remaining_member_ids:
            logger.info(f"Channel {channel.name} is empty except for bot, stopping recording")
            await self._stop_recording(channel)
        else:
            logger.info(f"Channel {channel.name} still has users, keeping recording active")
    
    async def _start_recording(self, channel: discord.VoiceChannel):
        """Start recording a voice channel."""
        logger.info(f"Current recording channels: {list(self._recording_channels)}")
        
        if channel.id in self._recording_channels:
            logger.debug(f"Already recording channel {channel.name}")
            return
        
        logger.info(f"Attempting to start recording for channel: {channel.name}")
        
        try:
            # Connect if not connected
            vc = channel.guild.voice_client
            if not vc or not vc.is_connected():
                logger.info(f"Connecting to voice channel {channel.name}")
                vc = await channel.connect()
                logger.info(f"Successfully connected to voice channel {channel.name}")
            else:
                logger.info(f"Already connected to voice channel {channel.name}")
            
            # Check if we're already recording
            if hasattr(vc, '_sink') and vc._sink:
                logger.info(f"Already recording in channel {channel.name}")
                self._recording_channels.add(channel.id)
                return
            
            # Create sink
            sink = AudioSink(self.transcription_service, channel.id, self.loop)
            logger.info(f"Created audio sink for channel {channel.name}")
            
            # Start recording using Pycord's start_recording method
            async def recording_callback(sink):
                """Called when recording stops."""
                logger.info(f"Recording callback called for channel {channel.name}")
            
            logger.info(f"Calling vc.start_recording()")
            vc.start_recording(sink, recording_callback)
            vc._sink = sink  # Store reference to prevent duplicate recording
            
            self._recording_channels.add(channel.id)
            logger.info(f"Started recording channel: {channel.name}")
            
        except Exception as e:
            logger.error(f"Failed to start recording: {e}", exc_info=True)
    
    async def _stop_recording(self, channel: discord.VoiceChannel):
        """Stop recording a voice channel."""
        if channel.id not in self._recording_channels:
            logger.info(f"Channel {channel.name} not in recording channels, skipping stop")
            return
        
        logger.info(f"Attempting to stop recording for channel: {channel.name}")
        
        try:
            vc = channel.guild.voice_client
            logger.info(f"Voice client found: {vc is not None}")
            logger.info(f"Voice client connected: {vc.is_connected() if vc else 'N/A'}")
            
            if vc and vc.is_connected():
                logger.info("Stopping recording on voice client")
                # Stop recording in a non-blocking way
                try:
                    vc.stop_recording()
                except Exception as e:
                    logger.warning(f"Error stopping recording: {e}")
                
                if hasattr(vc, '_sink'):
                    vc._sink = None
                    
                logger.info("Disconnecting from voice channel")
                await vc.disconnect()
                logger.info("Successfully disconnected from voice channel")
            else:
                logger.info("No active voice client to disconnect")
            
            # Flush all buffers
            await self.transcription_service.flush_all_buffers(channel.id)
            
            self._recording_channels.discard(channel.id)
            logger.info(f"Stopped recording channel: {channel.name}")
            
        except Exception as e:
            logger.error(f"Failed to stop recording: {e}", exc_info=True)
    
    async def close(self):
        """Clean shutdown."""
        logger.info("Shutting down bot...")
        
        # Stop recording all channels and disconnect
        for channel_id in list(self._recording_channels):
            try:
                # Get channel
                for guild in self.guilds:
                    channel = guild.get_channel(channel_id)
                    if channel:
                        logger.info(f"Stopping recording and disconnecting from {channel.name}")
                        await self._stop_recording(channel)
                        break
            except Exception as e:
                logger.error(f"Error stopping recording for channel {channel_id}: {e}")
        
        # Stop background services
        await self.transcription_service.stop_monitor()
        await self.session_manager.stop_timeout_monitor()
        
        await super().close()
