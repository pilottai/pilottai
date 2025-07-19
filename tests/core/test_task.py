import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from pilottai.config.model import JobResult
from pilottai.job.job import Job
from pilottai.enums.job_e import JobStatus, JobPriority


class TestJob:
    def test_initialization(self):
        """Test basic initialization of Job with default and custom values"""
        # Test with minimal parameters
        job = Job(description="Test job")
        assert job.description == "Test job"
        assert job.status == JobStatus.PENDING
        assert job.priority == JobPriority.MEDIUM
        assert job.context == {}
        assert job.deadline is None
        assert job.agent_id is None
        assert job.created_at is not None
        assert job.started_at is None
        assert job.completed_at is None
        assert job.result is None
        assert job.id is not None  # Should have auto-generated ID

        # Test with custom parameters
        custom_context = {"key": "value"}
        custom_deadline = datetime.now() + timedelta(hours=1)
        job = Job(
            description="Custom job",
            status=JobStatus.IN_PROGRESS,
            priority=JobPriority.HIGH,
            context=custom_context,
            deadline=custom_deadline,
            agent_id="test_agent"
        )

        assert job.description == "Custom job"
        assert job.status == JobStatus.IN_PROGRESS
        assert job.priority == JobPriority.HIGH
        assert job.context == custom_context
        assert job.deadline == custom_deadline
        assert job.agent_id == "test_agent"

    @pytest.mark.asyncio
    async def test_mark_started(self):
        """Test marking a job as started"""
        job = Job(description="Test job")
        assert job.status == JobStatus.PENDING
        assert job.started_at is None

        # Mark as started
        await job.mark_started(agent_id="test_agent")

        assert job.status == JobStatus.IN_PROGRESS
        assert job.agent_id == "test_agent"
        assert job.started_at is not None

        # Test trying to start a non-pending job
        job = Job(description="Already started", status=JobStatus.IN_PROGRESS)
        with pytest.raises(ValueError):
            await job.mark_started(agent_id="test_agent")

    @pytest.mark.asyncio
    async def test_mark_completed_success(self):
        """Test marking a job as completed successfully"""
        job = Job(description="Test job", status=JobStatus.IN_PROGRESS)

        # Create successful result
        result = JobResult(
            success=True,
            output="Job completed successfully",
            error=None,
            execution_time=1.5,
            metadata={"key": "value"}
        )

        # Mark as completed
        await job.mark_completed(result)

        assert job.status == JobStatus.COMPLETED
        assert job.completed_at is not None
        assert job.result == result
        assert job.result.success is True

    @pytest.mark.asyncio
    async def test_mark_completed_failure(self):
        """Test marking a job as failed"""
        job = Job(description="Test job", status=JobStatus.IN_PROGRESS)

        # Create failure result
        result = JobResult(
            success=False,
            output=None,
            error="Test error",
            execution_time=0.5,
            metadata={}
        )

        # Mark as completed with failure
        await job.mark_completed(result)

        assert job.status == JobStatus.FAILED
        assert job.completed_at is not None
        assert job.result == result
        assert job.result.success is False
        assert job.result.error == "Test error"

    @pytest.mark.asyncio
    async def test_mark_cancelled(self):
        """Test marking a job as cancelled"""
        job = Job(description="Test job", status=JobStatus.IN_PROGRESS)
        job.started_at = datetime.now() - timedelta(minutes=5)

        # Mark as cancelled
        await job.mark_cancelled(reason="User cancelled")

        assert job.status == JobStatus.CANCELLED
        assert job.completed_at is not None
        assert job.result is not None
        assert job.result.success is False
        assert "User cancelled" in job.result.error

    def test_is_completed_property(self):
        """Test is_completed property"""
        # Test with various statuses
        completed_job = Job(description="Completed", status=JobStatus.COMPLETED)
        failed_job = Job(description="Failed", status=JobStatus.FAILED)
        cancelled_job = Job(description="Cancelled", status=JobStatus.CANCELLED)
        pending_job = Job(description="Pending", status=JobStatus.PENDING)
        in_progress_job = Job(description="In Progress", status=JobStatus.IN_PROGRESS)

        # Check completion status
        assert completed_job.is_completed is True
        assert failed_job.is_completed is True
        assert cancelled_job.is_completed is True
        assert pending_job.is_completed is False
        assert in_progress_job.is_completed is False

    def test_is_active_property(self):
        """Test is_active property"""
        # Test with various statuses
        in_progress_job = Job(description="In Progress", status=JobStatus.IN_PROGRESS)
        pending_job = Job(description="Pending", status=JobStatus.PENDING)
        completed_job = Job(description="Completed", status=JobStatus.COMPLETED)

        # Check active status
        assert in_progress_job.is_active is True
        assert pending_job.is_active is False
        assert completed_job.is_active is False

    def test_is_expired_property(self):
        """Test is_expired property"""
        # Job with no deadline
        job_no_deadline = Job(description="No deadline")
        assert job_no_deadline.is_expired is False

        # Job with future deadline
        future_deadline = datetime.now() + timedelta(hours=1)
        job_future = Job(description="Future deadline", deadline=future_deadline)
        assert job_future.is_expired is False

        # Job with past deadline
        past_deadline = datetime.now() - timedelta(hours=1)
        job_past = Job(description="Past deadline", deadline=past_deadline)
        assert job_past.is_expired is True

    def test_duration_property(self):
        """Test duration property calculation"""
        # Job with no timing information
        job_no_timing = Job(description="No timing")
        assert job_no_timing.duration is None

        # Job with start and completion
        job_completed = Job(description="Completed job")
        job_completed.started_at = datetime.now() - timedelta(minutes=10)
        job_completed.completed_at = datetime.now()

        # Duration should be approximately 10 minutes (in seconds)
        duration = job_completed.duration
        assert duration is not None
        assert 590 <= duration <= 610  # Allow small margin for test execution time

        # Job with only start time
        job_started = Job(description="Started job")
        job_started.started_at = datetime.now()
        assert job_started.duration is None

    def test_to_dict_method(self):
        """Test conversion to dictionary if it exists"""
        # Create job with various attributes
        job = Job(description="Test job")

        # Skip this test if to_dict doesn't exist
        if not hasattr(job, 'to_dict'):
            pytest.skip("Job.to_dict() method not implemented")

        # Otherwise proceed with testing
        job.started_at = datetime.now() - timedelta(minutes=5)
        job.completed_at = datetime.now()
        job.result = JobResult(
            success=True,
            output="Job result",
            error=None,
            execution_time=1.5,
            metadata={"key": "value"}
        )

        # Convert to dictionary
        job_dict = job.to_dict()

        # Verify core dictionary contents without assuming specific fields
        assert "id" in job_dict
        assert job_dict["id"] == job.id
        assert "description" in job_dict
        assert job_dict["description"] == job.description
        assert "status" in job_dict
        assert job_dict["status"] == job.status
        assert "priority" in job_dict
        assert job_dict["priority"] == job.priority

    def test_model_methods(self):
        """Test model-related methods like model_dump"""
        # Create original job
        original = Job(
            description="Original job",
            priority=JobPriority.MEDIUM,
            context={"original": True}
        )

        # Test model_dump method if available
        if hasattr(original, 'model_dump'):
            model_data = original.model_dump()
            assert isinstance(model_data, dict)
            assert model_data["description"] == "Original job"

        # Test dict method if available
        if hasattr(original, 'dict'):
            dict_data = original.dict()
            assert isinstance(dict_data, dict)
            assert dict_data["description"] == "Original job"

    @pytest.mark.asyncio
    async def test_custom_methods(self):
        """Test any additional custom methods on Job"""
        job = Job(description="Test custom methods")

        # Test any other methods here that might exist on the Job class
        # This is a placeholder for future methods

        # Example: If there's a method to check if a job is overdue
        if hasattr(job, 'is_overdue'):
            assert isinstance(job.is_overdue(), bool)
