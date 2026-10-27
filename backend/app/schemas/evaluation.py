import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvaluationCaseCreate(BaseModel):
    question: str = Field(min_length=3, max_length=20_000)
    reference_answer: str = Field(min_length=1, max_length=40_000)
    reference_document_ids: list[uuid.UUID] = Field(default_factory=list)


class EvaluationCaseRead(EvaluationCaseCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: Literal["manual", "synthetic"]
    created_at: datetime


class SyntheticCaseRequest(BaseModel):
    count: int = Field(default=5, ge=1, le=25)


class EvaluationConfiguration(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    retrieval_mode: Literal["hybrid", "dense"] = "hybrid"
    use_reranker: bool = False
    top_k: int | None = Field(default=None, ge=1, le=100)


class EvaluationRunRequest(BaseModel):
    name: str = Field(default="RAG configuration comparison", min_length=1, max_length=160)
    configurations: list[EvaluationConfiguration] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def default_configurations(self) -> "EvaluationRunRequest":
        if not self.configurations:
            self.configurations = [
                EvaluationConfiguration(name="hybrid", retrieval_mode="hybrid"),
                EvaluationConfiguration(name="dense", retrieval_mode="dense"),
                EvaluationConfiguration(
                    name="hybrid + reranker", retrieval_mode="hybrid", use_reranker=True
                ),
                EvaluationConfiguration(
                    name="dense + reranker", retrieval_mode="dense", use_reranker=True
                ),
            ]
        names = [item.name for item in self.configurations]
        if len(names) != len(set(names)):
            raise ValueError("Configuration names must be unique")
        return self


class EvaluationResult(BaseModel):
    configuration: EvaluationConfiguration
    sample_count: int
    retrieval_labeled_count: int
    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    hit_rate_at_k: float | None = None
    mrr: float | None = None
    error: str | None = None


class EvaluationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    status: str
    configurations: list[EvaluationConfiguration]
    results: list[EvaluationResult]
    markdown_report: str
    created_at: datetime
