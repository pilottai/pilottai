# Contributing to PilottAI

First off, thank you for considering contributing to PilottAI! This document provides guidelines and instructions for contributing to the project.

## Table of Contents
- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
  - [Development Setup](#development-setup)
  - [Project Structure](#project-structure)
- [Development Process](#development-process)
  - [Creating a Branch](#creating-a-branch)
  - [Making Changes](#making-changes)
  - [Testing](#testing)
  - [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Community](#community)

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to [conduct@pilottai.com](mailto:conduct@pilottai.com).

## Getting Started

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/yourusername/pilottai.git
   cd pilottai
   ```

2. **Set Up Python Environment**
   ```bash
   # Create a virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate

   # Install dependencies
   pip install poetry
   poetry install
   ```

3. **Install Pre-commit Hooks**
   ```bash
   pre-commit install
   ```

### Project Structure

```
pilott/
├── core/            # Core framework components
├── agents/          # Agent implementations
├── memory/          # Memory management
├── orchestration/   # System orchestration
├── tools/           # Tool integrations
├── utils/           # Utility functions
└── tests/           # Test suite
```

## Development Process

### Creating a Branch

- Create branches from `main` for all changes
- Use meaningful branch names following this pattern:
  - `feature/description` for new features
  - `fix/description` for bug fixes
  - `docs/description` for documentation changes
  - `refactor/description` for code refactoring

```bash
git checkout -b feature/your-feature-name
```

### Making Changes

1. Make focused, incremental changes
2. Follow the [coding standards](#coding-standards)
3. Update tests and documentation as needed
4. Commit regularly with clear messages:

```bash
git commit -m "feat: add new agent capability"
git commit -m "fix: resolve memory leak in job router"
```

### Testing

1. **Run Tests**
   ```bash
   poetry run pytest
   ```

2. **Test Coverage**
   ```bash
   poetry run pytest --cov=pilottai tests/
   ```

3. **Type Checking**
   ```bash
   poetry run mypy pilottai
   ```

### Documentation

- Update relevant documentation in the `docs/` directory
- Add docstrings to new functions and classes
- Include usage examples for new features

## Pull Request Process

1. **Before Submitting**
   - Ensure all tests pass
   - Check code coverage
   - Run linting and type checking
   - Update documentation
   - Rebase on latest main

2. **PR Template**
   - Fill out the PR template completely
   - Link related issues
   - Describe your changes thoroughly
   - Include screenshots for UI changes

3. **Review Process**
   - At least one maintainer review is required
   - Address review comments promptly
   - Keep PR scope focused

## Coding Standards

### Python Style Guide

- Follow PEP 8 guidelines
- Use type hints for all functions
- Maximum line length: 88 characters
- Use descriptive variable names

### Code Quality

```python
# Good Example
async def process_job(job: Job) -> JobResult:
    """Process a job and return its result.

    Args:
        job: The job to process

    Returns:
        JobResult: The result of job processing
    """
    try:
        result = await self._execute_job_steps(job)
        return JobResult(success=True, output=result)
    except Exception as e:
        return JobResult(success=False, error=str(e))
```

### Testing Standards

- Write unit tests for all new functionality
- Maintain test coverage above 90%
- Use meaningful test names and descriptions

```python
async def test_job_processing_success():
    """Test successful job processing with valid input."""
    job = Job(description="test job")
    result = await agent.process_job(job)
    assert result.success
    assert result.output is not None
```

## Community

- Join our [Discord](https://discord.gg/pilottai)
- Follow us on [Twitter](https://twitter.com/pilottai)
- Subscribe to our [newsletter](https://pilottai.com/newsletter)

## Questions or Need Help?

- Check our [documentation](https://docs.pilottai.com)
- Ask in our [Discord](https://discord.gg/pilottai)
- Open a [discussion](https://github.com/pilottai/pilott/discussions)

Thank you for contributing to PilottAI! 🚀
