(function () {
  const ui = {
    stateDot: document.getElementById("v2StateDot"),
    statePill: document.getElementById("v2StatePill"),
    stateValue: document.getElementById("v2StateValue"),
    stateCopy: document.getElementById("v2StateCopy"),
    task: document.getElementById("v2Task"),
    tool: document.getElementById("v2Tool"),
    lastActive: document.getElementById("v2LastActive"),
    channel: document.getElementById("v2Channel"),
    activeRunsBadge: document.getElementById("v2ActiveRunsBadge"),
    runList: document.getElementById("v2RunList"),
    clusterAgentsBadge: document.getElementById("v2ClusterAgentsBadge"),
    clusterStateBadge: document.getElementById("v2ClusterStateBadge"),
    agentList: document.getElementById("v2AgentList"),
    eventList: document.getElementById("v2EventList"),
  };

  function setText(node, value) {
    if (node) node.textContent = value;
  }

  function formatTime(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString();
  }

  function formatStatus(state) {
    return (state || "idle").replace(/^./, (char) => char.toUpperCase());
  }

  function formatToolLabel(toolName) {
    const tool = String(toolName || "");
    const mapping = {
      read_workspace_file: "Reading files",
      write_workspace_file: "Writing files",
      edit_workspace_file: "Editing files",
      glob_workspace_files: "Finding files",
      grep_workspace_content: "Searching workspace",
      bash: "Running commands",
      web_search: "Web research",
      create_task: "Creating task",
      cancel_task: "Cancelling task",
      get_current_time: "Checking time",
    };
    return mapping[tool] || tool || "None";
  }

  function buildRunListHtml(runs) {
    if (!runs.length) {
      return '<div class="v2-run-item"><strong>Office idle</strong><span>No concurrent runs. The office is in low-noise standby mode.</span></div>';
    }

    return runs
      .map((run) => {
        const toolText = run.current_tool ? formatToolLabel(run.current_tool) : "Idle cruise";
        return `<div class="v2-run-item"><strong>${run.channel || "unknown"}</strong><span>${run.prompt || "No task"}</span><span>${toolText}</span></div>`;
      })
      .join("");
  }

  function buildAgentListHtml(agents) {
    if (!agents.length) {
      return '<div class="v2-run-item"><strong>No cluster agents</strong><span>Cluster mode is idle or disabled.</span></div>';
    }

    return agents
      .map((agent) => `<div class="v2-run-item"><strong>${agent.name || agent.agent_id}</strong><span>${agent.role || "agent"} · ${agent.status || "idle"}</span><span>${agent.summary || "No summary"}</span></div>`)
      .join("");
  }

  function buildEventListHtml(events) {
    if (!events.length) {
      return '<div class="v2-run-item"><strong>No collaboration events</strong><span>The cluster timeline will appear here.</span></div>';
    }

    return events
      .slice(-8)
      .reverse()
      .map((event) => `<div class="v2-run-item"><strong>${event.summary || event.kind || "event"}</strong><span>${event.agent_id || "system"}</span><span>${event.detail || event.created_at || ""}</span></div>`)
      .join("");
  }

  function updateDashboardUi(snapshot) {
    const agentData = snapshot.agent || {};
    const cluster = snapshot.cluster || {};
    const agents = Array.isArray(snapshot.agents) ? snapshot.agents.filter((agent) => agent && agent.role !== "primary") : [];
    const state = agentData.state || "idle";
    const runs = Array.isArray(agentData.active_runs) ? agentData.active_runs : [];
    const palette = {
      idle: { color: "#7c9bff", text: "IDLE", copy: "办公室当前处于低噪声巡航状态。" },
      working: { color: "#63e6be", text: "WORKING", copy: "Agent 已回到工位，正在执行任务。" },
      waiting: { color: "#ffd166", text: "WAITING", copy: "当前需要你的确认或补充输入。" },
      offline: { color: "#7b819a", text: "OFFLINE", copy: "当前没有活跃会话。" },
    }[state] || { color: "#7c9bff", text: formatStatus(state), copy: "办公室状态正在更新。" };

    if (ui.stateDot) {
      ui.stateDot.style.background = palette.color;
      ui.stateDot.style.boxShadow = `0 0 16px ${palette.color}`;
    }
    setText(ui.statePill, palette.text);
    setText(ui.stateValue, formatStatus(state));
    setText(ui.stateCopy, palette.copy);
    setText(ui.task, agentData.current_task || "No active task");
    setText(ui.tool, formatToolLabel(agentData.current_tool || agentData.tool_status || ""));
    setText(ui.channel, agentData.last_channel || "-");
    setText(ui.lastActive, formatTime(agentData.last_active_at));
    setText(ui.activeRunsBadge, String(agentData.active_runs_count || 0));
    setText(ui.clusterAgentsBadge, String(agents.length || 0));
    setText(ui.clusterStateBadge, String(cluster.state || "idle").toUpperCase());

    if (ui.runList) {
      ui.runList.innerHTML = buildRunListHtml(runs);
    }
    if (ui.agentList) {
      ui.agentList.innerHTML = buildAgentListHtml(agents);
    }
    if (ui.eventList) {
      ui.eventList.innerHTML = buildEventListHtml(Array.isArray(cluster.events) ? cluster.events : []);
    }
  }

  window.PixelOfficeV2UI = {
    updateDashboardUi,
  };
})();
