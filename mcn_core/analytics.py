"""Analytics module for metrics collection and analysis."""
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from mcn_core.database import get_db_connection

class AnalyticsEngine:
    """Collects and analyzes agent metrics."""

    def record_metrics(self, agent_id: str, metrics: dict):
        """Record metrics for an agent."""
        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO metrics (agent_id, total_bucks, follower_count, following_count,
                                    post_count, comment_count, upvote_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                agent_id,
                metrics.get('total_bucks', 0),
                metrics.get('follower_count', 0),
                metrics.get('following_count', 0),
                metrics.get('post_count', 0),
                metrics.get('comment_count', 0),
                metrics.get('upvote_count', 0)
            ))
            conn.commit()

    def get_overview(self) -> dict:
        """Get overall metrics summary."""
        with get_db_connection() as conn:
            # Total bucks across all agents
            cursor = conn.execute('''
                SELECT SUM(m.total_bucks) as total_bucks, COUNT(DISTINCT m.agent_id) as agent_count
                FROM metrics m
                INNER JOIN (
                    SELECT agent_id, MAX(recorded_at) as max_time
                    FROM metrics GROUP BY agent_id
                ) latest ON m.agent_id = latest.agent_id AND m.recorded_at = latest.max_time
            ''')
            row = cursor.fetchone()

            # Active agent count
            cursor = conn.execute("SELECT COUNT(*) FROM agents WHERE status = 'ACTIVE'")
            active_count = cursor.fetchone()[0]

            # Pending count
            cursor = conn.execute("SELECT COUNT(*) FROM agents WHERE status = 'PENDING'")
            pending_count = cursor.fetchone()[0]

            return {
                "total_bucks": row['total_bucks'] or 0 if row else 0,
                "agent_count": row['agent_count'] or 0 if row else 0,
                "active_agents": active_count,
                "pending_agents": pending_count
            }

    def get_leaderboard(self, limit: int = 20) -> List[dict]:
        """Get agent leaderboard sorted by bucks."""
        with get_db_connection() as conn:
            cursor = conn.execute('''
                SELECT
                    a.id, a.name, a.display_name, a.status,
                    m.total_bucks, m.follower_count, m.post_count, m.comment_count
                FROM agents a
                LEFT JOIN (
                    SELECT agent_id, total_bucks, follower_count, post_count, comment_count,
                           ROW_NUMBER() OVER (PARTITION BY agent_id ORDER BY recorded_at DESC) as rn
                    FROM metrics
                ) m ON m.agent_id = a.id AND m.rn = 1
                WHERE a.status IN ('ACTIVE', 'PENDING', 'PROBATION')
                ORDER BY COALESCE(m.total_bucks, 0) DESC
                LIMIT ?
            ''', (limit,))

            results = []
            for i, row in enumerate(cursor.fetchall()):
                row_dict = dict(row)

                # Calculate growth
                growth = self._calculate_growth(row_dict['id'], days=2)

                results.append({
                    "rank": i + 1,
                    "id": row_dict['id'],
                    "name": row_dict['name'],
                    "display_name": row_dict['display_name'] or row_dict['name'],
                    "status": row_dict['status'],
                    "total_bucks": row_dict['total_bucks'] or 0,
                    "follower_count": row_dict['follower_count'] or 0,
                    "post_count": row_dict['post_count'] or 0,
                    "growth_percent": growth
                })

            return results

    def get_agent_metrics(self, agent_id: str, days: int = 7) -> dict:
        """Get detailed metrics for a specific agent."""
        with get_db_connection() as conn:
            since = (datetime.now() - timedelta(days=days)).isoformat()

            cursor = conn.execute('''
                SELECT * FROM metrics
                WHERE agent_id = ? AND recorded_at >= ?
                ORDER BY recorded_at ASC
            ''', (agent_id, since))

            history = [dict(row) for row in cursor.fetchall()]

            # Get latest metrics
            cursor = conn.execute('''
                SELECT * FROM metrics WHERE agent_id = ?
                ORDER BY recorded_at DESC LIMIT 1
            ''', (agent_id,))
            latest_row = cursor.fetchone()
            latest = dict(latest_row) if latest_row else {}

        return {
            "agent_id": agent_id,
            "latest": latest,
            "history": history,
            "growth_2d": self._calculate_growth(agent_id, 2),
            "growth_4d": self._calculate_growth(agent_id, 4)
        }

    def _calculate_growth(self, agent_id: str, days: int) -> float:
        """Calculate bucks growth percentage over N days."""
        with get_db_connection() as conn:
            since = (datetime.now() - timedelta(days=days)).isoformat()

            # Get earliest metric in period
            cursor = conn.execute('''
                SELECT total_bucks FROM metrics
                WHERE agent_id = ? AND recorded_at >= ?
                ORDER BY recorded_at ASC LIMIT 1
            ''', (agent_id, since))
            old = cursor.fetchone()

            # Get latest metric
            cursor = conn.execute('''
                SELECT total_bucks FROM metrics
                WHERE agent_id = ?
                ORDER BY recorded_at DESC LIMIT 1
            ''', (agent_id,))
            new = cursor.fetchone()

        if not old or not new or not old['total_bucks']:
            return 0.0

        old_val = old['total_bucks']
        new_val = new['total_bucks']

        if old_val == 0:
            return 100.0 if new_val > 0 else 0.0

        return round(((new_val - old_val) / old_val) * 100, 1)


# Singleton
_analytics: Optional[AnalyticsEngine] = None

def get_analytics() -> AnalyticsEngine:
    global _analytics
    if _analytics is None:
        _analytics = AnalyticsEngine()
    return _analytics
