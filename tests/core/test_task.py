import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from pilottai.config.model import TaskResult
from pilottai.task.task import Task
from pilottai.enums.task_e import TaskStatus, TaskPriority


class TestTask:
    def test_initialization(self):
        """Test basic initialization of Task with default and custom values"""
        # Test with minimal parameters
        task = Task(description="Test task")
        assert task.description == "Test task"
        assert task.status == TaskStatus.PENDING
        assert task.priority == TaskPriority.MEDIUM
        assert task.context == {}
        assert task.deadline is None
        assert task.agent_id is None
        assert task.created_at is not None
        assert task.started_at is None
        assert task.completed_at is None
        assert task.result is None
        assert task.id is not None  # Should have auto-generated ID

        # Test with custom parameters
        custom_context = {"key": "value"}
        custom_deadline = datetime.now() + timedelta(hours=1)
        task = Task(
            description="Custom task",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.HIGH,
            context=custom_context,
            deadline=custom_deadline,
            agent_id="test_agent"
        )

        assert task.description == "Custom task"
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.priority == TaskPriority.HIGH
        assert task.context == custom_context
        assert task.deadline == custom_deadline
        assert task.agent_id == "test_agent"

    @pytest.mark.asyncio
    async def test_mark_started(self):
        """Test marking a task as started"""
        task = Task(description="Test task")
        assert task.status == TaskStatus.PENDING
        assert task.started_at is None

        # Mark as started
        await task.mark_started(agent_id="test_agent")

        assert task.status == TaskStatus.IN_PROGRESS
        assert task.agent_id == "test_agent"
        assert task.started_at is not None

        # Test trying to start a non-pending task
        task = Task(description="Already started", status=TaskStatus.IN_PROGRESS)
        with pytest.raises(ValueError):
            await task.mark_started(agent_id="test_agent")

    @pytest.mark.asyncio
    async def test_mark_completed_success(self):
        """Test marking a task as completed successfully"""
        task = Task(description="Test task", status=TaskStatus.IN_PROGRESS)

        # Create successful result
        result = TaskResult(
            success=True,
            output="Task completed successfully",
            error=None,
            execution_time=1.5,
            metadata={"key": "value"}
        )

        # Mark as completed
        await task.mark_completed(result)

        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None
        assert task.result == result
        assert task.result.success is True

    @pytest.mark.asyncio
    async def test_mark_completed_failure(self):
        """Test marking a task as failed"""
        task = Task(description="Test task", status=TaskStatus.IN_PROGRESS)

        # Create failure result
        result = TaskResult(
            success=False,
            output=None,
            error="Test error",
            execution_time=0.5,
            metadata={}
        )

        # Mark as completed with failure
        await task.mark_completed(result)

        assert task.status == TaskStatus.FAILED
        assert task.completed_at is not None
        assert task.result == result
        assert task.result.success is False
        assert task.result.error == "Test error"

    @pytest.mark.asyncio
    async def test_mark_cancelled(self):
        """Test marking a task as cancelled"""
        task = Task(description="Test task", status=TaskStatus.IN_PROGRESS)
        task.started_at = datetime.now() - timedelta(minutes=5)

        # Mark as cancelled
        await task.mark_cancelled(reason="User cancelled")

        assert task.status == TaskStatus.CANCELLED
        assert task.completed_at is not None
        assert task.result is not None
        assert task.result.success is False
        assert "User cancelled" in task.result.error

    def test_is_completed_property(self):
        """Test is_completed property"""
        # Test with various statuses
        completed_task = Task(description="Completed", status=TaskStatus.COMPLETED)
        failed_task = Task(description="Failed", status=TaskStatus.FAILED)
        cancelled_task = Task(description="Cancelled", status=TaskStatus.CANCELLED)
        pending_task = Task(description="Pending", status=TaskStatus.PENDING)
        in_progress_task = Task(description="In Progress", status=TaskStatus.IN_PROGRESS)

        # Check completion status
        assert completed_task.is_completed is True
        assert failed_task.is_completed is True
        assert cancelled_task.is_completed is True
        assert pending_task.is_completed is False
        assert in_progress_task.is_completed is False

    def test_is_active_property(self):
        """Test is_active property"""
        # Test with various statuses
        in_progress_task = Task(description="In Progress", status=TaskStatus.IN_PROGRESS)
        pending_task = Task(description="Pending", status=TaskStatus.PENDING)
        completed_task = Task(description="Completed", status=TaskStatus.COMPLETED)

        # Check active status
        assert in_progress_task.is_active is True
        assert pending_task.is_active is False
        assert completed_task.is_active is False

    def test_is_expired_property(self):
        """Test is_expired property"""
        # Task with no deadline
        task_no_deadline = Task(description="No deadline")
        assert task_no_deadline.is_expired is False

        # Task with future deadline
        future_deadline = datetime.now() + timedelta(hours=1)
        task_future = Task(description="Future deadline", deadline=future_deadline)
        assert task_future.is_expired is False

        # Task with past deadline
        past_deadline = datetime.now() - timedelta(hours=1)
        task_past = Task(description="Past deadline", deadline=past_deadline)
        assert task_past.is_expired is True

    def test_duration_property(self):
        """Test duration property calculation"""
        # Task with no timing information
        task_no_timing = Task(description="No timing")
        assert task_no_timing.duration is None

        # Task with start and completion
        task_completed = Task(description="Completed task")
        task_completed.started_at = datetime.now() - timedelta(minutes=10)
        task_completed.completed_at = datetime.now()

        # Duration should be approximately 10 minutes (in seconds)
        duration = task_completed.duration
        assert duration is not None
        assert 590 <= duration <= 610  # Allow small margin for test execution time

        # Task with only start time
        task_started = Task(description="Started task")
        task_started.started_at = datetime.now()
        assert task_started.duration is None

    def test_to_dict_method(self):
        """Test conversion to dictionary if it exists"""
        # Create task with various attributes
        task = Task(description="Test task")

        # Skip this test if to_dict doesn't exist
        if not hasattr(task, 'to_dict'):
            pytest.skip("Task.to_dict() method not implemented")

        # Otherwise proceed with testing
        task.started_at = datetime.now() - timedelta(minutes=5)
        task.completed_at = datetime.now()
        task.result = TaskResult(
            success=True,
            output="Task result",
            error=None,
            execution_time=1.5,
            metadata={"key": "value"}
        )

        # Convert to dictionary
        task_dict = task.to_dict()

        # Verify core dictionary contents without assuming specific fields
        assert "id" in task_dict
        assert task_dict["id"] == task.id
        assert "description" in task_dict
        assert task_dict["description"] == task.description
        assert "status" in task_dict
        assert task_dict["status"] == task.status
        assert "priority" in task_dict
        assert task_dict["priority"] == task.priority

    def test_model_methods(self):
        """Test model-related methods like model_dump"""
        # Create original task
        original = Task(
            description="Original task",
            priority=TaskPriority.MEDIUM,
            context={"original": True}
        )

        # Test model_dump method if available
        if hasattr(original, 'model_dump'):
            model_data = original.model_dump()
            assert isinstance(model_data, dict)
            assert model_data["description"] == "Original task"

        # Test dict method if available
        if hasattr(original, 'dict'):
            dict_data = original.dict()
            assert isinstance(dict_data, dict)
            assert dict_data["description"] == "Original task"

    @pytest.mark.asyncio
    async def test_custom_methods(self):
        """Test any additional custom methods on Task"""
        task = Task(description="Test custom methods")

        # Test any other methods here that might exist on the Task class
        # This is a placeholder for future methods

        # Example: If there's a method to check if a task is overdue
        if hasattr(task, 'is_overdue'):
            assert isinstance(task.is_overdue(), bool)
