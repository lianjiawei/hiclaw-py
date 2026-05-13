from __future__ import annotations

import json
from datetime import datetime
from threading import Lock
from typing import Any
from uuid import uuid4

from hiclaw.config import AGENT_CLUSTER_MAX_EVENTS, CLUSTER_RUNTIME_FILE
from hiclaw.core.types import ConversationRef

from .models import ClusterAgent, ClusterBlueprint

_STORE_LOCK = Lock()

DEFAULT_CLUSTER_RUNTIME_STATE: dict[str, Any] = {
    "runs": {},
    "run_order": [],
}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _compact(text: str | None, limit: int = 220) -> str:
    if not text:
        return ""
    normalized = " ".join(str(text).split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def _ensure_store_file() -> None:
    CLUSTER_RUNTIME_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not CLUSTER_RUNTIME_FILE.exists():
        CLUSTER_RUNTIME_FILE.write_text(json.dumps(DEFAULT_CLUSTER_RUNTIME_STATE, ensure_ascii=False, indent=2), encoding="utf-8")


def load_cluster_runtime_state() -> dict[str, Any]:
    _ensure_store_file()
    with _STORE_LOCK:
        try:
            raw = json.loads(CLUSTER_RUNTIME_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
        state = json.loads(json.dumps(DEFAULT_CLUSTER_RUNTIME_STATE, ensure_ascii=False))
        state["runs"] = dict(raw.get("runs") or {})
        state["run_order"] = list(raw.get("run_order") or [])
        return state


def save_cluster_runtime_state(state: dict[str, Any]) -> None:
    _ensure_store_file()
    payload = {
        "runs": dict(state.get("runs") or {}),
        "run_order": list(state.get("run_order") or []),
    }
    with _STORE_LOCK:
        CLUSTER_RUNTIME_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _update_state(mutator) -> dict[str, Any]:
    state = load_cluster_runtime_state()
    mutator(state)
    save_cluster_runtime_state(state)
    return state


def _build_agent_entries(agents: tuple[ClusterAgent, ...]) -> dict[str, Any]:
    now = _now_iso()
    return {
        agent.agent_id: {
            "agent_id": agent.agent_id,
            "name": agent.name,
            "role": agent.role,
            "status": "queued",
            "summary": _compact(agent.objective, 180),
            "updated_at": now,
        }
        for agent in agents
    }


def _build_task_entries(blueprint: ClusterBlueprint) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for index, step in enumerate(blueprint.planned_steps, start=1):
        assigned_agent = "planner" if index == 1 else "executor"
        if index == len(blueprint.planned_steps) and any(agent.role == "reviewer" for agent in blueprint.agents):
            assigned_agent = "reviewer"
        tasks.append(
            {
                "task_id": f"{blueprint.cluster_id}:task:{index}",
                "cluster_id": blueprint.cluster_id,
                "title": step,
                "assigned_agent": assigned_agent,
                "state": "queued",
                "depends_on": [tasks[-1]["task_id"]] if tasks else [],
                "input_payload": "",
                "output_payload": "",
            }
        )
    return tasks


def _append_message(run: dict[str, Any], *, from_agent: str, to_agent: str, kind: str, content: str) -> None:
    messages = list(run.get("messages") or [])
    messages.append(
        {
            "message_id": uuid4().hex,
            "cluster_id": run.get("cluster_id") or "",
            "from_agent": from_agent,
            "to_agent": to_agent,
            "kind": kind,
            "content": _compact(content, 220),
            "created_at": _now_iso(),
        }
    )
    run["messages"] = messages[-AGENT_CLUSTER_MAX_EVENTS:]


def _append_event(run: dict[str, Any], *, kind: str, agent_id: str, summary: str, detail: str = "") -> None:
    events = list(run.get("events") or [])
    events.append(
        {
            "cluster_id": run.get("cluster_id") or "",
            "kind": kind,
            "agent_id": agent_id,
            "summary": _compact(summary, 120),
            "detail": _compact(detail, 220),
            "created_at": _now_iso(),
        }
    )
    run["events"] = events[-AGENT_CLUSTER_MAX_EVENTS:]
    run["last_event_at"] = _now_iso()


def _set_agent_status(run: dict[str, Any], agent_id: str, *, status: str, summary: str = "") -> None:
    agents = dict(run.get("agents") or {})
    current = dict(agents.get(agent_id) or {})
    if not current:
        current = {
            "agent_id": agent_id,
            "name": agent_id.title(),
            "role": agent_id,
        }
    current.update(
        {
            "status": status,
            "summary": _compact(summary, 180),
            "updated_at": _now_iso(),
        }
    )
    agents[agent_id] = current
    run["agents"] = agents


def _set_task_state(run: dict[str, Any], assigned_agent: str, state: str, output_payload: str = "") -> None:
    tasks = list(run.get("tasks") or [])
    updated = False
    for task in tasks:
        if task.get("assigned_agent") == assigned_agent and task.get("state") in {"queued", "in_progress", "waiting"}:
            task["state"] = state
            if output_payload:
                task["output_payload"] = _compact(output_payload, 220)
            updated = True
            if state != "done":
                break
    if updated:
        run["tasks"] = tasks


def start_cluster_run(conversation: ConversationRef, blueprint: ClusterBlueprint) -> None:
    now = _now_iso()

    def mutator(state: dict[str, Any]) -> None:
        runs = dict(state.get("runs") or {})
        run = {
            "cluster_id": blueprint.cluster_id,
            "session_scope": conversation.session_scope,
            "conversation_key": conversation.conversation_key,
            "channel": conversation.channel,
            "objective": _compact(blueprint.objective, 180),
            "mode": blueprint.mode,
            "state": "working",
            "agents": _build_agent_entries(blueprint.agents),
            "tasks": _build_task_entries(blueprint),
            "messages": [],
            "events": [],
            "planned_steps": list(blueprint.planned_steps),
            "active_agents": [agent.agent_id for agent in blueprint.agents],
            "created_at": now,
            "updated_at": now,
            "last_event_at": now,
        }
        runs[blueprint.cluster_id] = run
        order = [item for item in state.get("run_order") or [] if item != blueprint.cluster_id]
        order.append(blueprint.cluster_id)
        state["runs"] = runs
        state["run_order"] = order[-200:]

    _update_state(mutator)


def record_cluster_event(cluster_id: str, *, kind: str, agent_id: str, summary: str, detail: str = "") -> None:
    def mutator(state: dict[str, Any]) -> None:
        runs = dict(state.get("runs") or {})
        run = dict(runs.get(cluster_id) or {})
        if not run:
            return
        _append_event(run, kind=kind, agent_id=agent_id, summary=summary, detail=detail)
        run["updated_at"] = _now_iso()
        runs[cluster_id] = run
        state["runs"] = runs

    _update_state(mutator)


def mark_cluster_agent_started(cluster_id: str, agent_id: str, summary: str) -> None:
    def mutator(state: dict[str, Any]) -> None:
        runs = dict(state.get("runs") or {})
        run = dict(runs.get(cluster_id) or {})
        if not run:
            return
        _set_agent_status(run, agent_id, status="working", summary=summary)
        _set_task_state(run, agent_id, "in_progress")
        _append_event(run, kind="agent_started", agent_id=agent_id, summary=summary)
        run["updated_at"] = _now_iso()
        runs[cluster_id] = run
        state["runs"] = runs

    _update_state(mutator)


def mark_cluster_agent_waiting(cluster_id: str, agent_id: str, waiting_text: str) -> None:
    def mutator(state: dict[str, Any]) -> None:
        runs = dict(state.get("runs") or {})
        run = dict(runs.get(cluster_id) or {})
        if not run:
            return
        run["state"] = "waiting"
        _set_agent_status(run, agent_id, status="waiting", summary=waiting_text)
        _set_task_state(run, agent_id, "waiting", output_payload=waiting_text)
        _append_event(run, kind="agent_note", agent_id=agent_id, summary="Agent waiting", detail=waiting_text)
        _append_message(run, from_agent=agent_id, to_agent="user", kind="waiting", content=waiting_text)
        run["updated_at"] = _now_iso()
        runs[cluster_id] = run
        state["runs"] = runs

    _update_state(mutator)


def mark_cluster_agent_finished(cluster_id: str, agent_id: str, summary: str, *, message_kind: str = "result") -> None:
    def mutator(state: dict[str, Any]) -> None:
        runs = dict(state.get("runs") or {})
        run = dict(runs.get(cluster_id) or {})
        if not run:
            return
        _set_agent_status(run, agent_id, status="done", summary=summary)
        _set_task_state(run, agent_id, "done", output_payload=summary)
        _append_event(run, kind="agent_finished", agent_id=agent_id, summary=summary)
        _append_message(run, from_agent=agent_id, to_agent="cluster", kind=message_kind, content=summary)
        run["state"] = "working"
        run["updated_at"] = _now_iso()
        runs[cluster_id] = run
        state["runs"] = runs

    _update_state(mutator)


def finish_cluster_run(cluster_id: str, success: bool, summary: str) -> None:
    def mutator(state: dict[str, Any]) -> None:
        runs = dict(state.get("runs") or {})
        run = dict(runs.get(cluster_id) or {})
        if not run:
            return
        run["state"] = "done" if success else "error"
        _append_event(
            run,
            kind="cluster_finished",
            agent_id="planner",
            summary="Cluster finished" if success else "Cluster failed",
            detail=summary,
        )
        _append_message(run, from_agent="cluster", to_agent="user", kind="final", content=summary)
        run["updated_at"] = _now_iso()
        runs[cluster_id] = run
        state["runs"] = runs

    _update_state(mutator)


def _select_dashboard_run(state: dict[str, Any]) -> dict[str, Any] | None:
    runs = dict(state.get("runs") or {})
    if not runs:
        return None
    order = list(state.get("run_order") or [])
    ordered_runs = [runs[item] for item in order if item in runs]
    active = [run for run in ordered_runs if str(run.get("state") or "") in {"queued", "working", "waiting"}]
    if active:
        return active[-1]
    return ordered_runs[-1] if ordered_runs else None


def build_cluster_projection() -> dict[str, Any]:
    state = load_cluster_runtime_state()
    run = _select_dashboard_run(state)
    if run is None:
        return {
            "agents": [],
            "cluster": {
                "enabled": False,
                "cluster_id": "",
                "state": "idle",
                "objective": "",
                "active_agents": [],
                "planned_steps": [],
                "events": [],
                "last_event_at": "",
                "updated_at": "",
                "messages": [],
                "tasks": [],
            },
        }
    return {
        "agents": list((run.get("agents") or {}).values()),
        "cluster": {
            "enabled": True,
            "cluster_id": str(run.get("cluster_id") or ""),
            "state": str(run.get("state") or "idle"),
            "objective": str(run.get("objective") or ""),
            "active_agents": list(run.get("active_agents") or []),
            "planned_steps": list(run.get("planned_steps") or []),
            "events": list(run.get("events") or []),
            "last_event_at": str(run.get("last_event_at") or ""),
            "updated_at": str(run.get("updated_at") or ""),
            "messages": list(run.get("messages") or []),
            "tasks": list(run.get("tasks") or []),
        },
    }
