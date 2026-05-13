from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ClusterAgentRole = Literal["planner", "executor", "reviewer"]
ClusterRunState = Literal["queued", "working", "waiting", "done", "error"]
ClusterTaskState = Literal["queued", "in_progress", "waiting", "done", "error"]
ClusterEventKind = Literal[
    "cluster_started",
    "task_dispatched",
    "agent_started",
    "agent_note",
    "agent_finished",
    "cluster_finished",
]


@dataclass(frozen=True, slots=True)
class ClusterAgent:
    agent_id: str
    role: ClusterAgentRole
    name: str
    objective: str


@dataclass(frozen=True, slots=True)
class ClusterEvent:
    kind: ClusterEventKind
    agent_id: str
    summary: str
    detail: str = ""


@dataclass(frozen=True, slots=True)
class ClusterBlueprint:
    cluster_id: str
    mode: str
    objective: str
    agents: tuple[ClusterAgent, ...] = field(default_factory=tuple)
    planned_steps: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ClusterTask:
    task_id: str
    cluster_id: str
    title: str
    assigned_agent: str
    state: ClusterTaskState = "queued"
    depends_on: tuple[str, ...] = ()
    input_payload: str = ""
    output_payload: str = ""


@dataclass(frozen=True, slots=True)
class ClusterMessage:
    message_id: str
    cluster_id: str
    from_agent: str
    to_agent: str
    kind: str
    content: str


@dataclass(frozen=True, slots=True)
class ClusterRun:
    cluster_id: str
    session_scope: str
    conversation_key: str
    channel: str
    objective: str
    state: ClusterRunState = "queued"
    mode: str = "collaborative"
    agents: tuple[ClusterAgent, ...] = field(default_factory=tuple)
    tasks: tuple[ClusterTask, ...] = field(default_factory=tuple)
    messages: tuple[ClusterMessage, ...] = field(default_factory=tuple)
