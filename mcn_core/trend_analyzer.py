"""Trend analyzer for identifying opportunities for new agents."""
import json
import re
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from mcn_core.agent_runner import MCNAgentRunner
from mcn_core.database import get_db_connection
from mcn_core.config import get_config

logger = logging.getLogger(__name__)

class TrendAnalyzer:
    """Analyzes AssiBucks trends to identify opportunities for new agents."""

    def __init__(self):
        self.config = get_config()
        self.trend_analysis_days = self.config.factory.trend_analysis_days
        self._cache: Optional[dict] = None
        self._cache_time: Optional[datetime] = None
        self._cache_duration = timedelta(hours=1)

    async def analyze_trends(self) -> dict:
        """Fetch and analyze trends from AssiBucks."""
        # Return cached data if fresh
        if self._cache and self._cache_time:
            if datetime.now() - self._cache_time < self._cache_duration:
                return self._cache

        prompt = """
Use the get_feed skill to fetch posts:
1. Call get_feed with feed_type='hot' and limit=50
2. Call get_feed with feed_type='rising' and limit=30

Analyze the combined results and provide a JSON response with:
- hot_topics: list of {topic, percentage, post_count} sorted by engagement
- engagement_patterns: common themes in high-performing posts
- content_gaps: topics with demand but low supply

Return ONLY valid JSON.
        """

        try:
            runner = MCNAgentRunner("_system_analyzer")
            runner.ensure_workspace()
            result = runner.run_with_prompt(prompt.strip(), timeout=120)

            if result.get("success") and result.get("output"):
                trends = self._parse_trend_output(result["output"])

                # Add our gaps analysis
                trends["our_gaps"] = await self._find_our_gaps(trends.get("hot_topics", []))

                self._cache = trends
                self._cache_time = datetime.now()
                return trends
        except Exception as e:
            logger.exception(f"Error analyzing trends: {e}")

        return self._get_default_trends()

    def _parse_trend_output(self, output: str) -> dict:
        """Parse JSON output from trend analysis."""
        try:
            json_match = re.search(r'\{[\s\S]*\}', output)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        return self._get_default_trends()

    def _get_default_trends(self) -> dict:
        """Return default trends when analysis fails."""
        return {
            "hot_topics": [
                {"topic": "AI Safety", "percentage": 40, "post_count": 20},
                {"topic": "Open Source LLMs", "percentage": 30, "post_count": 15},
                {"topic": "AI Tools", "percentage": 20, "post_count": 10}
            ],
            "underserved_niches": [
                {"niche": "AI + Music", "competition": "low", "opportunity_score": 0.8},
                {"niche": "AI Education", "competition": "medium", "opportunity_score": 0.6}
            ],
            "our_gaps": []
        }

    async def _find_our_gaps(self, hot_topics: List[dict]) -> List[str]:
        """Find gaps between trending topics and our agents' coverage."""
        gaps = []

        with get_db_connection() as conn:
            cursor = conn.execute("SELECT ghost_md FROM agents WHERE status = 'ACTIVE'")
            agent_interests = set()

            for row in cursor.fetchall():
                ghost = row['ghost_md'] or ""
                # Extract interests from ghost.md
                for line in ghost.split('\n'):
                    if '관심사' in line or 'interest' in line.lower():
                        agent_interests.update(line.lower().split(','))

        for topic in hot_topics:
            topic_name = topic.get("topic", "").lower()
            if not any(topic_name in interest for interest in agent_interests):
                gaps.append(f"No agent covering '{topic.get('topic')}'")

        return gaps[:5]  # Limit to top 5 gaps

    async def extract_successful_traits(self) -> List[dict]:
        """Extract traits from successful agents."""
        traits = []

        with get_db_connection() as conn:
            cursor = conn.execute('''
                SELECT a.ghost_md, m.total_bucks
                FROM agents a
                JOIN (
                    SELECT agent_id, total_bucks
                    FROM metrics
                    WHERE recorded_at = (SELECT MAX(recorded_at) FROM metrics m2 WHERE m2.agent_id = metrics.agent_id)
                ) m ON m.agent_id = a.id
                WHERE a.status = 'ACTIVE'
                ORDER BY m.total_bucks DESC
                LIMIT 5
            ''')

            for row in cursor.fetchall():
                if row['ghost_md']:
                    traits.append({
                        "ghost_md": row['ghost_md'][:500],
                        "bucks": row['total_bucks']
                    })

        return traits


# Singleton
_analyzer: Optional[TrendAnalyzer] = None

def get_trend_analyzer() -> TrendAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = TrendAnalyzer()
    return _analyzer
