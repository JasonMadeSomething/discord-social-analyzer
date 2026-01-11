from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import statistics

from src.repositories.session_repo import SessionRepository
from src.repositories.utterance_repo import UtteranceRepository
from src.repositories.message_repo import MessageRepository
from src.models.domain import Session, Utterance, Message
from src.config import settings


class ConversationAnalyzer:
    """
    Service for analyzing conversation dynamics and social patterns.
    Provides insights into speaking patterns, interactions, and topics.
    """
    
    def __init__(
        self,
        session_repo: SessionRepository,
        utterance_repo: UtteranceRepository,
        message_repo: MessageRepository
    ):
        self.session_repo = session_repo
        self.utterance_repo = utterance_repo
        self.message_repo = message_repo
    
    # =========================================================================
    # Speaking Pattern Analysis
    # =========================================================================
    
    def analyze_speaking_patterns(self, session_id: str) -> Dict:
        """
        Analyze speaking patterns for a session.
        
        Returns:
            Dict with speaking time, utterance counts, and distribution metrics
        """
        utterances = self.utterance_repo.get_utterances_by_session(session_id)
        
        if not utterances:
            return {
                'total_utterances': 0,
                'total_speaking_time': 0,
                'participants': {}
            }
        
        # Aggregate by user
        user_stats = defaultdict(lambda: {
            'utterance_count': 0,
            'total_speaking_time': 0.0,
            'avg_utterance_length': 0.0,
            'confidence_scores': []
        })
        
        for utt in utterances:
            stats = user_stats[utt.user_id]
            stats['utterance_count'] += 1
            stats['total_speaking_time'] += utt.audio_duration
            stats['confidence_scores'].append(utt.confidence)
            stats['username'] = utt.username
        
        # Calculate averages and percentages
        total_speaking_time = sum(s['total_speaking_time'] for s in user_stats.values())
        
        for user_id, stats in user_stats.items():
            stats['avg_utterance_length'] = (
                stats['total_speaking_time'] / stats['utterance_count']
            )
            stats['avg_confidence'] = statistics.mean(stats['confidence_scores'])
            stats['speaking_time_percentage'] = (
                (stats['total_speaking_time'] / total_speaking_time * 100)
                if total_speaking_time > 0 else 0
            )
            del stats['confidence_scores']  # Remove raw scores
        
        return {
            'total_utterances': len(utterances),
            'total_speaking_time': total_speaking_time,
            'participants': dict(user_stats),
            'dominance_score': self._calculate_dominance_score(user_stats)
        }
    
    def _calculate_dominance_score(self, user_stats: Dict) -> float:
        """
        Calculate conversation dominance (Gini coefficient).
        0 = perfectly equal, 1 = one person dominates completely.
        """
        if not user_stats:
            return 0.0
        
        speaking_times = [s['total_speaking_time'] for s in user_stats.values()]
        
        if len(speaking_times) < 2:
            return 0.0
        
        # Calculate Gini coefficient
        speaking_times.sort()
        n = len(speaking_times)
        cumsum = 0
        
        for i, time in enumerate(speaking_times):
            cumsum += (2 * (i + 1) - n - 1) * time
        
        total_time = sum(speaking_times)
        if total_time == 0:
            return 0.0
        
        return cumsum / (n * total_time)
    
    # =========================================================================
    # Turn-Taking Analysis
    # =========================================================================
    
    def analyze_turn_taking(self, session_id: str) -> Dict:
        """
        Analyze turn-taking patterns: who speaks after whom.
        
        Returns:
            Transition matrix and turn-taking metrics
        """
        utterances = self.utterance_repo.get_utterances_by_session(session_id)
        
        if len(utterances) < 2:
            return {
                'transitions': {},
                'turn_counts': {},
                'avg_response_time': None
            }
        
        # Build transition matrix
        transitions = defaultdict(lambda: defaultdict(int))
        response_times = []
        turn_counts = defaultdict(int)
        
        for i in range(len(utterances) - 1):
            current = utterances[i]
            next_utt = utterances[i + 1]
            
            # Count transition
            transitions[current.user_id][next_utt.user_id] += 1
            
            # Count turns (when speaker changes)
            if current.user_id != next_utt.user_id:
                turn_counts[next_utt.user_id] += 1
                
                # Calculate response time
                response_time = (next_utt.started_at - current.ended_at).total_seconds()
                if 0 <= response_time <= 30:  # Filter outliers
                    response_times.append(response_time)
        
        # Convert to regular dicts with usernames
        user_id_to_name = {u.user_id: u.username for u in utterances}
        
        transitions_with_names = {}
        for from_user, to_users in transitions.items():
            from_name = user_id_to_name.get(from_user, str(from_user))
            transitions_with_names[from_name] = {
                user_id_to_name.get(to_user, str(to_user)): count
                for to_user, count in to_users.items()
            }
        
        turn_counts_with_names = {
            user_id_to_name.get(user_id, str(user_id)): count
            for user_id, count in turn_counts.items()
        }
        
        return {
            'transitions': transitions_with_names,
            'turn_counts': turn_counts_with_names,
            'avg_response_time': (
                statistics.mean(response_times) if response_times else None
            ),
            'response_time_stats': (
                self._calculate_stats(response_times) if response_times else None
            )
        }
    
    def _calculate_stats(self, values: List[float]) -> Dict:
        """Calculate statistical measures for a list of values."""
        if not values:
            return None
        
        return {
            'mean': statistics.mean(values),
            'median': statistics.median(values),
            'stdev': statistics.stdev(values) if len(values) > 1 else 0,
            'min': min(values),
            'max': max(values)
        }
    
    # =========================================================================
    # Interaction Analysis
    # =========================================================================
    
    def analyze_interactions(self, session_id: str) -> Dict:
        """
        Analyze who interacts with whom based on temporal proximity.
        Two utterances are considered an interaction if they're within the configured window.
        
        Returns:
            Interaction graph and metrics
        """
        utterances = self.utterance_repo.get_utterances_by_session(session_id)
        
        if len(utterances) < 2:
            return {
                'interaction_graph': {},
                'interaction_counts': {}
            }
        
        # Build interaction graph
        interactions = defaultdict(lambda: defaultdict(int))
        interaction_window = timedelta(seconds=settings.analysis_interaction_window)
        
        for i in range(len(utterances) - 1):
            current = utterances[i]
            next_utt = utterances[i + 1]
            
            # Check if within interaction window and different speakers
            if (current.user_id != next_utt.user_id and
                next_utt.started_at - current.ended_at <= interaction_window):
                
                # Bidirectional interaction
                interactions[current.user_id][next_utt.user_id] += 1
                interactions[next_utt.user_id][current.user_id] += 1
        
        # Convert to usernames
        user_id_to_name = {u.user_id: u.username for u in utterances}
        
        interaction_graph = {}
        for user_id, partners in interactions.items():
            username = user_id_to_name.get(user_id, str(user_id))
            interaction_graph[username] = {
                user_id_to_name.get(partner_id, str(partner_id)): count
                for partner_id, count in partners.items()
            }
        
        # Calculate total interactions per user
        interaction_counts = {
            username: sum(partners.values())
            for username, partners in interaction_graph.items()
        }
        
        return {
            'interaction_graph': interaction_graph,
            'interaction_counts': interaction_counts
        }
    
    # =========================================================================
    # Topic Analysis (Simple - word frequency based)
    # =========================================================================
    
    def extract_keywords(self, session_id: str, top_n: int = None) -> List[Tuple[str, int]]:
        """
        Extract most common keywords from a session.
        Simple word frequency approach (can be enhanced with TF-IDF later).
        
        Returns:
            List of (word, count) tuples
        """
        if top_n is None:
            top_n = settings.analysis_default_keyword_limit
        
        utterances = self.utterance_repo.get_utterances_by_session(session_id)
        
        if not utterances:
            return []
        
        # Common words to filter out
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'is', 'was', 'are', 'were', 'been', 'be', 'have', 'has',
            'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could', 'can',
            'may', 'might', 'must', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
            'this', 'that', 'these', 'those', 'my', 'your', 'his', 'her', 'its',
            'our', 'their', 'me', 'him', 'her', 'us', 'them', 'what', 'which',
            'who', 'when', 'where', 'why', 'how', 'all', 'each', 'every', 'both',
            'few', 'more', 'most', 'other', 'some', 'such', 'no', 'not', 'only',
            'own', 'same', 'so', 'than', 'too', 'very', 'just', 'like', 'yeah',
            'um', 'uh', 'oh', 'okay', 'ok', 'well'
        }
        
        # Collect all words
        word_counts = Counter()
        
        for utt in utterances:
            words = utt.text.lower().split()
            for word in words:
                # Basic cleaning
                word = word.strip('.,!?;:"\'()[]{}')
                
                # Filter stopwords and short words
                if len(word) > 2 and word not in stopwords and word.isalpha():
                    word_counts[word] += 1
        
        return word_counts.most_common(top_n)
    
    # =========================================================================
    # Session Summary
    # =========================================================================
    
    def generate_session_summary(self, session_id: str) -> Dict:
        """
        Generate comprehensive summary of a session.
        
        Returns:
            Complete analysis including all metrics
        """
        session = self.session_repo.get_session(session_id)
        
        if not session:
            return {'error': 'Session not found'}
        
        # Get all analyses
        speaking_patterns = self.analyze_speaking_patterns(session_id)
        turn_taking = self.analyze_turn_taking(session_id)
        interactions = self.analyze_interactions(session_id)
        keywords = self.extract_keywords(session_id, top_n=15)
        
        # Session metadata
        summary = {
            'session_id': session.session_id,
            'channel_name': session.channel_name,
            'started_at': session.started_at.isoformat(),
            'ended_at': session.ended_at.isoformat() if session.ended_at else None,
            'duration_minutes': session.duration / 60 if session.duration else None,
            'status': session.status.value,
            'participant_count': len(session.participants),
            'participants': [
                {
                    'username': p.username,
                    'joined_at': p.joined_at.isoformat(),
                    'left_at': p.left_at.isoformat() if p.left_at else None
                }
                for p in session.participants
            ],
            
            # Analysis results
            'speaking_patterns': speaking_patterns,
            'turn_taking': turn_taking,
            'interactions': interactions,
            'top_keywords': keywords,
            
            # Quick insights
            'insights': self._generate_insights(
                speaking_patterns,
                turn_taking,
                interactions,
                session
            )
        }
        
        return summary
    
    def _generate_insights(
        self,
        speaking_patterns: Dict,
        turn_taking: Dict,
        interactions: Dict,
        session: Session
    ) -> List[str]:
        """Generate human-readable insights from analysis."""
        insights = []
        
        # Speaking dominance
        if speaking_patterns['dominance_score'] > 0.6:
            insights.append("⚠️ Conversation was dominated by a few speakers")
        elif speaking_patterns['dominance_score'] < 0.3:
            insights.append("✅ Speaking time was well distributed among participants")
        
        # Most active speaker
        if speaking_patterns['participants']:
            most_active = max(
                speaking_patterns['participants'].items(),
                key=lambda x: x[1]['total_speaking_time']
            )
            username = most_active[1]['username']
            percentage = most_active[1]['speaking_time_percentage']
            insights.append(f"🎤 Most active speaker: {username} ({percentage:.1f}% of speaking time)")
        
        # Response time
        avg_response = turn_taking.get('avg_response_time')
        if avg_response:
            if avg_response < 1.0:
                insights.append("⚡ Very responsive conversation with quick turn-taking")
            elif avg_response > 5.0:
                insights.append("🐢 Slower-paced conversation with longer pauses")
        
        # Interaction patterns
        if interactions['interaction_counts']:
            most_interactive = max(
                interactions['interaction_counts'].items(),
                key=lambda x: x[1]
            )
            insights.append(
                f"🤝 Most interactive participant: {most_interactive[0]} "
                f"({most_interactive[1]} interactions)"
            )
        
        # Session length
        if session.duration:
            if session.duration > 3600:  # Over 1 hour
                insights.append("📈 Long session - sustained engagement")
            elif session.duration < 300:  # Under 5 minutes
                insights.append("📉 Brief session")
        
        return insights
    
    # =========================================================================
    # Comparative Analysis
    # =========================================================================
    
    def compare_user_across_sessions(
        self,
        user_id: int,
        session_ids: Optional[List[str]] = None,
        limit: int = 10
    ) -> Dict:
        """
        Compare a user's participation across multiple sessions.
        
        Returns:
            Trends and patterns for the user
        """
        if session_ids:
            utterances_by_session = {}
            for sid in session_ids:
                utterances_by_session[sid] = self.utterance_repo.get_utterances_by_user(
                    user_id=user_id,
                    session_id=sid
                )
        else:
            # Get recent utterances
            all_utterances = self.utterance_repo.get_utterances_by_user(
                user_id=user_id,
                limit=limit * 100  # Get more to group by session
            )
            
            # Group by session
            utterances_by_session = defaultdict(list)
            for utt in all_utterances:
                utterances_by_session[utt.session_id].append(utt)
        
        # Analyze each session
        session_stats = []
        
        for session_id, utterances in utterances_by_session.items():
            if not utterances:
                continue
            
            session = self.session_repo.get_session(session_id)
            if not session:
                continue
            
            total_speaking_time = sum(u.audio_duration for u in utterances)
            
            session_stats.append({
                'session_id': session_id,
                'date': session.started_at.date().isoformat(),
                'utterance_count': len(utterances),
                'speaking_time': total_speaking_time,
                'avg_confidence': statistics.mean(u.confidence for u in utterances)
            })
        
        # Sort by date
        session_stats.sort(key=lambda x: x['date'])
        
        # Calculate trends
        if len(session_stats) >= 2:
            speaking_times = [s['speaking_time'] for s in session_stats]
            trend = "increasing" if speaking_times[-1] > speaking_times[0] else "decreasing"
        else:
            trend = "insufficient data"
        
        return {
            'user_id': user_id,
            'sessions_analyzed': len(session_stats),
            'session_stats': session_stats[-limit:],  # Last N sessions
            'trend': trend,
            'total_utterances': sum(s['utterance_count'] for s in session_stats),
            'total_speaking_time': sum(s['speaking_time'] for s in session_stats)
        }
