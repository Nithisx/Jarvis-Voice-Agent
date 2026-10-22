"""Loads and validates MCP server configurations from brain/configs/mcp_servers.yaml."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from jarvis_brain.config import find_project_root, load_yaml_file
from jarvis_brain.exceptions import ConfigurationError


@dataclass(frozen=True)
class MCPServerConfig:
    name: str
    enabled: bool
    transport: str
    command: str
    args: list[str]
    working_dir: Path
    env: dict[str, str]
    timeout_seconds: float = 30.0


def load_mcp_servers_config() -> dict[str, MCPServerConfig]:
    """Load configuration for all registered MCP servers from mcp_servers.yaml."""
    root = find_project_root()
    yaml_path = root / "brain" / "configs" / "mcp_servers.yaml"
    raw = load_yaml_file(yaml_path)

    servers_dict = raw.get("mcp_servers", {})
    configs: dict[str, MCPServerConfig] = {}

    python_exe = sys.executable

    for name, s_cfg in servers_dict.items():
        if not s_cfg.get("enabled", True):
            continue

        module = s_cfg.get("module")
        if not module:
            raise ConfigurationError(f"MCP server '{name}' missing required 'module' parameter.")

        py_path_rel = s_cfg.get("python_path", "")
        py_path_abs = str((root / py_path_rel).resolve()) if py_path_rel else ""

        server_env = os.environ.copy()
        if py_path_abs:
            existing_pp = server_env.get("PYTHONPATH", "")
            server_env["PYTHONPATH"] = f"{py_path_abs}{os.pathpathsep}{existing_pp}" if existing_pp else py_path_abs

        configs[name] = MCPServerConfig(
            name=name,
            enabled=True,
            transport=s_cfg.get("transport", "stdio"),
            command=python_exe,
            args=["-m", module],
            working_dir=root,
            env=server_env,
            timeout_seconds=float(s_cfg.get("timeout_seconds", 30.0)),
        )

    return configs

