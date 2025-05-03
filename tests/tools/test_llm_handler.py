import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from pilott.engine.llm import LLMHandler
from pilott.config.config import LLMConfig


@pytest.fixture
def llm_config():
    """Fixture for LLM configuration"""
    return LLMConfig(
        model_name="test-model",
        provider="test-provider",
        api_key="test-key",
        temperature=0.7,
        max_tokens=2000,
        max_rpm=10,
        retry_attempts=3,
        retry_delay=1.0
    )


@pytest.fixture
def llm_handler(llm_config):
    """Fixture for LLMHandler with mocked LiteLLM"""
    with patch('pilott.engine.llm.litellm') as mock_litellm:
        handler = LLMHandler(llm_config)
        # Set up the mock to be used in tests
        handler.litellm = mock_litellm
        yield handler


class TestLLMHandler:
    @pytest.mark.asyncio
    async def test_initialization(self, llm_config):
        """Test LLMHandler initialization"""
        # Test with LLMConfig object
        handler = LLMHandler(llm_config)
        assert handler.config["model"] == "test-model"
        assert handler.config["provider"] == "test-provider"
        assert handler.config["temperature"] == 0.7
        assert handler.config["max_tokens"] == 2000
        assert handler.config["max_rpm"] == 10
        assert handler.config["retry_attempts"] == 3
        assert handler.config["retry_delay"] == 1.0

        # Test with dictionary
        config_dict = {
            "model_name": "dict-model",
            "provider": "dict-provider",
            "api_key": "dict-key",
            "temperature": 0.5,
            "max_tokens": 1000
        }
        handler = LLMHandler(config_dict)
        assert handler.config["model"] == "dict-model"
        assert handler.config["provider"] == "dict-provider"
        assert handler.config["temperature"] == 0.5
        assert handler.config["max_tokens"] == 1000

    @pytest.mark.asyncio
    async def test_generate_response(self, llm_handler):
        """Test generating a response from LLM"""
        # Mock litellm.acompletion to return a successful response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].message.role = "assistant"
        mock_response.model = "test-model"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        llm_handler.litellm.acompletion = AsyncMock(return_value=mock_response)

        # Create test messages
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"}
        ]

        # Generate response
        response = await llm_handler.generate_response(messages)

        # Verify response format
        assert response["content"] == "Test response"
        assert response["role"] == "assistant"
        assert response["model"] == "test-model"
        assert "usage" in response
        assert response["usage"]["prompt_tokens"] == 10
        assert response["usage"]["completion_tokens"] == 5
        assert response["usage"]["total_tokens"] == 15

        # Verify LiteLLM was called with correct parameters
        llm_handler.litellm.acompletion.assert_called_once()
        call_args = llm_handler.litellm.acompletion.call_args[1]
        assert call_args["model"] == "test-model"
        assert call_args["messages"] == messages
        assert call_args["temperature"] == 0.7
        assert call_args["max_tokens"] == 2000

    @pytest.mark.asyncio
    async def test_generate_response_with_tools(self, llm_handler):
        """Test generating a response with tools"""
        # Mock response with tool calls
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.role = "assistant"
        mock_response.choices[0].message.tool_calls = [
            {"type": "function", "function": {"name": "test_tool", "arguments": "{}"}}
        ]
        mock_response.model = "test-model"
        mock_response.usage.prompt_tokens = 15
        mock_response.usage.completion_tokens = 10
        mock_response.usage.total_tokens = 25

        llm_handler.litellm.acompletion = AsyncMock(return_value=mock_response)

        # Create test messages and tools
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Use the test tool"}
        ]

        tools = [
            {
                "name": "test_tool",
                "description": "A test tool",
                "parameters": {"type": "object", "properties": {}}
            }
        ]

        # Generate response
        response = await llm_handler.generate_response(messages, tools)

        # Verify response format
        assert response["content"] is None
        assert response["role"] == "assistant"
        assert "tool_calls" in response
        assert response["tool_calls"][0]["type"] == "function"
        assert response["tool_calls"][0]["function"]["name"] == "test_tool"

        # Verify LiteLLM was called with correct parameters
        llm_handler.litellm.acompletion.assert_called_once()
        call_args = llm_handler.litellm.acompletion.call_args[1]
        assert "tools" in call_args
        assert call_args["tool_choice"] == "auto"

    @pytest.mark.asyncio
    async def test_rate_limiting(self, llm_handler):
        """Test rate limiting functionality"""
        # Set max_rpm to a low value for testing
        llm_handler.config["max_rpm"] = 2

        # Mock litellm.acompletion to return success
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].message.role = "assistant"
        mock_response.model = "test-model"
        mock_response.usage = MagicMock()

        llm_handler.litellm.acompletion = AsyncMock(return_value=mock_response)

        # Create test messages
        messages = [{"role": "user", "content": "Test"}]

        # Mock sleep to speed up test
        original_sleep = asyncio.sleep
        asyncio.sleep = AsyncMock()

        try:
            # Make multiple requests to trigger rate limiting
            for _ in range(3):
                await llm_handler.generate_response(messages)

            # Verify sleep was called for rate limiting
            asyncio.sleep.assert_called()
            assert len(llm_handler.call_times) <= llm_handler.config["max_rpm"]

        finally:
            # Restore original sleep function
            asyncio.sleep = original_sleep

    @pytest.mark.asyncio
    async def test_error_handling_and_retry(self, llm_handler):
        """Test error handling and retry logic"""
        # Mock litellm.acompletion to fail then succeed
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Success after retry"
        mock_response.choices[0].message.role = "assistant"
        mock_response.model = "test-model"
        mock_response.usage = MagicMock()

        # Set up side effects: first call raises exception, second call succeeds
        llm_handler.litellm.acompletion = AsyncMock(
            side_effect=[ValueError("Test error"), mock_response]
        )

        # Adjust retry settings for faster test
        llm_handler.config["retry_attempts"] = 2
        llm_handler.config["retry_delay"] = 0.1

        # Mock sleep to speed up test
        original_sleep = asyncio.sleep
        asyncio.sleep = AsyncMock()

        try:
            # Generate response with retries
            messages = [{"role": "user", "content": "Test retry"}]
            response = await llm_handler.generate_response(messages)

            # Verify response after retry
            assert response["content"] == "Success after retry"

            # Verify retry happened
            assert llm_handler.litellm.acompletion.call_count == 2
            asyncio.sleep.assert_called_once()

        finally:
            # Restore original sleep function
            asyncio.sleep = original_sleep

    @pytest.mark.asyncio
    async def test_format_tools(self, llm_handler):
        """Test formatting of tools for LLM API"""
        # Define test tools
        tools = [
            {
                "name": "test_tool_1",
                "description": "A test tool",
                "parameters": {"type": "object", "properties": {"param1": {"type": "string"}}}
            },
            {
                "name": "test_tool_2",
                "description": "Another test tool"
            }
        ]

        # Format tools
        formatted_tools = llm_handler._format_tools(tools)

        # Verify formatting
        assert len(formatted_tools) == 2
        assert formatted_tools[0]["type"] == "function"
        assert formatted_tools[0]["function"]["name"] == "test_tool_1"
        assert formatted_tools[0]["function"]["description"] == "A test tool"
        assert "parameters" in formatted_tools[0]["function"]

        assert formatted_tools[1]["type"] == "function"
        assert formatted_tools[1]["function"]["name"] == "test_tool_2"
        assert formatted_tools[1]["function"]["description"] == "Another test tool"

        # Test with invalid tool format
        with pytest.raises(ValueError):
            llm_handler._format_tools([{"invalid": "tool"}])

    @pytest.mark.asyncio
    async def test_process_response(self, llm_handler):
        """Test processing of LLM response"""
        # Create mock ModelResponse
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].message.role = "assistant"
        mock_response.model = "test-model"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        # Process response
        processed = llm_handler._process_response(mock_response)

        # Verify processing
        assert processed["content"] == "Test response"
        assert processed["role"] == "assistant"
        assert processed["model"] == "test-model"
        assert processed["usage"]["prompt_tokens"] == 10
        assert processed["usage"]["completion_tokens"] == 5
        assert processed["usage"]["total_tokens"] == 15

        # Test with invalid response
        with pytest.raises(ValueError):
            llm_handler._process_response(None)

        with pytest.raises(ValueError):
            invalid_response = MagicMock()
            invalid_response.choices = []
            llm_handler._process_response(invalid_response)

    @pytest.mark.asyncio
    async def test_exceeding_max_retries(self, llm_handler):
        """Test behavior when max retries is exceeded"""
        # Mock litellm.acompletion to always fail
        llm_handler.litellm.acompletion = AsyncMock(side_effect=ValueError("Persistent error"))

        # Adjust retry settings for faster test
        llm_handler.config["retry_attempts"] = 2
        llm_handler.config["retry_delay"] = 0.1

        # Mock sleep to speed up test
        original_sleep = asyncio.sleep
        asyncio.sleep = AsyncMock()

        try:
            # Generate response with retries that will all fail
            messages = [{"role": "user", "content": "Test failure"}]

            # Expect exception after all retries fail
            with pytest.raises(ValueError) as exc_info:
                await llm_handler.generate_response(messages)

            assert "Persistent error" in str(exc_info.value)

            # Verify all retries were attempted
            assert llm_handler.litellm.acompletion.call_count == llm_handler.config["retry_attempts"]

        finally:
            # Restore original sleep function
            asyncio.sleep = original_sleep
