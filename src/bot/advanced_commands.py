from discord.ext import commands
import discord
from discord import ApplicationContext, Option
import logging

from src.services.analyzer import ConversationAnalyzer
from src.repositories.session_repo import SessionRepository

logger = logging.getLogger(__name__)


class DeepAnalysisCommands(commands.Cog):
    """Advanced analysis commands for topics, recaps, and social dynamics."""
    
    def __init__(
        self,
        bot: commands.Bot,
        analyzer: ConversationAnalyzer,
        session_repo: SessionRepository
    ):
        self.bot = bot
        self.analyzer = analyzer
        self.session_repo = session_repo
    
    def _get_session_id(self, ctx: ApplicationContext, session_index: int = 1) -> str:
        """Helper to get session ID from context."""
        for vc in ctx.guild.voice_channels:
            session_id = self.bot.session_manager.get_active_session(vc.id)
            if session_id:
                return session_id
        
        sessions = []
        for vc in ctx.guild.voice_channels:
            sessions.extend(self.session_repo.get_sessions_by_channel(vc.id, limit=10))
        
        if not sessions:
            return None
        
        sessions.sort(key=lambda s: s.started_at, reverse=True)
        
        if session_index > len(sessions):
            return None
        
        return sessions[session_index - 1].session_id
    
    @discord.slash_command(
        name="topics",
        description="Identify conversation topics with keyword clustering"
    )
    async def analyze_topics(
        self,
        ctx: ApplicationContext,
        session_number: Option(
            int,
            description="Session number (1 = most recent)",
            required=False,
            default=1
        ),
        num_topics: Option(
            int,
            description="Number of topics to identify",
            required=False,
            default=5
        )
    ):
        try:
            session_id = self._get_session_id(ctx, session_number)
            
            if not session_id:
                await ctx.respond("No session found.")
                return
            
            await ctx.respond("🔍 Analyzing conversation topics...")
            
            result = self.analyzer.analyze_topics(session_id, num_topics)
            
            if not result['topics']:
                await ctx.followup.send("No topics found. The conversation may be too short.")
                return
            
            embed = discord.Embed(
                title="💬 Conversation Topics",
                description=f"Identified {result['topic_count']} main topics",
                color=discord.Color.blue()
            )
            
            for topic in result['topics']:
                keywords_str = ', '.join(topic['keywords'])
                
                examples_str = ""
                if topic['examples']:
                    examples_str = "\n**Examples:**\n"
                    for ex in topic['examples'][:2]:
                        examples_str += f"• *{ex['username']}*: {ex['text'][:80]}...\n"
                
                embed.add_field(
                    name=f"Topic {topic['topic_id']}: {topic['primary_keyword'].title()}",
                    value=(
                        f"**Keywords:** {keywords_str}\n"
                        f"**Mentions:** {topic['frequency']}"
                        f"{examples_str}"
                    ),
                    inline=False
                )
            
            await ctx.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in topics command: {e}", exc_info=True)
            await ctx.followup.send(f"Error analyzing topics: {str(e)}")
    
    @discord.slash_command(
        name="recap",
        description="Generate a structured recap of the conversation"
    )
    async def conversation_recap(
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
            session_id = self._get_session_id(ctx, session_number)
            
            if not session_id:
                await ctx.respond("No session found.")
                return
            
            await ctx.respond("📝 Generating conversation recap...")
            
            recap = self.analyzer.generate_recap(session_id)
            
            if 'error' in recap:
                await ctx.followup.send(f"Error: {recap['error']}")
                return
            
            # Main embed
            embed = discord.Embed(
                title=f"📝 Conversation Recap: {recap['channel_name']}",
                description=f"Duration: {recap['duration_minutes']:.1f} minutes | {recap['total_utterances']} utterances",
                color=discord.Color.green()
            )
            
            # Timeline
            if recap['timeline']:
                timeline_str = ""
                for segment in recap['timeline'][:5]:  # First 5 segments
                    keywords = ', '.join(segment['top_keywords'][:3])
                    timeline_str += (
                        f"**{segment['start_time']}** ({segment['utterance_count']} utterances)\n"
                        f"Topics: {keywords}\n"
                        f"Speakers: {', '.join(segment['active_speakers'])}\n\n"
                    )
                
                embed.add_field(
                    name="📅 Timeline",
                    value=timeline_str[:1024] if timeline_str else "No timeline data",
                    inline=False
                )
            
            # Key moments
            if recap['key_moments']:
                moments_str = ""
                for moment in recap['key_moments'][:3]:
                    moments_str += f"**{moment['timestamp']}** - {moment['description']}\n"
                
                embed.add_field(
                    name="⭐ Key Moments",
                    value=moments_str[:1024],
                    inline=False
                )
            
            # Highlights
            if recap['highlights']:
                highlights_str = ""
                for highlight in recap['highlights']:
                    highlights_str += (
                        f"**{highlight['type'].title()}** by {highlight['username']}\n"
                        f"*{highlight['text'][:100]}...*\n\n"
                    )
                
                embed.add_field(
                    name="🌟 Highlights",
                    value=highlights_str[:1024],
                    inline=False
                )
            
            # Participants
            if recap['participants']:
                participants_str = ""
                for p in recap['participants'][:5]:
                    participants_str += (
                        f"**{p['username']}**: {p['utterances']} utterances, "
                        f"{p['words']} words, {p['speaking_time_seconds']}s\n"
                    )
                
                embed.add_field(
                    name="👥 Participants",
                    value=participants_str[:1024],
                    inline=False
                )
            
            await ctx.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in recap command: {e}", exc_info=True)
            await ctx.followup.send(f"Error generating recap: {str(e)}")
    
    @discord.slash_command(
        name="dynamics",
        description="Analyze social dynamics and conversation flow"
    )
    async def social_dynamics(
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
            session_id = self._get_session_id(ctx, session_number)
            
            if not session_id:
                await ctx.respond("No session found.")
                return
            
            await ctx.respond("🔬 Analyzing social dynamics...")
            
            dynamics = self.analyzer.analyze_social_dynamics(session_id)
            
            if 'error' in dynamics:
                await ctx.followup.send(f"Error: {dynamics['error']}")
                return
            
            embed = discord.Embed(
                title="🔬 Social Dynamics Analysis",
                color=discord.Color.purple()
            )
            
            # Participant roles
            if dynamics['participant_roles']:
                roles_str = ""
                for role in dynamics['participant_roles']:
                    roles_str += (
                        f"**{role['username']}** - {role['role']}\n"
                        f"*{role['description']}* ({role['participation_rate']}%)\n\n"
                    )
                
                embed.add_field(
                    name="👤 Participant Roles",
                    value=roles_str[:1024],
                    inline=False
                )
            
            # Conversation flow
            if dynamics['conversation_flow']['dominant_flows']:
                flow_str = ""
                for flow in dynamics['conversation_flow']['dominant_flows'][:5]:
                    flow_str += f"{flow['from']} → {flow['to']}: {flow['exchanges']} exchanges\n"
                
                embed.add_field(
                    name="🔄 Conversation Flow",
                    value=flow_str[:1024],
                    inline=False
                )
            
            # Engagement metrics
            if dynamics['engagement_metrics']:
                metrics = dynamics['engagement_metrics']
                metrics_str = (
                    f"**Engagement Score:** {metrics.get('engagement_score', 'N/A')}\n"
                    f"**Avg Gap:** {metrics.get('avg_gap_between_utterances', 'N/A')}s\n"
                    f"**Speaker Diversity:** {metrics.get('avg_speaker_diversity', 'N/A')}\n"
                )
                
                embed.add_field(
                    name="📊 Engagement Metrics",
                    value=metrics_str,
                    inline=False
                )
            
            await ctx.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in dynamics command: {e}", exc_info=True)
            await ctx.followup.send(f"Error analyzing dynamics: {str(e)}")
    
    @discord.slash_command(
        name="influence",
        description="Show influence scores - who drives the conversation"
    )
    async def influence_scores(
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
            session_id = self._get_session_id(ctx, session_number)
            
            if not session_id:
                await ctx.respond("No session found.")
                return
            
            await ctx.respond("📈 Calculating influence scores...")
            
            dynamics = self.analyzer.analyze_social_dynamics(session_id)
            
            if 'error' in dynamics:
                await ctx.followup.send(f"Error: {dynamics['error']}")
                return
            
            influence = dynamics['influence_scores']
            
            if not influence:
                await ctx.followup.send("No influence data available.")
                return
            
            embed = discord.Embed(
                title="📈 Influence Rankings",
                description="Who drives the conversation?",
                color=discord.Color.gold()
            )
            
            for i, score in enumerate(influence[:10], 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                
                details = (
                    f"**Score:** {score['influence_score']}\n"
                    f"Responses triggered: {score['responses_triggered']}\n"
                )
                
                if score['avg_response_time']:
                    details += f"Avg response time: {score['avg_response_time']}s\n"
                
                details += f"Speaking time triggered: {score['speaking_time_triggered']}s"
                
                embed.add_field(
                    name=f"{medal} {score['username']}",
                    value=details,
                    inline=True
                )
            
            embed.set_footer(text="Higher scores = more influential in driving conversation")
            
            await ctx.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in influence command: {e}", exc_info=True)
            await ctx.followup.send(f"Error calculating influence: {str(e)}")


async def setup(bot: commands.Bot):
    """Setup function for the cog."""
    pass
