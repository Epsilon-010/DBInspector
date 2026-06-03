class PipelineError(Exception):
    """Base error for pipeline failures we surface to the client."""


class UnsafeQueryError(PipelineError):
    """SQL validator rejected the LLM-generated query (write op, multi-statement, etc.)."""


class QueryExecutionError(PipelineError):
    """The database refused or failed to execute the query."""
