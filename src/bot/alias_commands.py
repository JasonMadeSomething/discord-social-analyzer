"""Discord commands for managing speaker aliases."""
import discord
from discord.ext import commands
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class AliasCommands(commands.Cog):
    """Commands for managing speaker aliases."""
    
    def __init__(self, bot, speaker_alias_repo):
        """
        Initialize alias commands.
        
        Args:
            bot: Discord bot instance
            speaker_alias_repo: SpeakerAliasRepository instance
        """
        self.bot = bot
        self.speaker_alias_repo = speaker_alias_repo
    
    alias = discord.SlashCommandGroup("alias", "Manage speaker aliases for mention detection")
    
    @alias.command(name="add", description="Add an alias for a user")
    async def add_alias(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Member,
        nickname: str
    ):
        """
        Add a manual alias for a user.
        
        Args:
            ctx: Application context
            user: User to add alias for
            nickname: Alias/nickname to add
        """
        try:
            alias_id = self.speaker_alias_repo.add_alias(
                user_id=user.id,
                alias=nickname,
                alias_type='nickname',
                confidence=1.0,
                created_by=ctx.author.id
            )
            
            if alias_id:
                await ctx.respond(
                    f"✅ Added alias **'{nickname}'** for {user.mention}",
                    ephemeral=True
                )
                logger.info(f"User {ctx.author.id} added alias '{nickname}' for user {user.id}")
            else:
                await ctx.respond(
                    f"⚠️ Alias **'{nickname}'** already exists for {user.mention}",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Failed to add alias: {e}")
            await ctx.respond(
                f"❌ Failed to add alias: {str(e)}",
                ephemeral=True
            )
    
    @alias.command(name="list", description="List aliases for a user")
    async def list_aliases(
        self,
        ctx: discord.ApplicationContext,
        user: Optional[discord.Member] = None
    ):
        """
        List aliases for a user.
        
        Args:
            ctx: Application context
            user: User to list aliases for (defaults to command author)
        """
        try:
            target_user = user or ctx.author
            aliases = self.speaker_alias_repo.get_aliases_for_user(target_user.id)
            
            if not aliases:
                await ctx.respond(
                    f"No aliases found for {target_user.mention}",
                    ephemeral=True
                )
                return
            
            # Group by type
            by_type = {}
            for alias in aliases:
                if alias.alias_type not in by_type:
                    by_type[alias.alias_type] = []
                by_type[alias.alias_type].append(alias.alias)
            
            # Build response
            lines = [f"**Aliases for {target_user.mention}:**\n"]
            for alias_type, alias_list in by_type.items():
                lines.append(f"**{alias_type.replace('_', ' ').title()}:**")
                for alias_text in alias_list:
                    lines.append(f"  • {alias_text}")
                lines.append("")
            
            await ctx.respond(
                "\n".join(lines),
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Failed to list aliases: {e}")
            await ctx.respond(
                f"❌ Failed to list aliases: {str(e)}",
                ephemeral=True
            )
    
    @alias.command(name="remove", description="Remove an alias from a user")
    async def remove_alias(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Member,
        nickname: str
    ):
        """
        Remove an alias from a user.
        
        Args:
            ctx: Application context
            user: User to remove alias from
            nickname: Alias to remove
        """
        try:
            success = self.speaker_alias_repo.remove_alias(user.id, nickname)
            
            if success:
                await ctx.respond(
                    f"✅ Removed alias **'{nickname}'** from {user.mention}",
                    ephemeral=True
                )
                logger.info(f"User {ctx.author.id} removed alias '{nickname}' from user {user.id}")
            else:
                await ctx.respond(
                    f"⚠️ Alias **'{nickname}'** not found for {user.mention}",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Failed to remove alias: {e}")
            await ctx.respond(
                f"❌ Failed to remove alias: {str(e)}",
                ephemeral=True
            )
    
    @alias.command(name="search", description="Find which user an alias belongs to")
    async def search_alias(
        self,
        ctx: discord.ApplicationContext,
        alias: str
    ):
        """
        Search for which user an alias belongs to.
        
        Args:
            ctx: Application context
            alias: Alias to search for
        """
        try:
            user_id = self.speaker_alias_repo.get_user_by_alias(alias)
            
            if user_id:
                try:
                    user = await self.bot.fetch_user(user_id)
                    await ctx.respond(
                        f"🔍 Alias **'{alias}'** belongs to {user.mention} ({user.name})",
                        ephemeral=True
                    )
                except discord.NotFound:
                    await ctx.respond(
                        f"🔍 Alias **'{alias}'** belongs to user ID: {user_id} (user not found in server)",
                        ephemeral=True
                    )
            else:
                await ctx.respond(
                    f"⚠️ No user found with alias **'{alias}'**",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Failed to search alias: {e}")
            await ctx.respond(
                f"❌ Failed to search alias: {str(e)}",
                ephemeral=True
            )


def setup(bot):
    """Setup function for loading the cog."""
    bot.add_cog(AliasCommands(bot))
