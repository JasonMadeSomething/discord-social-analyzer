"""Voice channel control commands for the Discord bot."""
import discord
from discord import ApplicationContext, Option
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)


class VoiceCommands(commands.Cog):
    """Commands for controlling bot voice channel presence."""
    
    def __init__(self, bot):
        self.bot = bot
        self.transcription_service = bot.transcription_service
    
    @discord.slash_command(
        name="summon",
        description="Summon the bot to your current voice channel to start recording"
    )
    async def summon(self, ctx: ApplicationContext):
        # Check if user is in a voice channel
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.respond("❌ You must be in a voice channel to summon the bot!")
            return
        
        channel = ctx.author.voice.channel
        
        # Check if bot is already in a voice channel in this guild
        if ctx.guild.voice_client:
            if ctx.guild.voice_client.channel.id == channel.id:
                await ctx.respond(f"✅ I'm already in {channel.name}!")
                return
            else:
                await ctx.respond(f"⚠️ I'm already in {ctx.guild.voice_client.channel.name}. Use `/dismiss` first to move me.")
                return
        
        try:
            # Join the channel
            await ctx.respond(f"🎙️ Joining {channel.name}...")
            
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
            await ctx.followup.send(
                f"✅ Now recording in **{channel.name}** with {participant_count} participant(s)!\n"
                f"💬 I'll transcribe your conversations automatically."
            )
            
        except Exception as e:
            logger.error(f"Failed to join voice channel: {e}", exc_info=True)
            await ctx.followup.send(f"❌ Failed to join the voice channel: {e}")
    
    @discord.slash_command(
        name="dismiss",
        description="Dismiss the bot from the voice channel and stop recording"
    )
    async def dismiss(self, ctx: ApplicationContext):
        # Defer immediately to prevent interaction timeout
        await ctx.defer()
        
        if not ctx.guild.voice_client:
            await ctx.followup.send("❌ I'm not in a voice channel!")
            return
        
        channel = ctx.guild.voice_client.channel
        
        try:
            # Stop recording and disconnect
            await self.bot._stop_recording(channel)
            
            await ctx.followup.send(f"✅ Left {channel.name} and stopped recording.")
            
        except Exception as e:
            logger.error(f"Failed to leave voice channel: {e}", exc_info=True)
            await ctx.followup.send(f"❌ Failed to leave the voice channel: {e}")
    
    @discord.slash_command(
        name="move",
        description="Move the bot to your current voice channel"
    )
    async def move(self, ctx: ApplicationContext):
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.respond("❌ You must be in a voice channel to move the bot!")
            return
        
        # If bot is in a channel, leave it first
        if ctx.guild.voice_client:
            old_channel = ctx.guild.voice_client.channel
            await self.bot._stop_recording(old_channel)
            await ctx.respond(f"📦 Left {old_channel.name}")
        else:
            await ctx.respond("Moving to your channel...")
        
        # Now join the new channel
        await self.summon(ctx)
    
    @discord.slash_command(
        name="swapprovider",
        description="Hot-swap the transcription provider without restarting"
    )
    async def swap_provider(
        self,
        ctx: ApplicationContext,
        provider: Option(
            str,
            description="Choose transcription provider",
            choices=["whisper", "vosk"]
        )
    ):
        provider = provider.lower()
        current_provider = self.transcription_service.get_current_provider()
        
        # Check if already using this provider
        if (provider == 'whisper' and 'Whisper' in current_provider) or \
           (provider == 'vosk' and 'Vosk' in current_provider):
            await ctx.respond(f"ℹ️ Already using **{current_provider}**!")
            return
        
        try:
            await ctx.respond(f"🔄 Swapping from **{current_provider}** to **{provider.title()}**...\n"
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
            
            await ctx.followup.send(
                f"✅ **Provider swap complete!**\n"
                f"📊 **Old Provider:** {result['old_provider']}\n"
                f"📊 **New Provider:** {result['new_provider']}\n"
                f"🔢 **Buffers Processed:** {result['buffers_processed']}\n\n"
                f"All new audio will now be transcribed using **{result['new_provider']}**!"
            )
            
            logger.info(f"Provider swapped by {ctx.author.name}: {result}")
            
        except Exception as e:
            logger.error(f"Failed to swap provider: {e}", exc_info=True)
            await ctx.followup.send(f"❌ Failed to swap provider: {e}")
    
    @discord.slash_command(
        name="provider",
        description="Show the current transcription provider"
    )
    async def show_provider(self, ctx: ApplicationContext):
        current_provider = self.transcription_service.get_current_provider()
        
        provider_info = {
            'WhisperProvider': '🎯 **Whisper** - High accuracy, GPU recommended',
            'VoskProvider': '⚡ **Vosk** - Fast, CPU-friendly, offline'
        }
        
        info = provider_info.get(current_provider, current_provider)
        
        await ctx.respond(
            f"**Current Transcription Provider:**\n{info}\n\n"
            f"💡 Use `/swapprovider` to switch providers without restarting!"
        )


async def setup(bot):
    """Add the cog to the bot."""
    await bot.add_cog(VoiceCommands(bot))
