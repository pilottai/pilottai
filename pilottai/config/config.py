from typing import Optional, Union, Dict, Any

from pilottai.core.base_config import (
    ServeConfig,
    SecureConfig,
    LLMConfig,
    LogConfig,
    AgentConfig,
    RouterConfig,
    LoadBalancerConfig,
    ScalingConfig,
    FaultToleranceConfig
)


class Config:
    def __init__(
        self,
        name: str = "PilottAI",
        serve_config: Optional[Union[Dict[str, Any], ServeConfig]] = None,
        secure_config: Optional[Union[Dict[str, Any], SecureConfig]] = None,
        llm_config: Optional[Union[Dict[str, Any], LLMConfig]] = None,
        log_config: Optional[Union[Dict[str, Any], LogConfig]] = None,
        agent_config: Optional[Union[Dict[str, Any], AgentConfig]] = None,
        router_config: Optional[Union[Dict[str, Any], RouterConfig]] = None,
        load_balancer_config: Optional[Union[Dict[str, Any], LoadBalancerConfig]] = None,
        scaling_config: Optional[Union[Dict[str, Any], ScalingConfig]] = None,
        fault_tolerance_config: Optional[Union[Dict[str, Any], FaultToleranceConfig]] = None,
    ):
        self.name = name
        self.serve_config = self._init_config(serve_config, ServeConfig)
        self.secure_config = self._init_config(secure_config, SecureConfig)
        self.llm_config = self._init_config(llm_config, LLMConfig)
        self.log_config = self._init_config(log_config, LogConfig)
        self.agent_config = self._init_config(agent_config, AgentConfig)
        self.router_config = self._init_config(router_config, RouterConfig)
        self.load_balancer_config = self._init_config(load_balancer_config, LoadBalancerConfig)
        self.scaling_config = self._init_config(scaling_config, ScalingConfig)
        self.fault_tolerance_config = self._init_config(fault_tolerance_config, FaultToleranceConfig)

    def _init_config(self, config: Optional[Union[Dict[str, Any], object]], config_class: type) -> object:
        """Initialize configuration object from dict or existing object"""
        if config is None:
            # Create with defaults, but handle classes that need required parameters
            try:
                return config_class()
            except TypeError:
                # If class requires parameters, return None
                return None
        elif isinstance(config, dict):
            # Create from dictionary
            try:
                return config_class(**config)
            except TypeError as e:
                raise ValueError(f"Invalid configuration for {config_class.__name__}: {str(e)}")
        elif isinstance(config, config_class):
            # Already the correct type, return as-is
            return config
        else:
            raise ValueError(f"Config must be a dict or {config_class.__name__} instance, got {type(config)}")

    def update_config(self, config_name: str, config_data: Union[Dict[str, Any], object]) -> None:
        """Update a specific configuration"""
        if not hasattr(self, config_name):
            raise ValueError(f"Unknown config: {config_name}")

        current_config = getattr(self, config_name)
        config_class = type(current_config) if current_config else None

        # Map config names to classes
        config_mapping = {
            'serve_config': ServeConfig,
            'secure_config': SecureConfig,
            'llm_config': LLMConfig,
            'log_config': LogConfig,
            'agent_config': AgentConfig,
            'router_config': RouterConfig,
            'load_balancer_config': LoadBalancerConfig,
            'scaling_config': ScalingConfig,
            'fault_tolerance_config': FaultToleranceConfig,
        }

        if config_name in config_mapping:
            config_class = config_mapping[config_name]
            setattr(self, config_name, self._init_config(config_data, config_class))
        else:
            raise ValueError(f"Unknown config name: {config_name}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert all configurations to dictionary"""
        result = {'name': self.name}

        for attr_name in ['serve_config', 'secure_config', 'llm_config', 'log_config',
                          'agent_config', 'router_config', 'load_balancer_config',
                          'scaling_config', 'fault_tolerance_config']:
            config = getattr(self, attr_name)
            if config:
                if hasattr(config, 'to_dict'):
                    result[attr_name] = config.to_dict()
                elif hasattr(config, 'model_dump'):
                    result[attr_name] = config.model_dump()
                else:
                    result[attr_name] = config.__dict__

        return result
