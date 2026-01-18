"""Diagnostic commands for enrichment engine monitoring."""
import discord
from discord.ext import commands
from discord import ApplicationContext, Option
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DiagnosticCommands(commands.Cog):
    """Commands for diagnosing enrichment engine status."""
    
    def __init__(
        self,
        bot,
        idea_repo=None,
        exchange_repo=None,
        enrichment_queue_repo=None,
        speaker_alias_repo=None,
        session_repo=None
    ):
        """
        Initialize diagnostic commands.
        
        Args:
            bot: Discord bot instance
            idea_repo: IdeaRepository instance
            exchange_repo: ExchangeRepository instance
            enrichment_queue_repo: EnrichmentQueueRepository instance
            speaker_alias_repo: SpeakerAliasRepository instance
            session_repo: SessionRepository instance
        """
        self.bot = bot
        self.idea_repo = idea_repo
        self.exchange_repo = exchange_repo
        self.enrichment_queue_repo = enrichment_queue_repo
        self.speaker_alias_repo = speaker_alias_repo
        self.session_repo = session_repo
    
    @discord.slash_command(
        name="diagnostics",
        description="Show enrichment engine diagnostics"
    )
    async def diagnostics(self, ctx: ApplicationContext):
        """Show diagnostic information about the enrichment engine."""
        try:
            embed = discord.Embed(
                title="🔧 Enrichment Engine Diagnostics",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            # Check if enrichment engine is enabled
            if not self.idea_repo:
                embed.description = "⚠️ Enrichment engine is not initialized"
                await ctx.respond(embed=embed, ephemeral=True)
                return
            
            # Get recent session
            session_id = None
            for vc in ctx.guild.voice_channels:
                sid = self.bot.session_manager.get_active_session(vc.id)
                if sid:
                    session_id = sid
                    break
            
            if not session_id and self.session_repo:
                # Get most recent session
                sessions = []
                for vc in ctx.guild.voice_channels:
                    sessions.extend(self.session_repo.get_sessions_by_channel(vc.id, limit=1))
                if sessions:
                    sessions.sort(key=lambda s: s.started_at, reverse=True)
                    session_id = sessions[0].session_id
            
            # Ideas count
            if session_id:
                ideas = self.idea_repo.get_ideas_by_session(session_id, limit=1000)
                embed.add_field(
                    name="💡 Ideas (Current Session)",
                    value=f"{len(ideas)} ideas created",
                    inline=True
                )
                
                # Sample idea enrichment status
                if ideas:
                    sample_idea = ideas[0]
                    status = sample_idea.enrichment_status
                    status_text = "\n".join([
                        f"• {k.replace('_', ' ').title()}: {v}"
                        for k, v in status.items()
                    ])
                    embed.add_field(
                        name="📊 Sample Enrichment Status",
                        value=status_text or "No status",
                        inline=False
                    )
            else:
                embed.add_field(
                    name="💡 Ideas",
                    value="No active session",
                    inline=True
                )
            
            # Queue status
            if self.enrichment_queue_repo:
                pending = self.enrichment_queue_repo.get_pending_tasks(limit=100)
                embed.add_field(
                    name="📋 Queue",
                    value=f"{len(pending)} pending tasks",
                    inline=True
                )
                
                # Group by task type
                if pending:
                    task_counts = {}
                    for task in pending:
                        task_counts[task.task_type] = task_counts.get(task.task_type, 0) + 1
                    
                    queue_text = "\n".join([
                        f"• {k.replace('_', ' ').title()}: {v}"
                        for k, v in task_counts.items()
                    ])
                    embed.add_field(
                        name="📝 Pending Tasks by Type",
                        value=queue_text,
                        inline=False
                    )
            
            # Speaker aliases
            if self.speaker_alias_repo and ctx.author:
                aliases = self.speaker_alias_repo.get_aliases_for_user(ctx.author.id)
                embed.add_field(
                    name="👤 Your Aliases",
                    value=f"{len(aliases)} aliases registered",
                    inline=True
                )
            
            # Exchanges
            if session_id:
                exchanges = self.exchange_repo.get_exchanges_by_session(session_id, limit=1000)
                embed.add_field(
                    name="💬 Exchanges",
                    value=f"{len(exchanges)} exchanges created",
                    inline=True
                )
            
            embed.set_footer(text="Use /enrichment-status for detailed queue information")
            
            await ctx.respond(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Diagnostics command failed: {e}", exc_info=True)
            await ctx.respond(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.slash_command(
        name="enrichment_status",
        description="Show detailed enrichment queue status"
    )
    async def enrichment_status(
        self,
        ctx: ApplicationContext,
        show_all: Option(
            bool,
            description="Show all tasks (not just pending)",
            required=False,
            default=False
        )
    ):
        """Show detailed enrichment queue status."""
        try:
            if not self.enrichment_queue_repo:
                await ctx.respond("⚠️ Enrichment queue not available", ephemeral=True)
                return
            
            # Get tasks
            if show_all:
                # Would need to add a method to get all tasks
                tasks = self.enrichment_queue_repo.get_pending_tasks(limit=100)
                title = "📋 All Enrichment Tasks"
            else:
                tasks = self.enrichment_queue_repo.get_pending_tasks(limit=50)
                title = "📋 Pending Enrichment Tasks"
            
            if not tasks:
                await ctx.respond("✅ No pending enrichment tasks", ephemeral=True)
                return
            
            # Group by status and type
            by_type = {}
            for task in tasks:
                key = f"{task.task_type} ({task.status})"
                if key not in by_type:
                    by_type[key] = []
                by_type[key].append(task)
            
            embed = discord.Embed(
                title=title,
                color=discord.Color.gold(),
                timestamp=datetime.utcnow()
            )
            
            embed.description = f"Total: {len(tasks)} tasks"
            
            for key, task_list in sorted(by_type.items()):
                task_type, status = key.rsplit(' (', 1)
                status = status.rstrip(')')
                
                # Sample task details
                sample = task_list[0]
                details = [
                    f"Count: {len(task_list)}",
                    f"Priority: {sample.priority}",
                    f"Target: {sample.target_type}"
                ]
                
                if sample.error:
                    details.append(f"Error: {sample.error[:50]}...")
                
                embed.add_field(
                    name=f"{task_type.replace('_', ' ').title()} - {status}",
                    value="\n".join(details),
                    inline=True
                )
            
            await ctx.respond(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Enrichment status command failed: {e}", exc_info=True)
            await ctx.respond(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.slash_command(
        name="idea_inspect",
        description="Inspect a specific idea's enrichments"
    )
    async def idea_inspect(
        self,
        ctx: ApplicationContext,
        idea_number: Option(
            int,
            description="Idea number (1 = most recent)",
            required=False,
            default=1
        )
    ):
        """Inspect enrichments for a specific idea."""
        try:
            if not self.idea_repo:
                await ctx.respond("⚠️ Idea repository not available", ephemeral=True)
                return
            
            # Get recent session
            session_id = None
            for vc in ctx.guild.voice_channels:
                sid = self.bot.session_manager.get_active_session(vc.id)
                if sid:
                    session_id = sid
                    break
            
            if not session_id and self.session_repo:
                sessions = []
                for vc in ctx.guild.voice_channels:
                    sessions.extend(self.session_repo.get_sessions_by_channel(vc.id, limit=1))
                if sessions:
                    sessions.sort(key=lambda s: s.started_at, reverse=True)
                    session_id = sessions[0].session_id
            
            if not session_id:
                await ctx.respond("⚠️ No session found", ephemeral=True)
                return
            
            # Get ideas
            ideas = self.idea_repo.get_ideas_by_session(session_id, limit=100)
            
            if not ideas:
                await ctx.respond("⚠️ No ideas found in session", ephemeral=True)
                return
            
            if idea_number > len(ideas):
                await ctx.respond(f"⚠️ Only {len(ideas)} ideas available", ephemeral=True)
                return
            
            # Get specific idea (reverse order for most recent first)
            ideas.sort(key=lambda i: i.started_at, reverse=True)
            idea = ideas[idea_number - 1]
            
            embed = discord.Embed(
                title=f"💡 Idea #{idea_number} Details",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            
            # Basic info
            embed.add_field(
                name="Text",
                value=idea.text[:200] + ("..." if len(idea.text) > 200 else ""),
                inline=False
            )
            
            embed.add_field(
                name="Utterances",
                value=str(len(idea.utterance_ids)),
                inline=True
            )
            
            # Enrichments
            if idea.intent:
                embed.add_field(
                    name="Intent",
                    value=f"{idea.intent} ({idea.payload.get('intent_confidence', 'N/A')})",
                    inline=True
                )
            
            if idea.keywords:
                embed.add_field(
                    name="Keywords",
                    value=", ".join(idea.keywords[:5]),
                    inline=False
                )
            
            if idea.mentions:
                mentions_text = "\n".join([
                    f"• {m['alias']} → User {m['resolved_user_id']}"
                    for m in idea.mentions[:5]
                ])
                embed.add_field(
                    name="Mentions",
                    value=mentions_text,
                    inline=False
                )
            
            if idea.is_response_to_idea_id:
                latency = idea.payload.get('response_latency_ms', 'N/A')
                embed.add_field(
                    name="Response To",
                    value=f"Previous idea (latency: {latency}ms)",
                    inline=False
                )
            
            # Enrichment status
            status_text = "\n".join([
                f"• {k.replace('_', ' ').title()}: {v}"
                for k, v in idea.enrichment_status.items()
            ])
            embed.add_field(
                name="Enrichment Status",
                value=status_text,
                inline=False
            )
            
            await ctx.respond(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Idea inspect command failed: {e}", exc_info=True)
            await ctx.respond(f"❌ Error: {str(e)}", ephemeral=True)


def setup(bot):
    """Setup function for loading the cog."""
    bot.add_cog(DiagnosticCommands(bot))
