import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime


class EndpointConfig:
    """Represents a single endpoint configuration."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        # Support both 'source' (new) and 'behavior' (backward compatibility)
        self.source = config.get('source', self._map_behavior_to_source(config.get('behavior', 'microstrategy')))
        self.description = config.get('description', '')
        self.pagination = config.get('pagination', {})
        self.per_page = self.pagination.get('per_page', 100)
        
        # SQL/PG specific
        self.mssql = config.get('mssql', {})
        self.postgresql = config.get('postgresql', {})
        
        # MSTR specific
        self.mstr = config.get('mstr', {})
    
    @staticmethod
    def _map_behavior_to_source(behavior: str) -> str:
        """Map old behavior values to new source values for backward compatibility."""
        if behavior in ['livesql', 'cachesql']:
            return 'mssql'
        elif behavior in ['livepg', 'cachepg']:
            return 'postgresql'
        elif behavior in ['livemstr', 'cachemstr']:
            return 'microstrategy'
        return behavior  # Return as-is if already a source value
    
    @property
    def behavior(self) -> str:
        """Backward compatibility property - maps source to old behavior."""
        # All sources are now cached via nginx
        if self.source == 'mssql':
            return 'cachesql'
        elif self.source == 'postgresql':
            return 'cachepg'
        elif self.source == 'microstrategy':
            return 'cachemstr'
        return self.source
    
    @property
    def is_cached(self) -> bool:
        """Check if this endpoint uses caching - always True now (nginx caching)."""
        return True
    
    @property
    def is_mstr(self) -> bool:
        """Check if this endpoint uses MicroStrategy."""
        return self.source == 'microstrategy'
    
    @property
    def is_sql(self) -> bool:
        """Check if this endpoint uses MSSQL."""
        return self.source == 'mssql'
    
    @property
    def is_pg(self) -> bool:
        """Check if this endpoint uses PostgreSQL."""
        return self.source == 'postgresql'
    
    @property
    def cache_zone(self) -> str:
        """Get nginx cache zone name - always 'shortcache' now (10 minutes)."""
        return 'shortcache'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        config = {
            'source': self.source,
            'description': self.description,
            'pagination': {'per_page': self.per_page}
        }
        
        if self.mssql:
            config['mssql'] = self.mssql
        if self.postgresql:
            config['postgresql'] = self.postgresql
        if self.mstr:
            config['mstr'] = self.mstr
        
        return config


class EndpointConfigStore:
    """Manages endpoint configurations from YAML file."""
    
    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / 'config' / 'endpoints.yaml'
        self.config_path = config_path
        self._ensure_config_exists()
    
    def _ensure_config_exists(self):
        """Create default config file if it doesn't exist."""
        if not self.config_path.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self._save({'endpoints': {}})
    
    def _load(self) -> Dict[str, Any]:
        """Load YAML configuration."""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    
    def _save(self, data: Dict[str, Any]):
        """Save YAML configuration."""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
    
    def get_all(self) -> Dict[str, EndpointConfig]:
        """Get all endpoint configurations."""
        data = self._load()
        endpoints = data.get('endpoints', {})
        return {
            name: EndpointConfig(name, config)
            for name, config in endpoints.items()
        }
    
    def get(self, endpoint_name: str) -> Optional[EndpointConfig]:
        """Get single endpoint configuration."""
        endpoints = self.get_all()
        return endpoints.get(endpoint_name)
    
    def create(self, endpoint_name: str, config: Dict[str, Any]) -> EndpointConfig:
        """Create new endpoint configuration."""
        data = self._load()
        if 'endpoints' not in data:
            data['endpoints'] = {}
        
        if endpoint_name in data['endpoints']:
            raise ValueError(f"Endpoint '{endpoint_name}' already exists")
        
        endpoint = EndpointConfig(endpoint_name, config)
        data['endpoints'][endpoint_name] = endpoint.to_dict()
        self._save(data)
        return endpoint
    
    def update(self, endpoint_name: str, config: Dict[str, Any]) -> EndpointConfig:
        """Update existing endpoint configuration."""
        data = self._load()
        if 'endpoints' not in data or endpoint_name not in data['endpoints']:
            raise ValueError(f"Endpoint '{endpoint_name}' not found")
        
        endpoint = EndpointConfig(endpoint_name, config)
        data['endpoints'][endpoint_name] = endpoint.to_dict()
        self._save(data)
        return endpoint
    
    def delete(self, endpoint_name: str):
        """Delete endpoint configuration."""
        data = self._load()
        if 'endpoints' not in data or endpoint_name not in data['endpoints']:
            raise ValueError(f"Endpoint '{endpoint_name}' not found")
        
        del data['endpoints'][endpoint_name]
        self._save(data)
    
    def list_names(self) -> List[str]:
        """Get list of all endpoint names."""
        return list(self.get_all().keys())


# Singleton instance
_config_store: Optional[EndpointConfigStore] = None


def get_config_store() -> EndpointConfigStore:
    """Get config store singleton."""
    global _config_store
    if _config_store is None:
        _config_store = EndpointConfigStore()
    return _config_store
