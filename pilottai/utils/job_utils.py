from typing import Union, List, Any, Dict, Optional
from datetime import datetime

from pilottai.config.model import JobResult
from pilottai.job.job import Job


class JobUtility:
    """
    Utility class for working with job, providing helper methods
    for job conversion, validation, and common operations.
    """

    @staticmethod
    def to_job(job_input: Union[str, Dict, Job]) -> Job:
        """
        Convert a string, dictionary, or Job object to a Job instance.

        Args:
            job_input: A string (treated as description), dictionary, or Job object

        Returns:
            BaseJob: A properly instantiated Job object

        Raises:
            ValueError: If the input cannot be converted to a Job
        """
        if isinstance(job_input, Job):
            return job_input

        elif isinstance(job_input, str):
            return Job(description=job_input)

        elif isinstance(job_input, dict):
            # Ensure the dictionary has at least a description
            if "description" not in job_input:
                raise ValueError("Job dictionary must contain a 'description' field")

            return Job(**job_input)

        else:
            raise ValueError(
                f"Cannot convert {type(job_input)} to Job. Must be a string, dictionary, or Job object.")

    @staticmethod
    def to_job_list(job_inputs: Union[str, Dict, Job, List[str], List[Dict], List[Job]]) -> List[Job]:
        """
        Convert various input formats to a list of Job objects.

        Args:
            job_inputs: A single job or list of job in various formats

        Returns:
            List[BaseJob]: A list of properly instantiated Job objects
        """
        # Handle single items
        if isinstance(job_inputs, (str, dict, Job)):
            return [JobUtility.to_job(job_inputs)]

        # Handle lists
        elif isinstance(job_inputs, list):
            jobs = []
            for item in job_inputs:
                jobs.append(JobUtility.to_job(item))
            return jobs

        else:
            raise ValueError(f"Cannot convert {type(job_inputs)} to a list of Jobs")

    @staticmethod
    def is_job_object(job_input: Any) -> bool:
        """
        Check if the input is a Job object.

        Args:
            job_input: Any input to check

        Returns:
            bool: True if the input is a Job object, False otherwise
        """
        return isinstance(job_input, Job)

    @staticmethod
    def get_job_type(job_input: Any) -> str:
        """
        Get the type of the job input.

        Args:
            job_input: Any input to check

        Returns:
            str: The type of the job input ('job', 'str', 'dict', or 'unknown')
        """
        if isinstance(job_input, Job):
            return 'job'
        elif isinstance(job_input, str):
            return 'str'
        elif isinstance(job_input, dict):
            return 'dict'
        else:
            return 'unknown'

    @staticmethod
    def create_empty_result(job: Job, error: Optional[str] = None) -> JobResult:
        """
        Create an empty (failed) result for a job.

        Args:
            job: The job for which to create a result
            error: Optional error message

        Returns:
            JobResult: A failed job result
        """
        return JobResult(
            success=False,
            output=None,
            error=error or "Job execution failed",
            execution_time=0.0,
            metadata={
                "job_id": job.id,
                "created_at": datetime.now().isoformat()
            }
        )

    @staticmethod
    def merge_job_results(results: List[JobResult]) -> JobResult:
        """
        Merge multiple job results into a single result.

        Args:
            results: List of job results to merge

        Returns:
            JobResult: A consolidated job result
        """
        if not results:
            return JobResult(
                success=True,
                output="No job executed",
                error=None,
                execution_time=0.0
            )

        # Calculate overall success and total execution time
        overall_success = all(result.success for result in results)
        total_execution_time = sum(result.execution_time for result in results)

        # Combine outputs and errors
        outputs = []
        errors = []

        for i, result in enumerate(results):
            if result.output:
                outputs.append(f"Job {i + 1} output: {result.output}")
            if result.error:
                errors.append(f"Job {i + 1} error: {result.error}")

        combined_output = "\n".join(outputs) if outputs else None
        combined_error = "\n".join(errors) if errors else None

        return JobResult(
            success=overall_success,
            output=combined_output,
            error=combined_error,
            execution_time=total_execution_time,
            metadata={
                "result_count": len(results),
                "success_count": sum(1 for r in results if r.success),
                "fail_count": sum(1 for r in results if not r.success)
            }
        )
