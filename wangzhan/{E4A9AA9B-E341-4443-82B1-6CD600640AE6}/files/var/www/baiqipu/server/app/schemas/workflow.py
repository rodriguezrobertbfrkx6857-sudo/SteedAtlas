from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WorkflowNodeStateIn(BaseModel):
    node_id: str
    label: str | None = None
    type: str | None = None
    status: str = "pending"
    progress: int = Field(default=0, ge=0, le=100)
    output: dict[str, Any] = Field(default_factory=dict)


class WorkflowNodeStateOut(BaseModel):
    node_id: str
    label: str | None = None
    type: str | None = None
    status: str = "pending"
    progress: int = 0
    output: dict[str, Any] = Field(default_factory=dict)


class WorkflowTaskCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    horse_name: str | None = None
    duration: int = Field(default=30, ge=15, le=180)
    aspect_ratio: str = Field(default="9:16", min_length=1, max_length=20)
    workflow_definition: dict[str, Any] = Field(default_factory=dict)
    input_payload: dict[str, Any] = Field(default_factory=dict)
    webhook_url: str | None = None
    auto_start: bool = True


class WorkflowTaskDispatchIn(BaseModel):
    webhook_url: str | None = None


class WorkflowTaskCallbackIn(BaseModel):
    callback_token: str | None = None
    status: str | None = None
    progress: int | None = Field(default=None, ge=0, le=100)
    current_node: str | None = None
    node_id: str | None = None
    node_status: str | None = None
    node_progress: int | None = Field(default=None, ge=0, le=100)
    node_output: dict[str, Any] = Field(default_factory=dict)
    node_states: list[WorkflowNodeStateIn] = Field(default_factory=list)
    normalized_payload: dict[str, Any] = Field(default_factory=dict)
    result_payload: dict[str, Any] = Field(default_factory=dict)
    dispatch_response: dict[str, Any] = Field(default_factory=dict)
    n8n_execution_id: str | None = None
    error_message: str | None = None
    event: str | None = None


class WorkflowTaskOut(BaseModel):
    task_id: str
    title: str
    horse_name: str | None = None
    status: str
    progress: int = 0
    current_node: str | None = None
    aspect_ratio: str
    duration: int
    webhook_url: str | None = None
    callback_url: str
    callback_token: str
    n8n_execution_id: str | None = None
    workflow_definition: dict[str, Any] = Field(default_factory=dict)
    input_payload: dict[str, Any] = Field(default_factory=dict)
    normalized_payload: dict[str, Any] = Field(default_factory=dict)
    node_states: list[WorkflowNodeStateOut] = Field(default_factory=list)
    result_payload: dict[str, Any] = Field(default_factory=dict)
    dispatch_response: dict[str, Any] = Field(default_factory=dict)
    runtime_state: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    created_at: str
    updated_at: str | None = None


class WorkflowTaskDispatchOut(BaseModel):
    task: WorkflowTaskOut
    dispatch_status: str
    message: str


class WorkflowTaskListOut(BaseModel):
    items: list[WorkflowTaskOut] = Field(default_factory=list)
