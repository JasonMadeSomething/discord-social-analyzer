from discord.ext import commands
import discord
from discord import ApplicationContext, Option
from datetime import datetime, timedelta
import logging

from src.repositories.session_repo import SessionRepository
from src.repositories.utterance_repo import UtteranceRepository
from src.repositories.message_repo import MessageRepository

logger = logging.getLogger(__name__)


class AnalysisCommands(commands.Cog):
    """Commands for analyzing collected conversation data."""
    
    def __init__(
        self,
        bot: commands.Bot,
        session_repo: SessionRepository,
        utterance_repo: UtteranceRepository,
        message_repo: MessageRepository
    ):
        self.bot = bot
        self.session_repo = session_repo
        self.utterance_repo = utterance_repo
        self.message_repo = message_repo
    
    @discord.slash_command(
        name="stats",
        description="View session statistics"
    )
    async def session_stats(
        self,
        ctx: ApplicationContext,
        session_number: Option(
            int,
            description="Session number (1 = most recent)",
            required=False,
            default=1
        )
    ):
        try:
            # Get recent sessions for this channel
            channel_id = ctx.channel.id
            
            # Try to find voice channel in guild
            voice_channel_id = None
            for vc in ctx.guild.voice_channels:
                session_id = self.bot.session_manager.get_active_session(vc.id)
                if session_id:
                    voice_channel_id = vc.id
                    break
            
            if not voice_channel_id:
                # Get most recent session from any voice channel
                sessions = []
                for vc in ctx.guild.voice_channels:
                    sessions.extend(self.session_repo.get_sessions_by_channel(vc.id, limit=5))
                
                if not sessions:
                    await ctx.respond("No sessions found for this server.")
                    return
                
                sessions.sort(key=lambda s: s.started_at, reverse=True)
            else:
                sessions = self.session_repo.get_sessions_by_channel(voice_channel_id, limit=10)
            
            if session_number > len(sessions):
                await ctx.respond(f"Only {len(sessions)} sessions available.")
                return
            
            session = sessions[session_number - 1]
            
            # Get conversation stats
            stats = self.utterance_repo.get_conversation_stats(session.session_id)
            
            # Build embed
            embed = discord.Embed(
                title=f"Session Stats: {session.channel_name}",
                color=discord.Color.blue(),
                timestamp=session.started_at
            )
            
            embed.add_field(
                name="Duration",
                value=f"{session.duration / 60:.1f} minutes" if session.duration else "Ongoing",
                inline=True
            )
            
            embed.add_field(
                name="Participants",
                value=str(len(session.participants)),
                inline=True
            )
            
            embed.add_field(
                name="Status",
                value=session.status.value.title(),
                inline=True
            )
            
            if stats:
                # Sort by speaking time
                stats.sort(key=lambda x: x['total_speaking_time'], reverse=True)
                
                participation_text = ""
                for s in stats[:10]:  # Top 10 speakers
                    participation_text += (
                        f"**{s['username']}**: "
                        f"{s['utterance_count']} utterances, "
                        f"{s['total_speaking_time']:.1f}s speaking time\n"
                    )
                
                embed.add_field(
                    name="Participation",
                    value=participation_text or "No data",
                    inline=False
                )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in stats command: {e}", exc_info=True)
            await ctx.respond(f"Error retrieving stats: {str(e)}")
    
    @discord.slash_command(
        name="transcript",
        description="Get conversation transcript"
    )
    async def get_transcript(
        self,
        ctx: ApplicationContext,
        session_number: Option(
            int,
            description="Session number (1 = most recent)",
            required=False,
            default=1
        ),
        limit: Option(
            int,
            description="Maximum utterances to show",
            required=False,
            default=50
        )
    ):
        try:
            # Get sessions similar to stats command
            voice_channel_id = None
            for vc in ctx.guild.voice_channels:
                session_id = self.bot.session_manager.get_active_session(vc.id)
                if session_id:
                    voice_channel_id = vc.id
                    break
            
            if not voice_channel_id:
                sessions = []
                for vc in ctx.guild.voice_channels:
                    sessions.extend(self.session_repo.get_sessions_by_channel(vc.id, limit=5))
                
                if not sessions:
                    await ctx.respond("No sessions found.")
                    return
                
                sessions.sort(key=lambda s: s.started_at, reverse=True)
            else:
                sessions = self.session_repo.get_sessions_by_channel(voice_channel_id, limit=10)
            
            if session_number > len(sessions):
                await ctx.respond(f"Only {len(sessions)} sessions available.")
                return
            
            session = sessions[session_number - 1]
            
            # Get utterances
            utterances = self.utterance_repo.get_utterances_by_session(
                session.session_id,
                limit=limit
            )
            
            if not utterances:
                await ctx.respond("No utterances found for this session.")
                return
            
            # Build transcript
            transcript_lines = []
            for utt in utterances:
                timestamp = utt.started_at.strftime("%H:%M:%S")
                transcript_lines.append(f"[{timestamp}] **{utt.username}**: {utt.text}")
            
            # Split into chunks if too long
            transcript = "\n".join(transcript_lines)
            
            if len(transcript) > 1900:
                # Split and send multiple messages
                chunks = []
                current_chunk = ""
                for line in transcript_lines:
                    if len(current_chunk) + len(line) + 1 > 1900:
                        chunks.append(current_chunk)
                        current_chunk = line
                    else:
                        current_chunk += "\n" + line if current_chunk else line
                
                if current_chunk:
                    chunks.append(current_chunk)
                
                await ctx.respond(f"**Transcript for {session.channel_name}** (showing {len(utterances)} utterances):")
                for chunk in chunks:
                    await ctx.followup.send(chunk)
            else:
                await ctx.respond(
                    f"**Transcript for {session.channel_name}** "
                    f"(showing {len(utterances)} utterances):\n\n{transcript}"
                )
            
        except Exception as e:
            logger.error(f"Error in transcript command: {e}", exc_info=True)
            await ctx.respond(f"Error retrieving transcript: {str(e)}")
    
    @discord.slash_command(
        name="search",
        description="Search utterances by text content"
    )
    async def search_utterances(
        self,
        ctx: ApplicationContext,
        query: Option(str, description="Text to search for")
    ):
        try:
            utterances = self.utterance_repo.search_utterances(query, limit=20)
            
            if not utterances:
                await ctx.respond(f"No results found for: {query}")
                return
            
            embed = discord.Embed(
                title=f"Search Results: '{query}'",
                description=f"Found {len(utterances)} results",
                color=discord.Color.green()
            )
            
            for utt in utterances[:10]:  # Show top 10
                timestamp = utt.started_at.strftime("%Y-%m-%d %H:%M")
                embed.add_field(
                    name=f"{utt.username} - {timestamp}",
                    value=utt.text[:100] + ("..." if len(utt.text) > 100 else ""),
                    inline=False
                )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in search command: {e}", exc_info=True)
            await ctx.respond(f"Error searching: {str(e)}")
    
    @discord.slash_command(
        name="sessions",
        description="List recent sessions"
    )
    async def list_sessions(
        self,
        ctx: ApplicationContext,
        limit: Option(
            int,
            description="Number of sessions to show",
            required=False,
            default=10
        ),
        show_summary: Option(
            bool,
            description="Include topic summaries",
            required=False,
            default=False
        )
    ):
        try:
            # Get all sessions from voice channels
            all_sessions = []
            for vc in ctx.guild.voice_channels:
                sessions = self.session_repo.get_sessions_by_channel(vc.id, limit=limit)
                all_sessions.extend(sessions)
            
            # Sort by start time
            all_sessions.sort(key=lambda s: s.started_at, reverse=True)
            all_sessions = all_sessions[:limit]
            
            if not all_sessions:
                await ctx.respond("No sessions found.")
                return
            
            embed = discord.Embed(
                title="Recent Sessions",
                description=f"Showing {len(all_sessions)} most recent sessions",
                color=discord.Color.blue()
            )
            
            for i, session in enumerate(all_sessions, 1):
                duration = f"{session.duration / 60:.1f} min" if session.duration else "Ongoing"
                status_emoji = "🟢" if session.status.value == "active" else "⚫"
                
                # Generate session title/summary if requested
                session_title = ""
                if show_summary:
                    session_title = self._generate_session_title(session.session_id)
                    if session_title:
                        session_title = f"\n**Topic:** {session_title}"
                
                embed.add_field(
                    name=f"{i}. {session.channel_name} {status_emoji}",
                    value=(
                        f"Started: {session.started_at.strftime('%Y-%m-%d %H:%M')}\n"
                        f"Duration: {duration}\n"
                        f"Participants: {len(session.participants)}"
                        f"{session_title}"
                    ),
                    inline=False
                )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in sessions command: {e}", exc_info=True)
            await ctx.respond(f"Error listing sessions: {str(e)}")
    
    def _generate_session_title(self, session_id: str) -> str:
        """Generate a brief title/summary for a session based on top keywords."""
        try:
            utterances = self.utterance_repo.get_utterances_by_session(session_id)
            
            if not utterances or len(utterances) < 3:
                return "Brief conversation"
            
            # Extract top keywords
            from collections import Counter
            stopwords = {
                'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                'of', 'with', 'is', 'was', 'are', 'were', 'been', 'be', 'have', 'has',
                'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could', 'can',
                'i', 'you', 'he', 'she', 'it', 'we', 'they', 'this', 'that', 'my',
                'your', 'um', 'uh', 'oh', 'okay', 'ok', 'well', 'like', 'yeah', 'just'
            }
            
            word_counts = Counter()
            for utt in utterances:
                words = utt.text.lower().split()
                for word in words:
                    word = word.strip('.,!?;:"\'()[]{}').lower()
                    if len(word) > 3 and word not in stopwords and word.isalpha():
                        word_counts[word] += 1
            
            # Get top 3 keywords
            top_keywords = [word for word, _ in word_counts.most_common(3)]
            
            if not top_keywords:
                return "General discussion"
            
            # Create title from keywords
            return ", ".join(top_keywords).title()
            
        except Exception as e:
            logger.error(f"Error generating session title: {e}")
            return "Discussion"
    
    @discord.slash_command(
        name="help",
        description="Show available commands and usage"
    )
    async def help_command(self, ctx: ApplicationContext):
        embed = discord.Embed(
            title="Discord Social Analyzer - Commands",
            description="Available slash commands for analyzing conversations",
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name="/stats [session_number]",
            value="Get statistics for a session (default: most recent)",
            inline=False
        )
        
        embed.add_field(
            name="/transcript [session_number] [limit]",
            value="Get transcript of a session",
            inline=False
        )
        
        embed.add_field(
            name="/search <query>",
            value="Search utterances by text content",
            inline=False
        )
        
        embed.add_field(
            name="/sessions [limit] [show_summary]",
            value="List recent sessions with optional topic summaries",
            inline=False
        )
        
        await ctx.respond(embed=embed)


async def setup(bot: commands.Bot):
    """Setup function to add cog to bot."""
    # This will be called from main when initializing
    pass
