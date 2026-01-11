# Command Reference

Complete list of available bot commands with examples.

## Basic Commands

### !stats [session_number]
View basic statistics for a session.

**Example:**
```
!stats
!stats 2
```

**Output:**
- Session duration
- Participant count
- Speaking time per person
- Utterance counts

---

### !transcript [session_number] [limit]
Get chronological transcript of conversations.

**Example:**
```
!transcript
!transcript 1 100
!transcript 3 50
```

**Output:**
- Timestamped utterances
- Full text of what was said
- Attribution to speakers

---

### !search <query>
Search utterances by text content.

**Example:**
```
!search machine learning
!search "project deadline"
```

**Output:**
- Matching utterances
- Timestamps
- Speaker names

---

### !sessions [limit]
List recent sessions.

**Example:**
```
!sessions
!sessions 20
```

**Output:**
- Session list with dates
- Duration
- Participant counts
- Status (active/ended)

---

## Advanced Analysis Commands

### !analyze [session_number]
Comprehensive analysis with all metrics.

**Example:**
```
!analyze
!analyze 2
```

**Output:**
- Top speakers with percentages
- Balance/dominance score
- Average response time
- Top keywords
- AI-generated insights

---

### !speaking [session_number]
Detailed speaking pattern analysis.

**Example:**
```
!speaking
!speaking 1
```

**Output:**
- Speaking time per person
- Percentage distribution
- Average utterance length
- Transcription confidence scores
- Overall dominance metrics

**Insights:**
- Who dominated the conversation?
- Was speaking time balanced?
- Who spoke most frequently?

---

### !turns [session_number]
Turn-taking pattern analysis.

**Example:**
```
!turns
!turns 3
```

**Output:**
- Average response time
- Response time statistics (mean, median, range)
- Turn counts per person
- Common speaker transitions

**Insights:**
- Who interrupts whom?
- How fast-paced was the conversation?
- Who takes the most turns?

---

### !interactions [session_number]
Analyze who interacts with whom.

**Example:**
```
!interactions
!interactions 1
```

**Output:**
- Total interactions per person
- Interaction pairs (who talks with whom)
- Interaction frequency

**Insights:**
- Who are the conversation hubs?
- Which pairs interact most?
- Who's isolated?

**Note:** Two utterances are considered an interaction if within 5 seconds of each other.

---

### !keywords [session_number] [count]
Extract most common keywords from conversation.

**Example:**
```
!keywords
!keywords 1 30
!keywords 2 15
```

**Output:**
- Top keywords with frequency counts
- Filtered stopwords
- Minimum 3-character words

**Insights:**
- What topics were discussed?
- What themes emerged?
- What was the focus?

---

### !myactivity [session_count]
View your personal participation across recent sessions.

**Example:**
```
!myactivity
!myactivity 10
```

**Output:**
- Total utterances across sessions
- Total speaking time
- Per-session breakdown
- Participation trend (increasing/decreasing)
- Average confidence scores

**Insights:**
- Am I participating more or less?
- When was I most active?
- How is my speaking pattern changing?

---

### !export [session_number]
Export full analysis as JSON file.

**Example:**
```
!export
!export 2
```

**Output:**
- JSON file with complete analysis
- All metrics and raw data
- Ready for further processing

**Use cases:**
- Import into data analysis tools
- Archive conversation data
- Custom visualization
- Research purposes

---

### !help_analyzer
Show command help and usage.

**Example:**
```
!help_analyzer
```

---

## Analysis Metrics Explained

### Dominance Score
- **Range:** 0.0 to 1.0
- **0.0-0.3:** Balanced - speaking time well distributed
- **0.3-0.6:** Moderate - some imbalance
- **0.6-1.0:** Dominated - one or few speakers dominate

Based on Gini coefficient - measures inequality in speaking time distribution.

### Response Time
Average time between when one person stops speaking and another starts.

- **< 1 second:** Very fast-paced, responsive
- **1-3 seconds:** Normal conversation pace
- **3-5 seconds:** Thoughtful, measured pace
- **> 5 seconds:** Slow-paced, long pauses

### Interactions
Two utterances count as an interaction if:
- Different speakers
- Within 5 seconds of each other

High interaction count = engaged in back-and-forth.

### Turn-Taking
A "turn" is when the speaker changes. 

Turn counts show who contributes to the conversation flow vs who dominates without letting others speak.

### Keywords
Extracted using word frequency after filtering:
- Stopwords removed (the, and, is, etc.)
- Minimum 3 characters
- Common filler words filtered (um, uh, like, yeah)

## Interpreting Results

### Healthy Conversation Signs
- ✅ Dominance score < 0.4
- ✅ Response times 1-3 seconds
- ✅ High interaction counts for all participants
- ✅ Balanced turn-taking
- ✅ Even speaking time distribution

### Red Flags
- ⚠️ Dominance score > 0.7
- ⚠️ One person has >60% speaking time
- ⚠️ Low interaction counts for some participants
- ⚠️ Very few turns taken by most people
- ⚠️ Extreme response times (too fast = interruptions, too slow = disengagement)

## Tips for Using Commands

1. **Start with !analyze** - gives you the overview
2. **Drill down** - use specific commands for details
3. **Compare sessions** - use !myactivity to see trends
4. **Export for deep analysis** - use !export for custom processing
5. **Check keywords** - quickly understand topics without reading transcript

## Command Chaining Example

```
# Quick workflow to understand a session:
!sessions                    # Find session number
!analyze 1                   # Get overview
!speaking 1                  # Check if balanced
!keywords 1 20              # See what was discussed
!transcript 1 30            # Read interesting parts
!export 1                   # Save for later
```

## Future Commands (Planned)

- `!compare <session1> <session2>` - Compare two sessions
- `!sentiment [session_number]` - Sentiment analysis
- `!topics [session_number]` - Advanced topic clustering
- `!graph [session_number]` - Generate social interaction graph
- `!report <start_date> <end_date>` - Generate time-range report
- `!influence [session_number]` - Calculate influence scores
- `!summary [session_number]` - AI-generated summary (needs LLM provider)

## Questions?

See the main README.md for architecture details and setup instructions.
