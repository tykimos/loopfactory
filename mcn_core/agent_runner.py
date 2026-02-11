"""Agent runner for executing loop CLI commands."""
import subprocess
import json
import os
import time
from pathlib import Path
from datetime import datetime
from typing import Optional
import logging
from mcn_core.config import get_config
from mcn_core.database import get_db_connection
from mcn_core.agent_profiles import resolve_agent_profile

logger = logging.getLogger(__name__)

class MCNAgentRunner:
    """Executes loop CLI commands for agent operations."""

    # SKILL_URL from config, with fallback to default
    DEFAULT_SKILL_URL = "https://assibucks.vercel.app/skill.md"
    MAX_RETRY_ATTEMPTS = 8
    RETRYABLE_ERROR_KEYWORDS = (
        "concurrency",
        "rate limit",
        "rate-limit",
        "too many requests",
        "429",
        "resource_exhausted",
    )

    def __init__(self, agent_id: str, base_dir: Path = None):
        self.agent_id = agent_id
        self.config = get_config()
        self.base_dir = base_dir or Path(__file__).parent.parent / "agents"
        self.workspace_dir = self.base_dir / agent_id
        self.ghost_path = self.workspace_dir / "ghost.md"
        self.shell_path = self.workspace_dir / "shell.md"
        self.state_path = self.workspace_dir / "state.json"
        self.log_dir = self.workspace_dir / "logs"

    @property
    def skill_url(self) -> str:
        """Get skill URL from config or default."""
        return getattr(self.config.loop, 'skill_url', self.DEFAULT_SKILL_URL)

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
        return self._execute_loop(prompt, timeout=180)

    def run_with_prompt(self, prompt: str, timeout: int = 300) -> dict:
        """Execute loop CLI with a custom prompt (for reactivation prompts)."""
        return self._execute_loop(prompt, timeout)

    def execute(
        self,
        prompt: str,
        skill_url: str = None,
        timeout: int = 300,
        skill_config: dict = None
    ) -> dict:
        """Execute loop CLI with optional dynamic skill configuration.

        Args:
            prompt: The prompt to send to the agent
            skill_url: Optional skill URL (uses config default if not provided)
            timeout: Execution timeout in seconds
            skill_config: Optional skill configuration for dynamic skill file generation

        Returns:
            dict with success, output, error, log_file, return_code
        """
        # Determine effective skill URL
        effective_skill_url = skill_url or self.skill_url

        # If skill_config provided, create temp skill file
        if skill_config:
            effective_skill_url = self._create_temp_skill_file(skill_config)

        return self._execute_loop(prompt, timeout, effective_skill_url)

    def _create_temp_skill_file(self, skills_data: dict) -> str:
        """Create temporary skill file from skills data.

        Args:
            skills_data: Skills data dict from SkillManager.get_skills_for_task()
                        (contains selected_skills, enabled_categories, skill_names)

        Returns:
            file:// URL to the temp skill file
        """
        from mcn_core.skill_manager import get_skill_builder

        builder = get_skill_builder()
        return builder.create_temp_skill_file(skills_data, self.workspace_dir)

    @property
    def loop_cli_path(self) -> str:
        """Get loop CLI path from config."""
        return getattr(self.config.assiloop, 'cli_command', 'loop')

    def _is_retryable_limit_error(self, stdout_text: str, stderr_text: str) -> bool:
        """Return True if output suggests transient concurrency/rate limiting."""
        combined = f"{stdout_text or ''}\n{stderr_text or ''}".lower()
        return any(keyword in combined for keyword in self.RETRYABLE_ERROR_KEYWORDS)

    def _execute_loop(self, prompt: str, timeout: int, skill_url: str = None) -> dict:
        """Execute loop CLI and capture output."""
        # Resolve agent profile to check system_prompt_mode
        profile_env, mcp_servers, system_prompt_mode, profile_model = resolve_agent_profile(self.agent_id)

        # Determine effective skill URL
        effective_skill_url = skill_url or self.skill_url

        # Use skill_compact.md when system_prompt_mode is "compact"
        if system_prompt_mode == "compact" and effective_skill_url:
            if effective_skill_url.endswith("/skill.md"):
                effective_skill_url = effective_skill_url.replace("/skill.md", "/skill_compact.md")
                print(f"[AGENT_RUNNER] Compact mode: using {effective_skill_url}", flush=True)

        # Build command with headless mode (use full path from config)
        cmd = [
            self.loop_cli_path,
            "--headless",
            "--skill-url", effective_skill_url,
            "--ghost", str(self.ghost_path),
            "--shell", str(self.shell_path),
        ]

        # If agent has a local .assiloop/config.yaml, pass it explicitly
        config_path = self.workspace_dir / ".assiloop" / "config.yaml"
        if config_path.exists():
            cmd += ["--config", str(config_path)]

        cmd += ["--prompt", prompt]

        # Create log file
        self.ensure_workspace()
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_file = self.log_dir / f"{timestamp}.log"

        # Set up environment with LOOP_HEADLESS for auto-approval
        env = os.environ.copy()
        env["LOOP_HEADLESS"] = "true"

        # Apply loop-level env overrides
        loop_env = getattr(self.config.loop, "env", None) or {}
        for key, value in loop_env.items():
            env[str(key)] = str(value)

        # Resolve model: profile model has priority, then agent DB model.
        model = None
        try:
            if profile_model:
                model = profile_model
            else:
                with get_db_connection() as conn:
                    cursor = conn.execute(
                        "SELECT model FROM agents WHERE id = ?",
                        (self.agent_id,)
                    )
                    row = cursor.fetchone()
                    if row and row["model"]:
                        model = row["model"]
        except Exception:
            model = None

        if model:
            env["CLAUDE_MODEL"] = model
            # For models with smaller context (qwen 65K), reduce max_output_tokens
            # This is safe because env is passed per-subprocess, not globally
            # Use 8000 to leave room for ~57K input tokens
            if "qwen" in model.lower():
                env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = "8000"
        else:
            logger.warning(f"No model set in DB for agent {self.agent_id}")

        # Apply agent profile env overrides (profile resolved earlier for skill_url)
        for key, value in profile_env.items():
            env[str(key)] = str(value)

        # Build effective settings file (merge base settings with MCP servers)
        settings_path = getattr(self.config.loop, "settings_path", None)
        settings_obj = None
        if settings_path:
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings_obj = json.load(f)
            except Exception:
                settings_obj = None

        if mcp_servers:
            if not settings_obj:
                settings_obj = {}
            settings_obj["mcpServers"] = mcp_servers

        if settings_obj:
            # Write settings to agent workspace to avoid mutating global settings
            self.ensure_workspace()
            settings_file = self.workspace_dir / "settings.json"
            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(settings_obj, f)
            env["CLAUDE_CODE_SETTINGS"] = str(settings_file)
        elif settings_path and "CLAUDE_CODE_SETTINGS" not in env:
            env["CLAUDE_CODE_SETTINGS"] = settings_path

        try:
            attempts_log = []
            result = None

            for attempt in range(1, self.MAX_RETRY_ATTEMPTS + 1):
                result = subprocess.run(
                    cmd,
                    cwd=self.workspace_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=env
                )

                retryable = (
                    result.returncode != 0 and
                    attempt < self.MAX_RETRY_ATTEMPTS and
                    self._is_retryable_limit_error(result.stdout, result.stderr)
                )

                attempts_log.append({
                    "attempt": attempt,
                    "return_code": result.returncode,
                    "retryable": retryable,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                })

                if result.returncode == 0:
                    break

                if retryable:
                    backoff_seconds = min(2 ** (attempt - 1), 30)
                    logger.warning(
                        f"Retryable limit/concurrency error for agent {self.agent_id} "
                        f"(attempt {attempt}/{self.MAX_RETRY_ATTEMPTS}); retrying in {backoff_seconds}s"
                    )
                    time.sleep(backoff_seconds)
                    continue

                break

            # Write log
            with open(log_file, "w") as f:
                f.write(f"Command: {' '.join(cmd)}\n")
                f.write(f"Timestamp: {timestamp}\n")
                f.write(f"Model env (CLAUDE_MODEL): {env.get('CLAUDE_MODEL', '(unset)')}\n")
                f.write(f"Return code: {result.returncode if result else 'N/A'}\n")
                f.write(f"Attempts: {len(attempts_log)} / {self.MAX_RETRY_ATTEMPTS}\n")
                for attempt_info in attempts_log:
                    f.write(
                        f"\n--- ATTEMPT {attempt_info['attempt']} "
                        f"(rc={attempt_info['return_code']}, retryable={attempt_info['retryable']}) ---\n"
                    )
                    f.write(f"--- STDOUT ---\n{attempt_info['stdout']}\n")
                    f.write(f"--- STDERR ---\n{attempt_info['stderr']}\n")

            return {
                "success": result.returncode == 0 if result else False,
                "output": result.stdout if result else None,
                "error": result.stderr if result and result.returncode != 0 else None,
                "log_file": str(log_file),
                "return_code": result.returncode if result else -1
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
            logger.error(f"loop CLI not found at: {self.loop_cli_path}")
            return {
                "success": False,
                "output": None,
                "error": f"loop CLI not found at: {self.loop_cli_path}. Check config.yaml assiloop.cli_command",
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

    def _execute_loop(self, prompt: str, timeout: int, skill_url: str = None) -> dict:
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
