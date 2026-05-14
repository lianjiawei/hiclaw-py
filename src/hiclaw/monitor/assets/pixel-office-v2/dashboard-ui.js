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
    clusterStateBadge: document.getElementById("v2ClusterStateBadge"),
    eventList: document.getElementById("v2EventList"),
  };

  function setText(node, value) {
    if (node) node.textContent = value;
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function truncate(value, length = 120) {
    const text = String(value || "").replace(/\s+/g, " ").trim();
    if (text.length <= length) return text;
    return `${text.slice(0, length - 1)}...`;
  }

  function formatTime(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString();
  }

  function formatStatus(state) {
    const mapping = {
      idle: "空闲",
      working: "工作中",
      waiting: "等待中",
      offline: "离线",
      done: "已完成",
      error: "异常",
    };
    return mapping[state || "idle"] || String(state || "空闲");
  }

  function formatToolLabel(toolName) {
    const tool = String(toolName || "");
    const mapping = {
      read_workspace_file: "读取文件",
      write_workspace_file: "写入文件",
      edit_workspace_file: "编辑文件",
      glob_workspace_files: "查找文件",
      grep_workspace_content: "搜索工作区",
      bash: "执行命令",
      web_search: "联网调研",
      create_task: "创建任务",
      cancel_task: "取消任务",
      get_current_time: "查看时间",
    };
    return mapping[tool] || tool || "无";
  }

  function buildRunListHtml(runs) {
    if (!runs.length) {
      return '<div class="v2-run-item"><strong>当前没有运行任务</strong><span>正在等待下一次请求。</span></div>';
    }

    return runs
      .slice(0, 4)
      .map((run) => {
        const channel = escapeHtml(run.channel || "未知");
        const prompt = escapeHtml(truncate(run.prompt || "当前没有任务", 88));
        const toolText = escapeHtml(formatToolLabel(run.current_tool || ""));
        return `<div class="v2-run-item"><strong>${channel}</strong><span>${prompt}</span><span class="v2-item-meta">${toolText}</span></div>`;
      })
      .join("");
  }

  function buildEventListHtml(events) {
    if (!events.length) {
      return '<div class="v2-run-item timeline"><strong>当前没有协作事件</strong><span>下一次多智能体协作会显示在这里。</span></div>';
    }

    return events
      .slice(-7)
      .reverse()
      .map((event) => {
        const title = escapeHtml(truncate(event.summary || event.kind || "事件", 72));
        const meta = escapeHtml(`${event.agent_id || "system"} / ${event.kind || "event"}`);
        const detail = escapeHtml(truncate(event.detail || event.created_at || "", 104));
        return `<div class="v2-run-item timeline"><strong>${title}</strong><span class="v2-item-meta">${meta}</span><span>${detail}</span></div>`;
      })
      .join("");
  }

  function updateDashboardUi(snapshot) {
    const agentData = snapshot.agent || {};
    const cluster = snapshot.cluster || {};
    const agents = Array.isArray(snapshot.agents) ? snapshot.agents.filter((agent) => agent && agent.role !== "primary") : [];
    const state = agentData.state || "idle";
    const runs = Array.isArray(agentData.active_runs) ? agentData.active_runs : [];
    const palette = {
      idle: { color: "#7c9bff", text: "空闲", copy: "当前没有任务，办公室已准备好。" },
      working: { color: "#63e6be", text: "工作中", copy: "智能体正在工位上协同执行当前任务。" },
      waiting: { color: "#ffd166", text: "等待中", copy: "继续执行前需要新的输入或确认。" },
      offline: { color: "#7b819a", text: "离线", copy: "当前没有活跃会话连接到监控面板。" },
    }[state] || { color: "#7c9bff", text: formatStatus(state), copy: "运行状态正在更新。" };

    if (ui.stateDot) {
      ui.stateDot.style.background = palette.color;
      ui.stateDot.style.boxShadow = `0 0 14px ${palette.color}`;
    }
    setText(ui.statePill, palette.text);
    setText(ui.stateValue, formatStatus(state));
    setText(ui.stateCopy, palette.copy);
    setText(ui.task, agentData.current_task || cluster.objective || "当前没有任务");
    setText(ui.tool, formatToolLabel(agentData.current_tool || agentData.tool_status || ""));
    setText(ui.channel, agentData.last_channel || "-");
    setText(ui.lastActive, formatTime(agentData.last_active_at));
    setText(ui.activeRunsBadge, String(agentData.active_runs_count || 0));
    const clusterState = formatStatus(cluster.state || "idle");
    const clusterBadge = agents.length ? `${clusterState} / ${agents.length} 个智能体` : clusterState;
    setText(ui.clusterStateBadge, clusterBadge);

    if (ui.runList) {
      ui.runList.innerHTML = buildRunListHtml(runs);
    }
    if (ui.eventList) {
      ui.eventList.innerHTML = buildEventListHtml(Array.isArray(cluster.events) ? cluster.events : []);
    }
  }

  window.PixelOfficeV2UI = {
    updateDashboardUi,
  };
})();
