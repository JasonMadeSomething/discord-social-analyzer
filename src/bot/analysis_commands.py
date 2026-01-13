from discord.ext import commands
import discord
from discord import ApplicationContext, Option
import json
import logging

from src.services.analyzer import ConversationAnalyzer
from src.repositories.session_repo import SessionRepository

logger = logging.getLogger(__name__)


class AdvancedAnalysisCommands(commands.Cog):
    """Advanced analysis commands using the ConversationAnalyzer service."""
    
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
        # Try to find active session first
        voice_channel_id = None
        for vc in ctx.guild.voice_channels:
            session_id = self.bot.session_manager.get_active_session(vc.id)
            if session_id:
                return session_id
        
        # Get recent sessions
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
        name="analyze",
        description="Get comprehensive analysis of a session"
    )
    async def full_analysis(
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
            
            await ctx.respond("🔍 Analyzing session... This may take a moment.")
            
            # Generate full analysis
            summary = self.analyzer.generate_session_summary(session_id)
            
            # Create embed
            embed = discord.Embed(
                title=f"📊 Analysis: {summary['channel_name']}",
                color=discord.Color.purple(),
                timestamp=ctx.message.created_at
            )
            
            # Basic info
            duration = summary.get('duration_minutes')
            if duration:
                embed.add_field(
                    name="Duration",
                    value=f"{duration:.1f} minutes",
                    inline=True
                )
            
            embed.add_field(
                name="Participants",
                value=str(summary['participant_count']),
                inline=True
            )
            
            embed.add_field(
                name="Total Utterances",
                value=str(summary['speaking_patterns']['total_utterances']),
                inline=True
            )
            
            # Speaking patterns
            sp = summary['speaking_patterns']
            if sp['participants']:
                top_speakers = sorted(
                    sp['participants'].items(),
                    key=lambda x: x[1]['total_speaking_time'],
                    reverse=True
                )[:3]
                
                speakers_text = ""
                for _, stats in top_speakers:
                    speakers_text += (
                        f"**{stats['username']}**: "
                        f"{stats['speaking_time_percentage']:.1f}% "
                        f"({stats['utterance_count']} utterances)\n"
                    )
                
                embed.add_field(
                    name="🎤 Top Speakers",
                    value=speakers_text,
                    inline=False
                )
            
            # Dominance score
            dominance = sp['dominance_score']
            dominance_label = (
                "Balanced" if dominance < 0.3 else
                "Moderate" if dominance < 0.6 else
                "Dominated"
            )
            embed.add_field(
                name="Balance",
                value=f"{dominance_label} ({dominance:.2f})",
                inline=True
            )
            
            # Response time
            avg_response = summary['turn_taking'].get('avg_response_time')
            if avg_response:
                embed.add_field(
                    name="Avg Response Time",
                    value=f"{avg_response:.2f}s",
                    inline=True
                )
            
            # Top keywords
            if summary['top_keywords']:
                keywords = ", ".join([word for word, _ in summary['top_keywords'][:10]])
                embed.add_field(
                    name="🔑 Top Keywords",
                    value=keywords,
                    inline=False
                )
            
            # Insights
            if summary['insights']:
                insights_text = "\n".join(summary['insights'])
                embed.add_field(
                    name="💡 Insights",
                    value=insights_text,
                    inline=False
                )
            
            await ctx.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in analyze command: {e}", exc_info=True)
            await ctx.followup.send(f"Error during analysis: {str(e)}")
    
    @discord.slash_command(
        name="speaking",
        description="Detailed speaking pattern analysis"
    )
    async def speaking_patterns(
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
            
            patterns = self.analyzer.analyze_speaking_patterns(session_id)
            
            embed = discord.Embed(
                title="🎤 Speaking Patterns",
                color=discord.Color.blue()
            )
            
            # Sort by speaking time
            participants = sorted(
                patterns['participants'].items(),
                key=lambda x: x[1]['total_speaking_time'],
                reverse=True
            )
            
            for _, stats in participants:
                field_value = (
                    f"Speaking time: {stats['total_speaking_time']:.1f}s "
                    f"({stats['speaking_time_percentage']:.1f}%)\n"
                    f"Utterances: {stats['utterance_count']}\n"
                    f"Avg length: {stats['avg_utterance_length']:.1f}s\n"
                    f"Confidence: {stats['avg_confidence']:.2f}"
                )
                
                embed.add_field(
                    name=stats['username'],
                    value=field_value,
                    inline=True
                )
            
            # Overall metrics
            embed.add_field(
                name="📊 Overall",
                value=(
                    f"Total speaking time: {patterns['total_speaking_time']:.1f}s\n"
                    f"Total utterances: {patterns['total_utterances']}\n"
                    f"Dominance score: {patterns['dominance_score']:.2f}"
                ),
                inline=False
            )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in speaking command: {e}", exc_info=True)
            await ctx.respond(f"Error analyzing speaking patterns: {str(e)}")
    
    @discord.slash_command(
        name="turns",
        description="Analyze turn-taking patterns"
    )
    async def turn_taking(
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
            
            turn_data = self.analyzer.analyze_turn_taking(session_id)
            
            embed = discord.Embed(
                title="🔄 Turn-Taking Analysis",
                color=discord.Color.green()
            )
            
            # Response time stats
            if turn_data['avg_response_time']:
                stats = turn_data['response_time_stats']
                embed.add_field(
                    name="⏱️ Response Times",
                    value=(
                        f"Average: {stats['mean']:.2f}s\n"
                        f"Median: {stats['median']:.2f}s\n"
                        f"Range: {stats['min']:.2f}s - {stats['max']:.2f}s"
                    ),
                    inline=False
                )
            
            # Turn counts
            if turn_data['turn_counts']:
                turns_text = ""
                for username, count in sorted(
                    turn_data['turn_counts'].items(),
                    key=lambda x: x[1],
                    reverse=True
                ):
                    turns_text += f"**{username}**: {count} turns\n"
                
                embed.add_field(
                    name="🎯 Turn Counts",
                    value=turns_text,
                    inline=False
                )
            
            # Most common transitions
            if turn_data['transitions']:
                transitions_list = []
                for from_user, to_users in turn_data['transitions'].items():
                    for to_user, count in to_users.items():
                        if from_user != to_user:  # Skip self-transitions
                            transitions_list.append((from_user, to_user, count))
                
                # Sort by count
                transitions_list.sort(key=lambda x: x[2], reverse=True)
                
                if transitions_list:
                    trans_text = ""
                    for from_u, to_u, count in transitions_list[:5]:
                        trans_text += f"{from_u} → {to_u}: {count}\n"
                    
                    embed.add_field(
                        name="🔗 Common Transitions",
                        value=trans_text,
                        inline=False
                    )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in turns command: {e}", exc_info=True)
            await ctx.respond(f"Error analyzing turn-taking: {str(e)}")
    
    @discord.slash_command(
        name="interactions",
        description="Analyze interaction patterns (who responds to whom)"
    )
    async def interactions(
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
            
            interaction_data = self.analyzer.analyze_interactions(session_id)
            
            embed = discord.Embed(
                title="🤝 Interaction Patterns",
                color=discord.Color.gold()
            )
            
            # Overall interaction counts
            if interaction_data['interaction_counts']:
                counts_text = ""
                for username, count in sorted(
                    interaction_data['interaction_counts'].items(),
                    key=lambda x: x[1],
                    reverse=True
                ):
                    counts_text += f"**{username}**: {count} interactions\n"
                
                embed.add_field(
                    name="📊 Interaction Counts",
                    value=counts_text,
                    inline=False
                )
            
            # Interaction pairs
            if interaction_data['interaction_graph']:
                pairs = []
                for user1, partners in interaction_data['interaction_graph'].items():
                    for user2, count in partners.items():
                        if user1 < user2:  # Avoid duplicates
                            pairs.append((user1, user2, count))
                
                pairs.sort(key=lambda x: x[2], reverse=True)
                
                if pairs:
                    pairs_text = ""
                    for u1, u2, count in pairs[:8]:
                        pairs_text += f"{u1} ↔ {u2}: {count}\n"
                    
                    embed.add_field(
                        name="👥 Interaction Pairs",
                        value=pairs_text,
                        inline=False
                    )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in interactions command: {e}", exc_info=True)
            await ctx.respond(f"Error analyzing interactions: {str(e)}")
    
    @discord.slash_command(
        name="keywords",
        description="Extract most common keywords from a session"
    )
    async def keywords(
        self,
        ctx: ApplicationContext,
        session_number: Option(
            int,
            description="Session number (1 = most recent)",
            required=False,
            default=1
        ),
        count: Option(
            int,
            description="Number of keywords to show",
            required=False,
            default=20
        )
    ):
        try:
            session_id = self._get_session_id(ctx, session_number)
            
            if not session_id:
                await ctx.respond("No session found.")
                return
            
            keywords = self.analyzer.extract_keywords(session_id, top_n=count)
            
            if not keywords:
                await ctx.respond("No keywords found.")
                return
            
            embed = discord.Embed(
                title="🔑 Conversation Keywords",
                color=discord.Color.teal()
            )
            
            # Split into columns
            col1 = []
            col2 = []
            
            for i, (word, count) in enumerate(keywords):
                entry = f"**{word}**: {count}"
                if i < len(keywords) // 2:
                    col1.append(entry)
                else:
                    col2.append(entry)
            
            if col1:
                embed.add_field(
                    name="Top Words",
                    value="\n".join(col1),
                    inline=True
                )
            
            if col2:
                embed.add_field(
                    name="\u200b",  # Invisible character for spacing
                    value="\n".join(col2),
                    inline=True
                )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in keywords command: {e}", exc_info=True)
            await ctx.respond(f"Error extracting keywords: {str(e)}")
    
    @discord.slash_command(
        name="myactivity",
        description="View your participation across recent sessions"
    )
    async def user_activity(
        self,
        ctx: ApplicationContext,
        session_count: Option(
            int,
            description="Number of recent sessions to analyze",
            required=False,
            default=5
        )
    ):
        try:
            user_id = ctx.author.id
            
            comparison = self.analyzer.compare_user_across_sessions(
                user_id=user_id,
                limit=session_count
            )
            
            if comparison['sessions_analyzed'] == 0:
                await ctx.respond("No activity found for you.")
                return
            
            embed = discord.Embed(
                title=f"📈 Your Activity",
                description=f"Analysis of your last {comparison['sessions_analyzed']} sessions",
                color=discord.Color.blue()
            )
            
            # Overall stats
            embed.add_field(
                name="Overall",
                value=(
                    f"Total utterances: {comparison['total_utterances']}\n"
                    f"Total speaking time: {comparison['total_speaking_time']:.1f}s\n"
                    f"Trend: {comparison['trend']}"
                ),
                inline=False
            )
            
            # Per-session stats
            for session in comparison['session_stats']:
                embed.add_field(
                    name=f"Session {session['date']}",
                    value=(
                        f"Utterances: {session['utterance_count']}\n"
                        f"Speaking time: {session['speaking_time']:.1f}s\n"
                        f"Confidence: {session['avg_confidence']:.2f}"
                    ),
                    inline=True
                )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in myactivity command: {e}", exc_info=True)
            await ctx.respond(f"Error retrieving activity: {str(e)}")
    
    @discord.slash_command(
        name="export",
        description="Export full analysis as JSON file"
    )
    async def export_analysis(
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
            
            summary = self.analyzer.generate_session_summary(session_id)
            
            # Convert to JSON
            json_data = json.dumps(summary, indent=2, default=str)
            
            # Save to file
            filename = f"analysis_{session_id[:8]}.json"
            with open(filename, 'w') as f:
                f.write(json_data)
            
            # Send file
            await ctx.respond(
                "📊 Analysis exported:",
                file=discord.File(filename)
            )
            
        except Exception as e:
            logger.error(f"Error in export command: {e}", exc_info=True)
            await ctx.respond(f"Error exporting analysis: {str(e)}")


async def setup(bot: commands.Bot):
    """Setup function for the cog."""
    pass
