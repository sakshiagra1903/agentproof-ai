from pydantic import BaseModel, Field, ConfigDict
from typing import Any

class TestCase(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=5000)
    expected_answer: str = Field(min_length=1, max_length=10000)
    reference_context: str = Field(default='', max_length=20000)
    expected_keywords: list[str] = Field(default_factory=list)
    expected_citations: list[str] = Field(default_factory=list)
    actual_answer: str | None = Field(default=None, max_length=20000)
    actual_citations: list[str] = Field(default_factory=list)
    source_documents: list[dict[str, str]] = Field(default_factory=list, description='Source records with id and optional text/title')
    expected_tool_calls: list[str] = Field(default_factory=list)
    actual_tool_calls: list[str] = Field(default_factory=list)

class DatasetImport(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=2000)
    cases: list[TestCase] = Field(min_length=1, max_length=1000)

class EvaluationRequest(BaseModel):
    dataset_id: int | None = None
    dataset_name: str | None = None
    cases: list[TestCase] | None = None
    pass_threshold: float = Field(default=0.65, ge=0, le=1)
    actual_answers: dict[str, str] = Field(default_factory=dict)

class CompareResponse(BaseModel):
    baseline_id: int
    candidate_id: int
    score_delta: float | None
    pass_rate_delta: float | None
    newly_failing: list[str]
    newly_passing: list[str]
    common_case_score_changes: list[dict[str, Any]]


class TraceSpan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    span_id: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_.:-]+$')
    parent_span_id: str | None = Field(default=None, max_length=128, pattern=r'^[A-Za-z0-9_.:-]+$')
    name: str = Field(min_length=1, max_length=200)
    kind: str = Field(default='internal', pattern='^(llm|tool|retrieval|chain|internal)$')
    status: str = Field(default='ok', pattern='^(ok|error|unset)$')
    started_at: str | None = Field(default=None, max_length=64)
    ended_at: str | None = Field(default=None, max_length=64)
    input: Any = None
    output: Any = None
    error: str | None = Field(default=None, max_length=5000)
    attributes: dict[str, Any] = Field(default_factory=dict)

class TraceIngest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    trace_id: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_.:-]+$')
    name: str = Field(default='agent-execution', max_length=200)
    session_id: str | None = Field(default=None, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)
    spans: list[TraceSpan] = Field(min_length=1, max_length=500)
