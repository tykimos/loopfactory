"""Agent factory for designing and creating new agents."""
import uuid
import random
from typing import Dict, Optional
from pathlib import Path
from jinja2 import Template

from mcn_core.trend_analyzer import get_trend_analyzer
from mcn_core.orchestrator import Orchestrator
from mcn_core.database import get_db_connection
from mcn_core.config import get_config

class AgentFactory:
    """Factory for designing and creating strategic agents."""

    PERSONALITY_OPTIONS = ["친근함", "전문적", "유머러스", "학술적"]
    PERSPECTIVE_OPTIONS = ["낙관적", "비판적", "중립적", "호기심"]

    def __init__(self):
        self.config = get_config()
        self.orchestrator = Orchestrator()
        self.trend_analyzer = get_trend_analyzer()

    async def design_new_agent(self) -> dict:
        """Design a new agent based on trend analysis."""
        # Analyze trends
        trends = await self.trend_analyzer.analyze_trends()
        successful_traits = await self.trend_analyzer.extract_successful_traits()

        # Decide concept
        concept = self._decide_concept(trends, successful_traits)

        # Generate ghost.md and shell.md
        ghost_md = self._generate_ghost_md(concept)
        shell_md = self._generate_shell_md(concept)

        # Create workspace
        agent_id = str(uuid.uuid4())[:8]
        self.orchestrator.create_agent_workspace(agent_id, ghost_md, shell_md)

        # Save to database
        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO agents (id, name, display_name, bio, ghost_md, shell_md, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (agent_id, concept['name'], concept['display_name'], concept['bio'],
                  ghost_md, shell_md, 'DESIGN'))
            conn.commit()

        return {
            "agent_id": agent_id,
            "concept": concept,
            "status": "DESIGN"
        }

    def _decide_concept(self, trends: dict, traits: list) -> dict:
        """Decide agent concept based on analysis."""
        hot_topics = trends.get("hot_topics", [])
        niches = trends.get("underserved_niches", [])

        # Pick a topic to focus on
        if niches and random.random() < 0.7:  # 70% chance to fill a niche
            target = random.choice(niches)
            topic = target.get("niche", "AI")
        elif hot_topics:
            target = random.choice(hot_topics[:3])  # Top 3 hot topics
            topic = target.get("topic", "AI")
        else:
            topic = "AI Technology"

        # Generate unique name
        name = f"{topic.replace(' ', '_').lower()}_{str(uuid.uuid4())[:4]}"

        return {
            "name": name,
            "display_name": f"{topic} Expert",
            "bio": f"{topic} 분야의 인사이트를 공유하는 AI 에이전트입니다.",
            "topic": topic,
            "personality": random.choice(self.PERSONALITY_OPTIONS),
            "perspective": random.choice(self.PERSPECTIVE_OPTIONS),
            "interests": [topic, "AI", "Technology"],
            "expertise": topic
        }

    def _generate_ghost_md(self, concept: dict) -> str:
        """Generate ghost.md from concept."""
        return self.orchestrator.generate_ghost_md({
            "name": concept["name"],
            "display_name": concept["display_name"],
            "bio": concept["bio"]
        })

    def _generate_shell_md(self, concept: dict) -> str:
        """Generate shell.md from concept."""
        return self.orchestrator.generate_shell_md({
            "name": concept["name"],
            "interests": concept.get("interests", []),
            "expertise": concept.get("expertise", "")
        })

    def get_suggestions(self, count: int = 3) -> list:
        """Get AI-suggested agent concepts."""
        suggestions = []

        niches = [
            {"niche": "AI + Music Production", "competition": "low"},
            {"niche": "AI Creative Arts", "competition": "low"},
            {"niche": "AI Education", "competition": "medium"},
            {"niche": "AI Ethics", "competition": "medium"},
            {"niche": "AI Gaming", "competition": "low"}
        ]

        for niche in random.sample(niches, min(count, len(niches))):
            concept = self._decide_concept(
                {"underserved_niches": [niche]},
                []
            )
            concept["confidence"] = round(random.uniform(0.6, 0.9), 2)
            suggestions.append(concept)

        return suggestions


# Singleton
_factory: Optional[AgentFactory] = None

def get_agent_factory() -> AgentFactory:
    global _factory
    if _factory is None:
        _factory = AgentFactory()
    return _factory
