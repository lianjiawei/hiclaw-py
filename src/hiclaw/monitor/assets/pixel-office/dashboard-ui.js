(function () {
  const ui = {
    metricState: document.getElementById("metricState"),
    metricTask: document.getElementById("metricTask"),
    metricTool: document.getElementById("metricTool"),
    metricLastActive: document.getElementById("metricLastActive"),
    metricChannel: document.getElementById("metricChannel"),
    activeRunsBadge: document.getElementById("activeRunsBadge"),
    runList: document.getElementById("runList"),
  };

  function setText(node, value) {
    if (node) {
      node.textContent = value;
    }
  }

  function formatStatus(state) {
    return (state || "idle").replace(/^./, (char) => char.toUpperCase());
  }

  function formatTime(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString();
  }

  function formatToolLabel(toolName) {
    const tool = String(toolName || "");
    const mapping = {
      read_workspace_file: "读文件",
      write_workspace_file: "写文件",
      edit_workspace_file: "改文件",
      glob_workspace_files: "找文件",
      grep_workspace_content: "搜内容",
      bash: "跑命令",
      web_search: "联网搜索",
      create_task: "创建任务",
      cancel_task: "取消任务",
      get_current_time: "看时间",
    };
    return mapping[tool] || tool || "无";
  }

  function buildRunListHtml(runs) {
    if (!runs.length) {
      return '<div class="run-item"><strong>Idle</strong><span>当前没有并发任务，会话角色会在办公室自由活动。</span></div>';
    }

    return runs
      .map((run) => {
        const toolText = run.current_tool ? `动作：${formatToolLabel(run.current_tool)}` : "动作：巡航中";
        return `<div class="run-item"><strong>${run.channel || "unknown"}</strong><span>${run.prompt || "暂无任务"}</span><span>${toolText}</span></div>`;
      })
      .join("");
  }

  function updateDashboardUi(snapshot) {
    const agentData = snapshot.agent || {};
    const state = agentData.state || "idle";
    const runs = Array.isArray(agentData.active_runs) ? agentData.active_runs : [];

    setText(ui.metricState, formatStatus(state));
    setText(ui.metricTask, agentData.current_task || "暂无任务");
    setText(ui.metricTool, agentData.current_tool || agentData.tool_status || "无");
    setText(ui.metricLastActive, formatTime(agentData.last_active_at));
    setText(ui.metricChannel, agentData.last_channel || "-");
    setText(ui.activeRunsBadge, `${agentData.active_runs_count || 0} active runs`);

    if (ui.runList) {
      ui.runList.innerHTML = buildRunListHtml(runs);
    }
  }

  window.PixelOfficeUI = {
    updateDashboardUi,
  };
})();
