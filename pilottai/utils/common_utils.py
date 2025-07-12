import os
import re
import json
import yaml
from typing import Dict, List, Any, Optional
from pathlib import Path


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


def _find_project_root() -> Optional[Path]:
    """
    Find the project root by looking for common project files.

    Returns:
        Path to project root or None if not found
    """
    current = Path.cwd()

    # Look for common project indicators
    indicators = ['pyproject.toml', 'setup.py', 'requirements.txt', '.git']

    # Traverse up the directory tree
    for parent in [current] + list(current.parents):
        if any((parent / indicator).exists() for indicator in indicators):
            return parent

    return current  # Fallback to current directory


def _get_package_root() -> Optional[Path]:
    """
    Find the package root by looking for __init__.py files.

    Returns:
        Path to the main package directory
    """
    project_root = _find_project_root()
    if not project_root:
        return None

    # Look for main package directories (those with __init__.py)
    for item in project_root.iterdir():
        if item.is_dir() and (item / '__init__.py').exists():
            # Check if it has a rules subdirectory
            if (item / 'rules').exists():
                return item

    return None


def get_rules(rules_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load the rules.yaml file and return its contents.
    Uses dynamic path discovery to find the rules file.

    Args:
        rules_path: Optional custom path to the rules file

    Returns:
        Dict containing the rules
    """
    if rules_path:
        return load_yaml_file(rules_path)

    # Dynamic path discovery
    paths_to_try = []

    # Add custom path if provided
    if rules_path:
        paths_to_try.append(rules_path)

    # Try to find project and package roots
    project_root = _find_project_root()
    package_root = _get_package_root()

    # Build potential paths
    if package_root:
        paths_to_try.extend([
            str(package_root / 'rules' / 'rules.yaml'),
            str(package_root / 'rules.yaml')
        ])

    if project_root:
        paths_to_try.extend([
            str(project_root / 'rules' / 'rules.yaml'),
            str(project_root / 'rules.yaml')
        ])

    # Add fallback paths relative to current working directory
    paths_to_try.extend([
        "rules/rules.yaml",
        "rules.yaml",
        # Common package names
        "pilottai/rules/rules.yaml",
        "pilott/rules/rules.yaml",
        "src/rules/rules.yaml"
    ])

    # Try each path
    for path in paths_to_try:
        try:
            if os.path.exists(path):
                return load_yaml_file(path)
        except (FileNotFoundError, yaml.YAMLError):
            continue

    # If all else fails, try to find any rules.yaml file recursively
    if project_root:
        for rules_file in project_root.rglob("rules.yaml"):
            try:
                return load_yaml_file(str(rules_file))
            except (FileNotFoundError, yaml.YAMLError):
                continue

    raise FileNotFoundError(
        f"Could not find rules.yaml file. Searched in: {paths_to_try}"
    )


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
    try:
        rules = get_rules()
        if agent_type not in rules:
            return {}
        return rules[agent_type]
    except FileNotFoundError:
        return {}


def get_all_agent_types() -> List[str]:
    """
    Get all available agent types from the rules.

    Returns:
        List of agent type strings
    """
    try:
        rules = get_rules()
        return [key for key in rules.keys() if isinstance(rules[key], dict)]
    except FileNotFoundError:
        return []


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
    template = get_agent_rule(
        "system.base",
        agent_type,
        "You are an AI agent with:\nRole: {role}\nGoal: {goal}\nDescription: {description}"
    )

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
    try:
        rules = get_rules()
        if "tools" not in rules or tool_name not in rules["tools"]:
            return default

        tool_rules = rules["tools"][tool_name]

        if rule_key:
            return tool_rules.get(rule_key, default)
        return tool_rules
    except FileNotFoundError:
        return default


def extract_json_from_response(response: str) -> dict:
    try:
        # Step 1: Try to extract content between triple backticks
        match = re.search(r"```(?:json)?\s*(\{.*?})\s*```", response, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            # Fallback: Assume the entire content is JSON
            json_str = response.strip()

        # Step 2: Parse the JSON
        return json.loads(json_str)

    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to decode JSON: {e}")
    except Exception as e:
        raise ValueError(f"Unexpected error during JSON extraction: {e}")
