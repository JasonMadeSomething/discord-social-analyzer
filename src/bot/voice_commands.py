"""Voice channel control commands for the Discord bot."""
import discord
from discord.ext import commands
import logging
from src.config import settings

logger = logging.getLogger(__name__)


class VoiceCommands(commands.Cog):
    """Commands for controlling bot voice channel presence."""
    
    def __init__(self, bot):
        self.bot = bot
        self.transcription_service = bot.transcription_service
    
    @commands.command(name='summon', aliases=['join'])
    async def summon(self, ctx):
        """
        Summon the bot to your current voice channel.
        
        Usage: !summon or !join
        
        The bot will join your voice channel and start recording/transcribing.
        You must be in a voice channel to use this command.
        """
        # Check if user is in a voice channel
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("❌ You must be in a voice channel to summon the bot!")
            return
        
        channel = ctx.author.voice.channel
        
        # Check if bot is already in a voice channel in this guild
        if ctx.guild.voice_client:
            if ctx.guild.voice_client.channel.id == channel.id:
                await ctx.send(f"✅ I'm already in {channel.name}!")
                return
            else:
                await ctx.send(f"⚠️ I'm already in {ctx.guild.voice_client.channel.name}. Use `!dismiss` first to move me.")
                return
        
        try:
            # Join the channel
            await ctx.send(f"🎙️ Joining {channel.name}...")
            
            # Trigger the bot's join logic
            await self.bot._start_recording(channel)
            
            # Create session for all current members (excluding the bot)
            session_id = self.bot.session_manager.get_active_session(channel.id)
            if not session_id:
                session_id = self.bot.session_manager.start_session(
                    channel_id=channel.id,
                    channel_name=channel.name,
                    guild_id=channel.guild.id
                )
            
            # Add all current members as participants
            for member in channel.members:
                if not member.bot:
                    self.bot.session_manager.add_participant(
                        channel_id=channel.id,
                        user_id=member.id,
                        username=member.name,
                        display_name=member.display_name or member.name
                    )
            
            participant_count = len([m for m in channel.members if not m.bot])
            await ctx.send(
                f"✅ Now recording in **{channel.name}** with {participant_count} participant(s)!\n"
                f"💬 I'll transcribe your conversations automatically."
            )
            
        except Exception as e:
            logger.error(f"Failed to join voice channel: {e}", exc_info=True)
            await ctx.send(f"❌ Failed to join the voice channel: {e}")
    
    @commands.command(name='dismiss', aliases=['leave', 'stop'])
    async def dismiss(self, ctx):
        """
        Dismiss the bot from the voice channel.
        
        Usage: !dismiss, !leave, or !stop
        
        The bot will stop recording and leave the voice channel.
        """
        if not ctx.guild.voice_client:
            await ctx.send("❌ I'm not in a voice channel!")
            return
        
        channel = ctx.guild.voice_client.channel
        
        try:
            await ctx.send(f"👋 Leaving {channel.name}...")
            
            # Stop recording and disconnect
            await self.bot._stop_recording(channel)
            
            await ctx.send("✅ Recording stopped and left the voice channel.")
            
        except Exception as e:
            logger.error(f"Failed to leave voice channel: {e}", exc_info=True)
            await ctx.send(f"❌ Failed to leave the voice channel: {e}")
    
    @commands.command(name='move')
    async def move(self, ctx):
        """
        Move the bot to your current voice channel.
        
        Usage: !move
        
        Convenience command that dismisses from current channel and joins yours.
        """
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("❌ You must be in a voice channel to move the bot!")
            return
        
        # If bot is in a channel, leave it first
        if ctx.guild.voice_client:
            old_channel = ctx.guild.voice_client.channel
            await self.bot._stop_recording(old_channel)
            await ctx.send(f"📦 Left {old_channel.name}")
        
        # Now join the new channel
        await self.summon(ctx)
    
    @commands.command(name='swapprovider', aliases=['switchprovider'])
    async def swap_provider(self, ctx, provider: str):
        """
        Hot-swap the transcription provider without restarting.
        
        Usage: !swapprovider <whisper|vosk>
        
        This will:
        1. Process all in-flight audio buffers with the current provider
        2. Switch to the new provider
        3. All new audio will use the new provider
        
        No restart required!
        """
        provider = provider.lower()
        
        if provider not in ['whisper', 'vosk']:
            await ctx.send("❌ Invalid provider! Choose `whisper` or `vosk`.")
            return
        
        current_provider = self.transcription_service.get_current_provider()
        
        # Check if already using this provider
        if (provider == 'whisper' and 'Whisper' in current_provider) or \
           (provider == 'vosk' and 'Vosk' in current_provider):
            await ctx.send(f"ℹ️ Already using **{current_provider}**!")
            return
        
        try:
            await ctx.send(f"🔄 Swapping from **{current_provider}** to **{provider.title()}**...\n"
                          f"⏳ Processing in-flight buffers...")
            
            # Create the new provider instance
            if provider == 'whisper':
                from src.providers.whisper_provider import WhisperProvider
                new_provider = WhisperProvider()
            else:  # vosk
                from src.providers.vosk_provider import VoskProvider
                new_provider = VoskProvider()
            
            # Perform the swap
            result = await self.transcription_service.swap_provider(new_provider)
            
            await ctx.send(
                f"✅ **Provider swap complete!**\n"
                f"📊 **Old Provider:** {result['old_provider']}\n"
                f"📊 **New Provider:** {result['new_provider']}\n"
                f"🔢 **Buffers Processed:** {result['buffers_processed']}\n\n"
                f"All new audio will now be transcribed using **{result['new_provider']}**!"
            )
            
            logger.info(f"Provider swapped by {ctx.author.name}: {result}")
            
        except Exception as e:
            logger.error(f"Failed to swap provider: {e}", exc_info=True)
            await ctx.send(f"❌ Failed to swap provider: {e}")
    
    @commands.command(name='provider')
    async def show_provider(self, ctx):
        """
        Show the current transcription provider.
        
        Usage: !provider
        """
        current_provider = self.transcription_service.get_current_provider()
        
        provider_info = {
            'WhisperProvider': '🎯 **Whisper** - High accuracy, GPU recommended',
            'VoskProvider': '⚡ **Vosk** - Fast, CPU-friendly, offline'
        }
        
        info = provider_info.get(current_provider, current_provider)
        
        await ctx.send(
            f"**Current Transcription Provider:**\n{info}\n\n"
            f"💡 Use `!swapprovider <whisper|vosk>` to switch providers without restarting!"
        )


async def setup(bot):
    """Add the cog to the bot."""
    await bot.add_cog(VoiceCommands(bot))
