from typing import List, Dict, Optional, Tuple, Set
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import statistics
import re

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
    
    # =========================================================================
    # Topic Clustering (Advanced)
    # =========================================================================
    
    def analyze_topics(self, session_id: str, num_topics: int = 5) -> Dict:
        """
        Identify conversation topics using simple co-occurrence clustering.
        Groups related keywords into topic clusters.
        
        Returns:
            Topic clusters with keywords and example utterances
        """
        utterances = self.utterance_repo.get_utterances_by_session(session_id)
        
        if not utterances:
            return {'topics': [], 'topic_count': 0}
        
        # Extract keywords with context
        keyword_contexts = defaultdict(list)
        stopwords = self._get_stopwords()
        
        for utt in utterances:
            words = self._extract_words(utt.text, stopwords)
            
            # Store context for each keyword
            for word in words:
                keyword_contexts[word].append({
                    'utterance_id': utt.utterance_id,
                    'text': utt.text,
                    'username': utt.username,
                    'timestamp': utt.started_at
                })
        
        # Build co-occurrence matrix
        cooccurrence = defaultdict(lambda: defaultdict(int))
        
        for utt in utterances:
            words = self._extract_words(utt.text, stopwords)
            # Count co-occurrences within same utterance
            for i, word1 in enumerate(words):
                for word2 in words[i+1:]:
                    cooccurrence[word1][word2] += 1
                    cooccurrence[word2][word1] += 1
        
        # Cluster keywords into topics using simple greedy clustering
        topics = self._cluster_keywords(cooccurrence, keyword_contexts, num_topics)
        
        return {
            'topics': topics,
            'topic_count': len(topics),
            'total_keywords': len(keyword_contexts)
        }
    
    def _get_stopwords(self) -> Set[str]:
        """Get comprehensive stopword list."""
        return {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'is', 'was', 'are', 'were', 'been', 'be', 'have', 'has',
            'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could', 'can',
            'may', 'might', 'must', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
            'this', 'that', 'these', 'those', 'my', 'your', 'his', 'her', 'its',
            'our', 'their', 'me', 'him', 'her', 'us', 'them', 'what', 'which',
            'who', 'when', 'where', 'why', 'how', 'all', 'each', 'every', 'both',
            'few', 'more', 'most', 'other', 'some', 'such', 'no', 'not', 'only',
            'own', 'same', 'so', 'than', 'too', 'very', 'just', 'like', 'yeah',
            'um', 'uh', 'oh', 'okay', 'ok', 'well', 'now', 'then', 'there', 'here',
            'get', 'got', 'going', 'go', 'went', 'think', 'know', 'mean', 'see',
            'said', 'say', 'really', 'actually', 'basically', 'literally'
        }
    
    def _extract_words(self, text: str, stopwords: Set[str]) -> List[str]:
        """Extract meaningful words from text."""
        words = text.lower().split()
        cleaned = []
        
        for word in words:
            # Clean punctuation
            word = re.sub(r'[^a-z0-9]', '', word)
            
            # Filter
            if len(word) > 2 and word not in stopwords and word.isalpha():
                cleaned.append(word)
        
        return cleaned
    
    def _cluster_keywords(
        self,
        cooccurrence: Dict,
        keyword_contexts: Dict,
        num_topics: int
    ) -> List[Dict]:
        """Cluster keywords into topics using greedy approach."""
        # Get most frequent keywords as seed topics
        keyword_freq = {k: len(v) for k, v in keyword_contexts.items()}
        seed_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)
        
        if len(seed_keywords) < num_topics:
            num_topics = len(seed_keywords)
        
        topics = []
        used_keywords = set()
        
        for i in range(num_topics):
            if i >= len(seed_keywords):
                break
            
            seed = seed_keywords[i][0]
            if seed in used_keywords:
                continue
            
            # Find related keywords
            related = []
            if seed in cooccurrence:
                related = sorted(
                    cooccurrence[seed].items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5]  # Top 5 related keywords
            
            topic_keywords = [seed] + [k for k, _ in related if k not in used_keywords]
            topic_keywords = topic_keywords[:6]  # Max 6 keywords per topic
            
            # Mark as used
            used_keywords.update(topic_keywords)
            
            # Get example utterances
            examples = []
            for kw in topic_keywords[:2]:  # Use top 2 keywords for examples
                if kw in keyword_contexts:
                    examples.extend(keyword_contexts[kw][:2])
            
            # Remove duplicates
            seen_ids = set()
            unique_examples = []
            for ex in examples:
                if ex['utterance_id'] not in seen_ids:
                    unique_examples.append(ex)
                    seen_ids.add(ex['utterance_id'])
            
            topics.append({
                'topic_id': i + 1,
                'keywords': topic_keywords,
                'primary_keyword': seed,
                'frequency': keyword_freq[seed],
                'examples': unique_examples[:3]  # Max 3 examples
            })
        
        return topics
    
    # =========================================================================
    # Conversation Recap
    # =========================================================================
    
    def generate_recap(self, session_id: str) -> Dict:
        """
        Generate a structured recap of the conversation.
        Includes timeline, key moments, and summary.
        
        Returns:
            Conversation recap with timeline and highlights
        """
        session = self.session_repo.get_session(session_id)
        utterances = self.utterance_repo.get_utterances_by_session(session_id)
        
        if not session or not utterances:
            return {'error': 'No data available'}
        
        # Build timeline segments (5-minute chunks)
        timeline = self._build_timeline(utterances, session)
        
        # Identify key moments (high activity, topic shifts)
        key_moments = self._identify_key_moments(utterances)
        
        # Get most quoted/referenced utterances
        highlights = self._find_highlights(utterances)
        
        # Participant summary
        participants = self._summarize_participants(utterances)
        
        return {
            'session_id': session_id,
            'channel_name': session.channel_name,
            'duration_minutes': session.duration / 60 if session.duration else 0,
            'timeline': timeline,
            'key_moments': key_moments,
            'highlights': highlights,
            'participants': participants,
            'total_utterances': len(utterances)
        }
    
    def _build_timeline(self, utterances: List[Utterance], session: Session) -> List[Dict]:
        """Build timeline of conversation in segments."""
        if not utterances:
            return []
        
        timeline = []
        segment_duration = timedelta(minutes=5)
        
        start_time = session.started_at
        current_segment_start = start_time
        segment_utterances = []
        
        for utt in utterances:
            if utt.started_at >= current_segment_start + segment_duration:
                # Save current segment
                if segment_utterances:
                    timeline.append(self._create_timeline_segment(
                        segment_utterances,
                        current_segment_start,
                        len(timeline) + 1
                    ))
                
                # Start new segment
                current_segment_start += segment_duration
                segment_utterances = []
            
            segment_utterances.append(utt)
        
        # Add final segment
        if segment_utterances:
            timeline.append(self._create_timeline_segment(
                segment_utterances,
                current_segment_start,
                len(timeline) + 1
            ))
        
        return timeline
    
    def _create_timeline_segment(
        self,
        utterances: List[Utterance],
        start_time: datetime,
        segment_num: int
    ) -> Dict:
        """Create a timeline segment summary."""
        # Get top keywords for this segment
        word_counts = Counter()
        stopwords = self._get_stopwords()
        
        for utt in utterances:
            words = self._extract_words(utt.text, stopwords)
            word_counts.update(words)
        
        top_keywords = [w for w, _ in word_counts.most_common(3)]
        
        # Get active speakers
        speaker_counts = Counter(utt.username for utt in utterances)
        
        return {
            'segment': segment_num,
            'start_time': start_time.strftime('%H:%M'),
            'utterance_count': len(utterances),
            'active_speakers': list(speaker_counts.keys()),
            'top_keywords': top_keywords,
            'sample_text': utterances[0].text[:100] if utterances else ''
        }
    
    def _identify_key_moments(self, utterances: List[Utterance]) -> List[Dict]:
        """Identify key moments in conversation (high activity, topic shifts)."""
        if len(utterances) < 10:
            return []
        
        key_moments = []
        window_size = 10
        
        # Find high-activity windows
        for i in range(0, len(utterances) - window_size, window_size // 2):
            window = utterances[i:i+window_size]
            
            # Calculate activity score
            unique_speakers = len(set(u.user_id for u in window))
            avg_response_time = self._calc_avg_response_time(window)
            
            # High activity = multiple speakers + fast responses
            if unique_speakers >= 3 and avg_response_time and avg_response_time < 2.0:
                key_moments.append({
                    'type': 'high_activity',
                    'timestamp': window[0].started_at.strftime('%H:%M:%S'),
                    'description': f'{unique_speakers} speakers in rapid exchange',
                    'sample': window[0].text[:80]
                })
        
        return key_moments[:5]  # Top 5 key moments
    
    def _calc_avg_response_time(self, utterances: List[Utterance]) -> Optional[float]:
        """Calculate average response time for utterances."""
        if len(utterances) < 2:
            return None
        
        times = []
        for i in range(len(utterances) - 1):
            if utterances[i].user_id != utterances[i+1].user_id:
                rt = (utterances[i+1].started_at - utterances[i].ended_at).total_seconds()
                if 0 <= rt <= 30:
                    times.append(rt)
        
        return statistics.mean(times) if times else None
    
    def _find_highlights(self, utterances: List[Utterance]) -> List[Dict]:
        """Find highlight utterances (longest, most confident, etc.)."""
        if not utterances:
            return []
        
        highlights = []
        
        # Longest utterance
        longest = max(utterances, key=lambda u: len(u.text))
        if len(longest.text) > 50:
            highlights.append({
                'type': 'longest',
                'username': longest.username,
                'text': longest.text,
                'timestamp': longest.started_at.strftime('%H:%M:%S')
            })
        
        # Most confident transcription
        most_confident = max(utterances, key=lambda u: u.confidence)
        if most_confident.confidence > 0.9:
            highlights.append({
                'type': 'clearest',
                'username': most_confident.username,
                'text': most_confident.text,
                'confidence': most_confident.confidence,
                'timestamp': most_confident.started_at.strftime('%H:%M:%S')
            })
        
        return highlights
    
    def _summarize_participants(self, utterances: List[Utterance]) -> List[Dict]:
        """Summarize each participant's contribution."""
        participant_stats = defaultdict(lambda: {
            'utterance_count': 0,
            'total_words': 0,
            'speaking_time': 0.0
        })
        
        for utt in utterances:
            stats = participant_stats[utt.username]
            stats['utterance_count'] += 1
            stats['total_words'] += len(utt.text.split())
            stats['speaking_time'] += utt.audio_duration
        
        return [
            {
                'username': username,
                'utterances': stats['utterance_count'],
                'words': stats['total_words'],
                'speaking_time_seconds': round(stats['speaking_time'], 1)
            }
            for username, stats in participant_stats.items()
        ]
    
    # =========================================================================
    # Social Dynamics & Influence
    # =========================================================================
    
    def analyze_social_dynamics(self, session_id: str) -> Dict:
        """
        Analyze social dynamics: who influences whom, conversation flow,
        engagement patterns.
        
        Returns:
            Social dynamics metrics and influence scores
        """
        utterances = self.utterance_repo.get_utterances_by_session(session_id)
        
        if len(utterances) < 5:
            return {'error': 'Insufficient data for social dynamics analysis'}
        
        # Calculate influence scores
        influence = self._calculate_influence_scores(utterances)
        
        # Analyze conversation flow
        flow = self._analyze_conversation_flow(utterances)
        
        # Identify conversation roles
        roles = self._identify_conversation_roles(utterances, influence)
        
        # Engagement metrics
        engagement = self._calculate_engagement_metrics(utterances)
        
        return {
            'influence_scores': influence,
            'conversation_flow': flow,
            'participant_roles': roles,
            'engagement_metrics': engagement
        }
    
    def _calculate_influence_scores(self, utterances: List[Utterance]) -> Dict:
        """
        Calculate influence scores based on:
        - How often others respond to you
        - How quickly others respond
        - How long others speak after you speak
        """
        user_influence = defaultdict(lambda: {
            'response_count': 0,
            'avg_response_time': [],
            'triggered_speaking_time': 0.0,
            'username': ''
        })
        
        for i in range(len(utterances) - 1):
            current = utterances[i]
            next_utt = utterances[i + 1]
            
            # Different speaker = potential influence
            if current.user_id != next_utt.user_id:
                influence = user_influence[current.user_id]
                influence['username'] = current.username
                influence['response_count'] += 1
                
                # Response time
                rt = (next_utt.started_at - current.ended_at).total_seconds()
                if 0 <= rt <= 30:
                    influence['avg_response_time'].append(rt)
                
                # Speaking time triggered
                influence['triggered_speaking_time'] += next_utt.audio_duration
        
        # Calculate final scores
        scores = []
        for user_id, data in user_influence.items():
            avg_rt = statistics.mean(data['avg_response_time']) if data['avg_response_time'] else None
            
            # Influence score: more responses + faster responses + more triggered speech = higher influence
            score = data['response_count'] * 10
            if avg_rt:
                score += max(0, 10 - avg_rt)  # Faster response = higher score
            score += data['triggered_speaking_time'] / 10
            
            scores.append({
                'username': data['username'],
                'influence_score': round(score, 1),
                'responses_triggered': data['response_count'],
                'avg_response_time': round(avg_rt, 2) if avg_rt else None,
                'speaking_time_triggered': round(data['triggered_speaking_time'], 1)
            })
        
        # Sort by influence score
        scores.sort(key=lambda x: x['influence_score'], reverse=True)
        
        return scores
    
    def _analyze_conversation_flow(self, utterances: List[Utterance]) -> Dict:
        """Analyze how conversation flows between participants."""
        # Build flow graph
        flow_graph = defaultdict(lambda: defaultdict(int))
        
        for i in range(len(utterances) - 1):
            from_user = utterances[i].username
            to_user = utterances[i + 1].username
            if from_user != to_user:
                flow_graph[from_user][to_user] += 1
        
        # Find dominant flows
        dominant_flows = []
        for from_user, to_users in flow_graph.items():
            for to_user, count in to_users.items():
                if count >= 3:  # At least 3 exchanges
                    dominant_flows.append({
                        'from': from_user,
                        'to': to_user,
                        'exchanges': count
                    })
        
        dominant_flows.sort(key=lambda x: x['exchanges'], reverse=True)
        
        return {
            'dominant_flows': dominant_flows[:5],
            'total_exchanges': sum(sum(to_users.values()) for to_users in flow_graph.values())
        }
    
    def _identify_conversation_roles(self, utterances: List[Utterance], influence: List[Dict]) -> List[Dict]:
        """Identify conversation roles: leader, supporter, observer, etc."""
        user_stats = defaultdict(lambda: {
            'utterances': 0,
            'speaking_time': 0.0,
            'responses_given': 0,
            'username': ''
        })
        
        # Gather stats
        for i, utt in enumerate(utterances):
            stats = user_stats[utt.user_id]
            stats['username'] = utt.username
            stats['utterances'] += 1
            stats['speaking_time'] += utt.audio_duration
            
            # Count responses given
            if i > 0 and utterances[i-1].user_id != utt.user_id:
                stats['responses_given'] += 1
        
        # Assign roles
        roles = []
        total_utterances = len(utterances)
        
        for user_id, stats in user_stats.items():
            participation_rate = stats['utterances'] / total_utterances
            
            # Determine role
            if participation_rate > 0.4:
                role = 'Leader'
                description = 'Dominates conversation'
            elif participation_rate > 0.25:
                role = 'Active Participant'
                description = 'Highly engaged'
            elif stats['responses_given'] > stats['utterances'] * 0.7:
                role = 'Responder'
                description = 'Primarily responds to others'
            elif participation_rate < 0.1:
                role = 'Observer'
                description = 'Limited participation'
            else:
                role = 'Contributor'
                description = 'Balanced participation'
            
            roles.append({
                'username': stats['username'],
                'role': role,
                'description': description,
                'participation_rate': round(participation_rate * 100, 1)
            })
        
        return roles
    
    def _calculate_engagement_metrics(self, utterances: List[Utterance]) -> Dict:
        """Calculate overall engagement metrics."""
        if not utterances:
            return {}
        
        # Calculate gaps between utterances
        gaps = []
        for i in range(len(utterances) - 1):
            gap = (utterances[i+1].started_at - utterances[i].ended_at).total_seconds()
            if 0 <= gap <= 60:  # Filter outliers
                gaps.append(gap)
        
        # Unique speakers per time window
        window_size = 10
        speaker_diversity = []
        for i in range(0, len(utterances) - window_size, window_size):
            window = utterances[i:i+window_size]
            unique_speakers = len(set(u.user_id for u in window))
            speaker_diversity.append(unique_speakers)
        
        return {
            'avg_gap_between_utterances': round(statistics.mean(gaps), 2) if gaps else None,
            'median_gap': round(statistics.median(gaps), 2) if gaps else None,
            'avg_speaker_diversity': round(statistics.mean(speaker_diversity), 1) if speaker_diversity else None,
            'engagement_score': self._calculate_engagement_score(gaps, speaker_diversity)
        }
    
    def _calculate_engagement_score(self, gaps: List[float], diversity: List[int]) -> str:
        """Calculate overall engagement score."""
        if not gaps or not diversity:
            return 'Unknown'
        
        avg_gap = statistics.mean(gaps)
        avg_diversity = statistics.mean(diversity)
        
        # High engagement: short gaps + high diversity
        if avg_gap < 2.0 and avg_diversity >= 3:
            return 'Very High'
        elif avg_gap < 3.0 and avg_diversity >= 2:
            return 'High'
        elif avg_gap < 5.0:
            return 'Moderate'
        else:
            return 'Low'
