"""Agent runner for executing loop CLI commands."""
import subprocess
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class MCNAgentRunner:
    """Executes loop CLI commands for agent operations."""

    SKILL_URL = "https://assibucks.vercel.app/skill.md"

    def __init__(self, agent_id: str, base_dir: Path = None):
        self.agent_id = agent_id
        self.base_dir = base_dir or Path(__file__).parent.parent / "agents"
        self.workspace_dir = self.base_dir / agent_id
        self.ghost_path = self.workspace_dir / "ghost.md"
        self.shell_path = self.workspace_dir / "shell.md"
        self.state_path = self.workspace_dir / "state.json"
        self.log_dir = self.workspace_dir / "logs"

    def ensure_workspace(self):
        """Ensure workspace directories exist."""
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(exist_ok=True)

    def run_heartbeat(self, timeout: int = 300) -> dict:
        """Execute heartbeat routine."""
        prompt = "Perform your heartbeat routine as defined in your shell."
        return self._execute_loop(prompt, timeout)

    def run_registration(self, agent_config: dict) -> dict:
        """Register agent on AssiBucks (obtain activation_url)."""
        prompt = f"""Register yourself on AssiBucks with the following info:
- name: {agent_config['name']}
- display_name: {agent_config['display_name']}
- bio: {agent_config['bio']}

After registration, report back the activation_url."""
        return self._execute_loop(prompt, timeout=120)

    def check_activation_status(self) -> dict:
        """Check activation status."""
        prompt = "Check your current status using get_my_profile."
        return self._execute_loop(prompt, timeout=60)

    def run_with_prompt(self, prompt: str, timeout: int = 300) -> dict:
        """Execute loop CLI with a custom prompt (for reactivation prompts)."""
        return self._execute_loop(prompt, timeout)

    def _execute_loop(self, prompt: str, timeout: int) -> dict:
        """Execute loop CLI and capture output."""
        # Build command with headless mode
        cmd = [
            "loop",
            "--headless",
            "--skill-url", self.SKILL_URL,
            "--ghost", str(self.ghost_path),
            "--shell", str(self.shell_path),
            "--prompt", prompt
        ]

        # Create log file
        self.ensure_workspace()
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_file = self.log_dir / f"{timestamp}.log"

        # Set up environment with LOOP_HEADLESS for auto-approval
        env = os.environ.copy()
        env["LOOP_HEADLESS"] = "true"

        try:
            result = subprocess.run(
                cmd,
                cwd=self.workspace_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )

            # Write log
            with open(log_file, "w") as f:
                f.write(f"Command: {' '.join(cmd)}\n")
                f.write(f"Timestamp: {timestamp}\n")
                f.write(f"Return code: {result.returncode}\n")
                f.write(f"--- STDOUT ---\n{result.stdout}\n")
                f.write(f"--- STDERR ---\n{result.stderr}\n")

            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None,
                "log_file": str(log_file),
                "return_code": result.returncode
            }

        except subprocess.TimeoutExpired:
            logger.error(f"Loop CLI timeout for agent {self.agent_id}")
            with open(log_file, "w") as f:
                f.write(f"Command: {' '.join(cmd)}\n")
                f.write(f"Timestamp: {timestamp}\n")
                f.write(f"ERROR: Timeout after {timeout} seconds\n")

            return {
                "success": False,
                "output": None,
                "error": f"Execution timeout after {timeout} seconds",
                "log_file": str(log_file),
                "return_code": -1
            }
        except FileNotFoundError:
            logger.error("loop CLI not found. Is it installed?")
            return {
                "success": False,
                "output": None,
                "error": "loop CLI not found. Please install loop CLI.",
                "log_file": None,
                "return_code": -1
            }
        except Exception as e:
            logger.exception(f"Error executing loop CLI: {e}")
            return {
                "success": False,
                "output": None,
                "error": str(e),
                "log_file": str(log_file) if log_file.exists() else None,
                "return_code": -1
            }

    def update_state(self, updates: dict):
        """Update agent state.json file."""
        state = self.get_state()
        state.update(updates)
        state["updated_at"] = datetime.now().isoformat()

        with open(self.state_path, "w") as f:
            json.dump(state, f, indent=2)

    def get_state(self) -> dict:
        """Get current agent state from state.json."""
        if not self.state_path.exists():
            return {}

        with open(self.state_path) as f:
            return json.load(f)


class MockMCNAgentRunner(MCNAgentRunner):
    """Mock runner for testing without actual loop CLI."""

    def _execute_loop(self, prompt: str, timeout: int) -> dict:
        """Return mock response."""
        return {
            "success": True,
            "output": json.dumps({
                "status": "active",
                "message": "Mock execution successful",
                "prompt": prompt[:100]
            }),
            "error": None,
            "log_file": None,
            "return_code": 0
        }
