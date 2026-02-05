"""
CLI configuration management for persistent DWH settings.

Stores configuration in ~/.dwh/config.yaml or project-local .dwh.yaml
Priority: CLI option > env var (DWH_PLATFORM) > project config > global config
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from src.connectors import is_dwh_supported, list_supported_dwh
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Config file locations
GLOBAL_CONFIG_DIR = Path.home() / ".dwh"
GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.yaml"
LOCAL_CONFIG_FILE = Path(".dwh.yaml")

# Environment variable for DWH platform
ENV_VAR_PLATFORM = "DWH_PLATFORM"


class DWHConfig:
    """Manages DWH CLI configuration."""
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize config manager.
        
        Args:
            project_root: Project root directory for local config lookup
        """
        self.project_root = project_root or Path.cwd()
        self._global_config: Optional[Dict[str, Any]] = None
        self._local_config: Optional[Dict[str, Any]] = None
    
    @property
    def global_config_path(self) -> Path:
        """Get global config file path."""
        return GLOBAL_CONFIG_FILE
    
    @property
    def local_config_path(self) -> Path:
        """Get local (project) config file path."""
        return self.project_root / LOCAL_CONFIG_FILE.name
    
    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """Load YAML config file."""
        if path.exists():
            try:
                content = path.read_text()
                return yaml.safe_load(content) or {}
            except Exception as e:
                logger.warning(f"Failed to load config from {path}: {e}")
        return {}
    
    def _save_yaml(self, path: Path, data: Dict[str, Any]) -> None:
        """Save YAML config file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.dump(data, default_flow_style=False))
        logger.debug(f"Saved config to {path}")
    
    def get_global_config(self) -> Dict[str, Any]:
        """Load global config from ~/.dwh/config.yaml."""
        if self._global_config is None:
            self._global_config = self._load_yaml(self.global_config_path)
        return self._global_config
    
    def get_local_config(self) -> Dict[str, Any]:
        """Load local config from .dwh.yaml in project root."""
        if self._local_config is None:
            self._local_config = self._load_yaml(self.local_config_path)
        return self._local_config
    
    def get_platform(self, cli_override: Optional[str] = None) -> str:
        """
        Get the configured DWH platform.
        
        Priority:
        1. CLI override (--wh option)
        2. Environment variable (DWH_PLATFORM)
        3. Local project config (.dwh.yaml)
        4. Global config (~/.dwh/config.yaml)
        
        Args:
            cli_override: Platform specified via CLI option
            
        Returns:
            DWH platform shorthand
            
        Raises:
            ValueError: If no platform is configured
        """
        # 1. CLI override
        if cli_override:
            if not is_dwh_supported(cli_override):
                supported = list_supported_dwh()
                raise ValueError(
                    f"Unsupported platform: '{cli_override}'. "
                    f"Use one of: {', '.join(supported)}"
                )
            return cli_override.lower()
        
        # 2. Environment variable
        env_platform = os.getenv(ENV_VAR_PLATFORM)
        if env_platform:
            if not is_dwh_supported(env_platform):
                supported = list_supported_dwh()
                raise ValueError(
                    f"Invalid {ENV_VAR_PLATFORM}='{env_platform}'. "
                    f"Use one of: {', '.join(supported)}"
                )
            return env_platform.lower()
        
        # 3. Local project config
        local_config = self.get_local_config()
        if platform := local_config.get("platform"):
            return platform.lower()
        
        # 4. Global config
        global_config = self.get_global_config()
        if platform := global_config.get("platform"):
            return platform.lower()
        
        # No platform configured
        raise ValueError(
            "No DWH platform configured. Set it using one of:\n"
            "  dwh config set-wh <platform>     # Set globally\n"
            "  dwh config set-wh <platform> -l  # Set for this project\n"
            f"  export {ENV_VAR_PLATFORM}=<platform>  # Environment variable\n"
            f"\nSupported platforms: {', '.join(list_supported_dwh())}"
        )
    
    def set_platform(self, platform: str, local: bool = False) -> Path:
        """
        Set the DWH platform in config.
        
        Args:
            platform: DWH platform shorthand (sf, bq, rs, db)
            local: If True, save to local project config; otherwise global
            
        Returns:
            Path to the config file that was updated
            
        Raises:
            ValueError: If platform is not supported
        """
        platform = platform.lower()
        if not is_dwh_supported(platform):
            supported = list_supported_dwh()
            raise ValueError(
                f"Unsupported platform: '{platform}'. "
                f"Use one of: {', '.join(supported)}"
            )
        
        if local:
            config = self.get_local_config()
            config["platform"] = platform
            self._save_yaml(self.local_config_path, config)
            self._local_config = config
            return self.local_config_path
        else:
            config = self.get_global_config()
            config["platform"] = platform
            self._save_yaml(self.global_config_path, config)
            self._global_config = config
            return self.global_config_path
    
    def clear_platform(self, local: bool = False) -> Optional[Path]:
        """
        Clear the DWH platform from config.
        
        Args:
            local: If True, clear from local config; otherwise global
            
        Returns:
            Path to the config file that was updated, or None if not found
        """
        if local:
            config = self.get_local_config()
            if "platform" in config:
                del config["platform"]
                self._save_yaml(self.local_config_path, config)
                self._local_config = config
                return self.local_config_path
        else:
            config = self.get_global_config()
            if "platform" in config:
                del config["platform"]
                self._save_yaml(self.global_config_path, config)
                self._global_config = config
                return self.global_config_path
        return None
    
    def get_config_info(self) -> Dict[str, Any]:
        """
        Get comprehensive config info for display.
        
        Returns:
            Dictionary with all config sources and values
        """
        env_platform = os.getenv(ENV_VAR_PLATFORM)
        local_config = self.get_local_config()
        global_config = self.get_global_config()
        
        # Determine active platform and source
        active_platform = None
        active_source = None
        
        if env_platform and is_dwh_supported(env_platform):
            active_platform = env_platform.lower()
            active_source = f"env ({ENV_VAR_PLATFORM})"
        elif local_config.get("platform"):
            active_platform = local_config["platform"]
            active_source = f"local ({self.local_config_path})"
        elif global_config.get("platform"):
            active_platform = global_config["platform"]
            active_source = f"global ({self.global_config_path})"
        
        return {
            "active_platform": active_platform,
            "active_source": active_source,
            "env_var": env_platform,
            "local_config": local_config,
            "local_config_path": self.local_config_path,
            "global_config": global_config,
            "global_config_path": self.global_config_path,
        }


# Global config instance
_config: Optional[DWHConfig] = None


def get_config() -> DWHConfig:
    """Get the global config instance."""
    global _config
    if _config is None:
        _config = DWHConfig()
    return _config


def get_dwh_platform(cli_override: Optional[str] = None) -> str:
    """
    Convenience function to get the configured DWH platform.
    
    Args:
        cli_override: Platform specified via CLI option
        
    Returns:
        DWH platform shorthand
        
    Raises:
        ValueError: If no platform is configured
    """
    return get_config().get_platform(cli_override)
