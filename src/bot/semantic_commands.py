import discord
from discord.ext import commands
from src.services.vector_service import VectorService
from src.repositories.utterance_repo import UtteranceRepository
from src.repositories.session_repo import SessionRepository
import logging

logger = logging.getLogger(__name__)


class SemanticCommands(commands.Cog):
    """Commands for semantic search and topic analysis."""
    
    def __init__(
        self,
        bot: commands.Bot,
        vector_service: VectorService,
        utterance_repo: UtteranceRepository,
        session_repo: SessionRepository
    ):
        self.bot = bot
        self.vector_service = vector_service
        self.utterance_repo = utterance_repo
        self.session_repo = session_repo
    
    @commands.command(name='semantic')
    async def semantic_search(self, ctx, *, query: str):
        """
        Semantic search across all conversations.
        
        Usage: !semantic <query>
        Example: !semantic machine learning algorithms
        """
        if not self.vector_service.enabled:
            await ctx.send("❌ Semantic search is disabled. Set QDRANT_ENABLED=true in .env")
            return
        
        await ctx.send(f"🔍 Searching for: *{query}*...")
        
        try:
            results = await self.vector_service.semantic_search(
                query=query,
                limit=10
            )
            
            if not results:
                await ctx.send("No results found.")
                return
            
            embed = discord.Embed(
                title="Semantic Search Results",
                description=f"Query: *{query}*",
                color=discord.Color.blue()
            )
            
            for i, result in enumerate(results[:5], 1):
                metadata = result['metadata']
                score = result['score']
                
                timestamp = metadata.get('timestamp', 'Unknown')
                
                embed.add_field(
                    name=f"{i}. {metadata.get('username', 'Unknown')} (Score: {score:.3f})",
                    value=f"```{metadata.get('text', '')[:200]}```\nTime: {timestamp}",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}", exc_info=True)
            await ctx.send(f"❌ Search failed: {str(e)}")
    
    @commands.command(name='topicmap')
    async def show_topics(self, ctx):
        """
        Show common topics discussed (placeholder for future clustering).
        
        Usage: !topicmap
        """
        await ctx.send("📊 Topic clustering is not yet implemented. Coming soon!")
    
    @commands.command(name='similar')
    async def find_similar(self, ctx, utterance_id: int):
        """
        Find utterances similar to a specific one.
        
        Usage: !similar <utterance_id>
        Example: !similar 42
        """
        if not self.vector_service.enabled:
            await ctx.send("❌ Semantic search is disabled.")
            return
        
        await ctx.send("🔍 Finding similar utterances is not yet fully implemented.")
    
    @commands.command(name='vectorstats')
    async def vector_stats(self, ctx):
        """
        Show vector database statistics.
        
        Usage: !vectorstats
        """
        if not self.vector_service.enabled:
            await ctx.send("❌ Vector database is disabled.")
            return
        
        try:
            info = self.vector_service.vector_store.get_collection_info()
            
            embed = discord.Embed(
                title="Vector Database Statistics",
                color=discord.Color.green()
            )
            
            embed.add_field(name="Collection", value=self.vector_service.vector_store.collection_name, inline=False)
            embed.add_field(name="Total Vectors", value=info.get('vectors_count', 'Unknown'), inline=True)
            embed.add_field(name="Indexed Vectors", value=info.get('indexed_vectors_count', 'Unknown'), inline=True)
            embed.add_field(name="Points", value=info.get('points_count', 'Unknown'), inline=True)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Failed to get vector stats: {e}", exc_info=True)
            await ctx.send(f"❌ Failed to get stats: {str(e)}")
