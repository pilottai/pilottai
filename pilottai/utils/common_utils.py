import os
import yaml
from typing import Dict, List, Any, Optional, Union


def load_yaml_file(file_path: str) -> Dict[str, Any]:
    """
    Load a YAML file and return its contents.

    Args:
        file_path: Path to the YAML file

    Returns:
        Dict containing the YAML file contents

    Raises:
        FileNotFoundError: If the file doesn't exist
        yaml.YAMLError: If the file is not valid YAML
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"YAML file not found: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Error parsing YAML file {file_path}: {str(e)}")


def get_rules(rules_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load the rules.yaml file and return its contents.

    Args:
        rules_path: Optional custom path to the rules file

    Returns:
        Dict containing the rules
    """
    default_paths = [
        "pilottai/rules/rules.yaml",  # From project root
        "rules/rules.yaml",  # Alternative location
        "rules.yaml"  # Fallback
    ]

    if rules_path:
        paths_to_try = [rules_path] + default_paths
    else:
        paths_to_try = default_paths

    for path in paths_to_try:
        try:
            return load_yaml_file(path)
        except FileNotFoundError:
            continue

    raise FileNotFoundError("Could not find rules.yaml file in any of the expected locations")


def get_rule_value(
    key_path: str,
    default: Any = None,
    rules: Optional[Dict[str, Any]] = None
) -> Any:
    """
    Get a value from the rules using a dot-notation path.

    Args:
        key_path: Dot-notation path to the value (e.g., "agent.system.base")
        default: Default value to return if the key doesn't exist
        rules: Optional rules dict (will load from file if not provided)

    Returns:
        The value at the specified path, or the default if not found
    """
    if rules is None:
        try:
            rules = get_rules()
        except FileNotFoundError:
            return default

    parts = key_path.split('.')
    current = rules

    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return default

    return current


def get_agent_rule(
    rule_type: str,
    agent_type: Optional[str] = None,
    default: Any = None
) -> Any:
    """
    Get a specific rule for an agent.

    Args:
        rule_type: Type of rule to get (e.g., "system.base", "task_analysis")
        agent_type: Type of agent (defaults to "agent" if None)
        default: Default value to return if the rule doesn't exist

    Returns:
        The rule value, or the default if not found
    """
    agent_type = agent_type or "agent"
    key_path = f"{agent_type}.{rule_type}"
    return get_rule_value(key_path, default)


def get_prompt_template(
    prompt_type: str,
    agent_type: Optional[str] = None
) -> Optional[str]:
    """
    Get a prompt template from the rules.

    Args:
        prompt_type: Type of prompt to get (e.g., "task_analysis", "system")
        agent_type: Type of agent (defaults to "agent" if None)

    Returns:
        The prompt template string, or None if not found
    """
    return get_agent_rule(prompt_type, agent_type)


def format_prompt(
    prompt_template: str,
    variables: Dict[str, Any]
) -> str:
    """
    Format a prompt template with variables.

    Args:
        prompt_template: Template string with {variable} placeholders
        variables: Dictionary of variables to substitute

    Returns:
        Formatted prompt string
    """
    # Handle missing variables by replacing them with empty strings
    # This prevents KeyError when a variable is in the template but not in the variables dict
    formatted_prompt = prompt_template

    for key, value in variables.items():
        placeholder = "{" + key + "}"
        formatted_prompt = formatted_prompt.replace(placeholder, str(value))

    return formatted_prompt


def get_agent_prompts(agent_type: Optional[str] = None) -> Dict[str, str]:
    """
    Get all prompts for an agent type.

    Args:
        agent_type: Type of agent (defaults to "agent" if None)

    Returns:
        Dictionary of prompt templates keyed by prompt type
    """
    agent_type = agent_type or "agent"
    rules = get_rules()

    if agent_type not in rules:
        return {}

    return rules[agent_type]


def get_all_agent_types() -> List[str]:
    """
    Get all available agent types from the rules.

    Returns:
        List of agent type strings
    """
    rules = get_rules()
    return [key for key in rules.keys() if isinstance(rules[key], dict)]


def format_system_prompt(
    agent_role: str,
    agent_goal: str,
    agent_description: Optional[str] = None,
    agent_type: Optional[str] = None
) -> str:
    """
    Format the system prompt for an agent.

    Args:
        agent_role: Role of the agent
        agent_goal: Goal of the agent
        agent_description: Optional description for the agent
        agent_type: Type of agent (defaults to "agent" if None)

    Returns:
        Formatted system prompt
    """
    template = get_agent_rule("system.base", agent_type,
                              "You are an AI agent with:\nRole: {role}\nGoal: {goal}\nDescription: {description}")

    return format_prompt(template, {
        "role": agent_role,
        "goal": agent_goal,
        "description": agent_description or "No specific description provided."
    })


def get_tool_rules(
    tool_name: str,
    rule_key: Optional[str] = None,
    default: Any = None
) -> Any:
    """
    Get rules for a specific tool.

    Args:
        tool_name: Name of the tool
        rule_key: Optional specific rule key to get
        default: Default value if rule not found

    Returns:
        Tool rules or specific rule value
    """
    rules = get_rules()
    if "tools" not in rules or tool_name not in rules["tools"]:
        return default

    tool_rules = rules["tools"][tool_name]

    if rule_key:
        return tool_rules.get(rule_key, default)
    return tool_rules
