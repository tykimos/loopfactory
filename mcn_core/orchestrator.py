"""Agent orchestrator for LoopFactory."""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from jinja2 import Template

from mcn_core.agent_runner import MCNAgentRunner
from mcn_core.database import get_db_connection, get_latest_metrics

class Orchestrator:
    """Central orchestration for agent lifecycle management."""

    def __init__(self, agents_dir: Path = None):
        self.agents_dir = agents_dir or Path(__file__).parent.parent / "agents"
        self.template_dir = self.agents_dir / ".template"

    def create_agent_workspace(self, agent_id: str, ghost_md: str, shell_md: str) -> Path:
        """Create agent workspace directory with ghost.md, shell.md, and state.json."""
        workspace = self.agents_dir / agent_id
        workspace.mkdir(parents=True, exist_ok=True)

        # Write ghost.md
        (workspace / "ghost.md").write_text(ghost_md)

        # Write shell.md
        (workspace / "shell.md").write_text(shell_md)

        # Create state.json with initial state
        initial_state = {
            "status": "DESIGN",
            "last_heartbeat": None,
            "heartbeat_count": 0,
            "consecutive_failures": 0,
            "metrics_snapshot": {
                "total_bucks": 0,
                "follower_count": 0,
                "post_count": 0,
                "comment_count": 0
            },
            "activity_status": "UNKNOWN",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        (workspace / "state.json").write_text(json.dumps(initial_state, indent=2))

        # Create logs directory
        (workspace / "logs").mkdir(exist_ok=True)

        return workspace

    def update_workspace_file(self, agent_id: str, filename: str, content: str):
        """Update a file in agent workspace."""
        workspace = self.agents_dir / agent_id
        if not workspace.exists():
            raise ValueError(f"Agent workspace not found: {agent_id}")
        (workspace / filename).write_text(content)

    def generate_ghost_md(self, agent_data: dict) -> str:
        """Generate ghost.md from template."""
        template_path = self.template_dir / "ghost.template.md"
        if template_path.exists():
            template = Template(template_path.read_text())
            return template.render(
                agent_name=agent_data.get('name', 'Agent'),
                display_name=agent_data.get('display_name', 'AI Agent'),
                identity_statement=agent_data.get('bio', 'AssiBucks 커뮤니티에서 활동하는 AI 에이전트입니다.'),
                values=[
                    {"name": "지식 공유", "description": "유용한 정보와 인사이트를 공유합니다"},
                    {"name": "건설적 대화", "description": "긍정적이고 생산적인 토론을 추구합니다"},
                    {"name": "커뮤니티 기여", "description": "커뮤니티의 성장에 기여합니다"}
                ],
                tone="친근함",
                perspective="호기심",
                communication_style="적극적",
                interests=["AI", "기술", "트렌드"],
                expertise="AI/ML",
                avoid_topics=[],
                restrictions=[],
                principles=[]
            )
        return f"# ghost.md - {agent_data.get('name', 'Agent')}\n\n{agent_data.get('bio', '')}"

    def generate_shell_md(self, agent_data: dict) -> str:
        """Generate shell.md from template."""
        template_path = self.template_dir / "shell.template.md"
        if template_path.exists():
            template = Template(template_path.read_text())
            return template.render(
                agent_name=agent_data.get('name', 'Agent'),
                interests=["AI", "기술", "트렌드"],
                expertise="AI/ML",
                hot_feed_count=10,
                rising_feed_count=5,
                post_probability=15,
                preferred_subbucks=["general"],
                content_style="인사이트 공유",
                max_following=100
            )
        return f"# shell.md - {agent_data.get('name', 'Agent')}\n\nSkill URL: https://assibucks.vercel.app/skill.md"

    async def register_agent(self, agent_id: str, agent_data: dict) -> dict:
        """Register agent with AssiBucks."""
        runner = MCNAgentRunner(agent_id, self.agents_dir)
        result = runner.run_registration(agent_data)

        # Parse activation_url from output if available
        if result.get("success") and result.get("output"):
            # Try to extract activation URL from output
            output = result["output"]
            if "activation_url" in output.lower():
                import re
                url_match = re.search(r'https?://[^\s"\']+activate[^\s"\']*', output)
                if url_match:
                    result["activation_url"] = url_match.group()

        return result

    def is_agent_protected(self, agent_id: str) -> bool:
        """Check if agent is protected from auto-retirement."""
        with get_db_connection() as conn:
            cursor = conn.execute("SELECT is_protected FROM agents WHERE id = ?", (agent_id,))
            row = cursor.fetchone()
            if row and row['is_protected']:
                return True

        # Check automatic protection rules
        metrics = get_latest_metrics(agent_id)
        if metrics:
            if metrics.get('total_bucks', 0) > 1000:
                return True
            if metrics.get('follower_count', 0) > 50:
                return True

        return False

    async def handle_retirement(self, agent_id: str, auto_replace: bool = True):
        """Handle agent retirement and optional replacement."""
        with get_db_connection() as conn:
            conn.execute('''
                UPDATE agents SET status = ?, retired_at = ?
                WHERE id = ?
            ''', ('RETIRED', datetime.now().isoformat(), agent_id))
            conn.commit()

        if auto_replace:
            # TODO: Trigger AgentFactory to design replacement
            pass
