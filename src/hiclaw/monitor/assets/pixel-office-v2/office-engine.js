(function () {
  const canvas = document.getElementById("officeCanvasV2");
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;

  const scene = {
    width: canvas.width,
    height: canvas.height,
    floorTop: 220,
    walkMinX: 120,
    walkMaxX: 1120,
    corridorY: 426,
    occupancy: [null, null, null, null],
    seats: [
      { x: 760, y: 360 },
      { x: 470, y: 360 },
      { x: 630, y: 528 },
      { x: 930, y: 520 },
    ],
  };
  const clusterZones = {
    planner: { seatIndex: 1, idle: { x: 446, y: 446 }, waiting: { x: 396, y: 520 } },
    executor: { seatIndex: 0, idle: { x: 748, y: 446 }, waiting: { x: 714, y: 522 } },
    reviewer: { seatIndex: 2, idle: { x: 630, y: 572 }, waiting: { x: 576, y: 548 } },
  };

  const agents = new Map();
  const palette = [
    { body: "#7c9bff", glow: "rgba(124,155,255,0.22)", hair: "#223055" },
    { body: "#63e6be", glow: "rgba(99,230,190,0.2)", hair: "#173840" },
    { body: "#ff9ec2", glow: "rgba(255,158,194,0.18)", hair: "#4f2442" },
    { body: "#ffd166", glow: "rgba(255,209,102,0.18)", hair: "#4f3a18" },
  ];

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function fill(x, y, w, h, color) {
    ctx.fillStyle = color;
    ctx.fillRect(Math.round(x), Math.round(y), w, h);
  }

  function ensureAgent(id, index = 0) {
    if (agents.has(id)) return agents.get(id);
    const role = palette[index % palette.length];
    const agent = {
      id,
      x: 220 + index * 40,
      y: 520,
      targetX: 220 + index * 40,
      targetY: 520,
      state: "idle",
      action: "idle",
      direction: 1,
      label: id,
      channel: "",
      currentTool: "",
      task: "",
      seatIndex: index % scene.seats.length,
      bob: 0,
      pulse: 0,
      wanderCooldown: 0,
      helper: false,
      route: [],
      routeIndex: 0,
      skin: role,
      role: "primary",
      bubbleText: "",
      bubbleCooldown: 0,
      eventKind: "",
      eventSummary: "",
    };
    agents.set(id, agent);
    return agent;
  }

  function classifyAction(state, toolName) {
    if (state === "waiting") return "waiting";
    if (state !== "working") return "idle";
    const tool = String(toolName || "").toLowerCase();
    if (tool.includes("read") || tool.includes("grep") || tool.includes("glob")) return "reading";
    if (tool.includes("write") || tool.includes("edit")) return "writing";
    if (tool.includes("bash")) return "running";
    if (tool.includes("search")) return "researching";
    return "working";
  }

  function chooseSeat(index, preferred = 0) {
    const occupied = new Set();
    scene.occupancy.forEach((value) => {
      if (typeof value === "number") occupied.add(value);
    });

    for (let offset = 0; offset < scene.seats.length; offset += 1) {
      const seatIndex = (preferred + offset) % scene.seats.length;
      if (!occupied.has(seatIndex)) {
        return seatIndex;
      }
    }
    return index % scene.seats.length;
  }

  function assignRoute(agent, x, y) {
    agent.route = [
      { x: clamp(agent.x, scene.walkMinX, scene.walkMaxX), y: scene.corridorY },
      { x: clamp(x, scene.walkMinX, scene.walkMaxX), y: scene.corridorY },
      { x, y },
    ];
    agent.routeIndex = 0;
  }

  function mapClusterStatus(status) {
    const value = String(status || "idle").toLowerCase();
    if (value === "working") return "working";
    if (value === "waiting") return "waiting";
    if (value === "queued") return "working";
    if (value === "done") return "idle";
    if (value === "error") return "waiting";
    return "idle";
  }

  function actionForClusterAgent(role, status, summary) {
    if (status === "waiting") return "waiting";
    const text = `${role} ${summary || ""}`.toLowerCase();
    if (text.includes("read") || text.includes("分析") || text.includes("检查")) return "reading";
    if (text.includes("write") || text.includes("修改") || text.includes("执行")) return "writing";
    if (text.includes("search") || text.includes("调研")) return "researching";
    if (role === "planner") return "reading";
    if (role === "reviewer") return "researching";
    return status === "working" ? "working" : "idle";
  }

  function skinForRole(role, index) {
    if (role === "planner") {
      return { body: "#8ea3ff", glow: "rgba(142,163,255,0.24)", hair: "#24345f" };
    }
    if (role === "executor") {
      return { body: "#63e6be", glow: "rgba(99,230,190,0.22)", hair: "#153d3e" };
    }
    if (role === "reviewer") {
      return { body: "#ff9ec2", glow: "rgba(255,158,194,0.2)", hair: "#512746" };
    }
    return palette[index % palette.length];
  }

  function bubbleForEvent(event, role) {
    if (!event) return "";
    const kind = String(event.kind || "").toLowerCase();
    if (kind === "task_dispatched") return role === "planner" ? "PLAN" : "TASK";
    if (kind === "agent_started") return role === "executor" ? "GO" : "SYNC";
    if (kind === "agent_finished") return role === "reviewer" ? "CHECK" : "DONE";
    if (kind === "agent_note") return "NOTE";
    if (kind === "cluster_finished") return "OK";
    return "MSG";
  }

  function summarizeEvent(event) {
    if (!event) return "";
    const summary = String(event.summary || "").trim();
    const detail = String(event.detail || "").trim();
    return summary || detail;
  }

  function syncOfficeState(snapshot) {
    const agentData = snapshot.agent || {};
    const runs = Array.isArray(agentData.active_runs) ? agentData.active_runs : [];
    const cluster = snapshot.cluster || {};
    const clusterAgents = Array.isArray(snapshot.agents) ? snapshot.agents.filter((item) => item && item.role !== "primary") : [];
    const activeIds = new Set();
    scene.occupancy = [null, null, null, null];

    if (cluster.enabled && clusterAgents.length) {
      const events = Array.isArray(cluster.events) ? cluster.events : [];
      const orderedRoles = ["planner", "executor", "reviewer"];
      const orderedAgents = [...clusterAgents].sort((a, b) => orderedRoles.indexOf(String(a.role || "")) - orderedRoles.indexOf(String(b.role || "")));
      orderedAgents.forEach((item, index) => {
        const workerId = item.agent_id || `cluster-${index}`;
        const worker = ensureAgent(workerId, index);
        const role = String(item.role || "agent").toLowerCase();
        const zone = clusterZones[role] || { seatIndex: index % scene.seats.length, idle: { x: 620, y: 540 }, waiting: { x: 620, y: 520 } };
        const roleEvent = [...events].reverse().find((event) => String(event.agent_id || "") === workerId);
        worker.state = mapClusterStatus(item.status);
        worker.action = actionForClusterAgent(role, worker.state, item.summary || "");
        worker.currentTool = "";
        worker.task = item.summary || cluster.objective || "";
        worker.channel = role || "cluster";
        worker.label = item.name || workerId;
        worker.helper = false;
        worker.role = role;
        worker.skin = skinForRole(role, index);
        worker.screenTint = worker.action === "reading" ? "#8fe3ff" : worker.action === "running" ? "#ffd166" : worker.action === "writing" ? "#63e6be" : "#7c9bff";
        worker.seatIndex = zone.seatIndex;
        worker.bubbleText = bubbleForEvent(roleEvent, role);
        worker.bubbleCooldown = worker.bubbleText ? 2600 : Math.max(0, worker.bubbleCooldown || 0);
        worker.eventKind = String((roleEvent || {}).kind || "");
        worker.eventSummary = summarizeEvent(roleEvent);
        worker.x = Number.isFinite(worker.x) ? worker.x : zone.idle.x;
        worker.y = Number.isFinite(worker.y) ? worker.y : zone.idle.y;
        scene.occupancy[worker.seatIndex] = worker.seatIndex;
        activeIds.add(workerId);
      });

      for (const [id, worker] of agents.entries()) {
        if (!activeIds.has(id)) {
          worker.state = "offline";
        }
      }

      for (const worker of agents.values()) {
        if (worker.state === "working") {
          const seat = scene.seats[worker.seatIndex] || scene.seats[0];
          assignRoute(worker, seat.x, seat.y);
        } else if (worker.state === "waiting") {
          const zone = clusterZones[worker.role] || clusterZones.executor;
          assignRoute(worker, zone.waiting.x, zone.waiting.y);
        } else if (worker.state === "idle") {
          const zone = clusterZones[worker.role] || clusterZones.executor;
          assignRoute(worker, zone.idle.x, zone.idle.y);
        }
      }
      return;
    }

    const main = ensureAgent("main", 0);
    main.state = agentData.state || "idle";
    main.action = classifyAction(main.state, agentData.current_tool || "");
    main.currentTool = agentData.current_tool || "";
    main.task = agentData.current_task || "";
    main.channel = agentData.last_channel || "";
    main.label = String(agentData.name || "").trim() || "Hiclaw";
    main.helper = false;
    main.screenTint = main.action === "reading" ? "#8fe3ff" : main.action === "running" ? "#ffd166" : main.action === "writing" ? "#63e6be" : "#7c9bff";
    main.seatIndex = main.state === "working" ? chooseSeat(0, 1) : 2;
    scene.occupancy[main.seatIndex] = main.seatIndex;
    activeIds.add("main");

    runs.forEach((run, index) => {
      const workerId = run.conversation_key || `run-${index}`;
      const worker = ensureAgent(workerId, index + 1);
      worker.state = "working";
      worker.action = classifyAction(worker.state, run.current_tool || "");
      worker.currentTool = run.current_tool || "";
      worker.task = run.prompt || "";
      worker.channel = run.channel || "";
      worker.label = run.channel || workerId;
      worker.helper = false;
      worker.screenTint = worker.action === "reading" ? "#8fe3ff" : worker.action === "running" ? "#ffd166" : worker.action === "writing" ? "#63e6be" : "#7c9bff";
      worker.seatIndex = chooseSeat(index + 1, index + 1);
      scene.occupancy[worker.seatIndex] = worker.seatIndex;
      activeIds.add(workerId);
    });

    for (const [id, worker] of agents.entries()) {
      if (!activeIds.has(id) && id !== "main") {
        worker.state = "offline";
      }
    }

    if (main.state === "idle") assignRoute(main, 580, 540);
    if (main.state === "waiting") assignRoute(main, 210, 520);

    for (const worker of agents.values()) {
      if (worker.state === "working") {
        const seat = scene.seats[worker.seatIndex] || scene.seats[0];
        assignRoute(worker, seat.x, seat.y);
      }
    }

    if (runs.length > 1) {
      runs.forEach((run, index) => {
        const helper = ensureAgent(`${run.conversation_key || `run-${index}`}::helper`, index + 3);
        helper.state = "working";
        helper.action = "running";
        helper.currentTool = run.current_tool || "";
        helper.channel = run.channel || "";
        helper.label = `assistant ${index + 1}`;
        helper.helper = true;
        helper.task = run.prompt || "";
        helper.screenTint = "#ffd166";
        assignRoute(helper, 300 + index * 90, 566 - (index % 2) * 16);
        activeIds.add(helper.id);
      });
    }
  }

  function updateAgent(agent, dt) {
    if (agent.state === "offline") return;

    agent.bob += dt * 0.004;
    agent.pulse += dt * 0.01;
    agent.wanderCooldown -= dt;

    if (agent.state === "idle" && agent.wanderCooldown <= 0) {
      assignRoute(
        agent,
        510 + Math.round((Math.random() - 0.5) * 220),
        540 + Math.round((Math.random() - 0.5) * 20),
      );
      agent.wanderCooldown = 2200 + Math.random() * 1800;
    }

    if (Array.isArray(agent.route) && agent.route.length) {
      const waypoint = agent.route[agent.routeIndex] || agent.route[agent.route.length - 1];
      agent.targetX = waypoint.x;
      agent.targetY = waypoint.y;
    }

    const speed = agent.state === "working" ? 0.12 : agent.state === "waiting" ? 0.07 : 0.08;
    const dx = agent.targetX - agent.x;
    const dy = agent.targetY - agent.y;
    const distance = Math.hypot(dx, dy);
    if (distance > 1.2) {
      agent.x += (dx / distance) * speed * dt;
      agent.y += (dy / distance) * speed * dt;
      agent.direction = dx >= 0 ? 1 : -1;
    } else if (agent.route.length) {
      agent.routeIndex = Math.min(agent.routeIndex + 1, agent.route.length - 1);
    }

    for (const other of agents.values()) {
      if (other === agent || other.state === "offline") continue;
      const pushDx = agent.x - other.x;
      const pushDy = agent.y - other.y;
      const pushDistance = Math.hypot(pushDx, pushDy);
      if (pushDistance > 0 && pushDistance < 36) {
        const force = (36 - pushDistance) * 0.018;
        agent.x += (pushDx / pushDistance) * force * dt;
        agent.y += (pushDy / pushDistance) * force * dt;
      }
    }

    agent.x = clamp(agent.x, scene.walkMinX, scene.walkMaxX);
    agent.y = clamp(agent.y, 300, 620);
    agent.bubbleCooldown = Math.max(0, (agent.bubbleCooldown || 0) - dt);
  }

  function drawWallDecor() {
    fill(332, 106, 96, 44, "#cfd9f5");
    fill(342, 116, 76, 24, "#6e7fa8");
    fill(458, 106, 96, 44, "#cfd9f5");
    fill(468, 116, 76, 24, "#6e7fa8");
    fill(746, 106, 108, 44, "#cfd9f5");
    fill(758, 116, 84, 24, "#63e6be");
    fill(890, 106, 90, 44, "#cfd9f5");
    fill(900, 116, 70, 24, "#ffd166");
  }

  function drawSeatForeground(x) {
    fill(x, 356, 100, 28, "#39476b");
    fill(x + 30, 384, 40, 78, "#2a314a");
    fill(x + 26, 462, 48, 14, "rgba(0,0,0,0.2)");
  }

  function drawOfficeChair(x, y, accent = "#4a567f") {
    fill(x + 8, y, 34, 12, accent);
    fill(x + 14, y + 12, 22, 22, "#2d3550");
    fill(x + 18, y + 34, 14, 20, "#39415f");
    fill(x + 23, y + 54, 4, 26, "#242b40");
    fill(x + 10, y + 72, 30, 6, "#20283c");
    fill(x + 2, y + 64, 10, 4, "#20283c");
    fill(x + 38, y + 64, 10, 4, "#20283c");
    fill(x + 20, y + 76, 4, 12, "#20283c");
    fill(x + 26, y + 76, 4, 12, "#20283c");
  }

  function drawPlantPot(x, y, scale = 1) {
    const w = 26 * scale;
    const h = 18 * scale;
    fill(x + 8 * scale, y + 34 * scale, w, h, "#8b654b");
    fill(x + 4 * scale, y + 30 * scale, (w + 8 * scale), 6 * scale, "#a87959");
    fill(x + 16 * scale, y + 2 * scale, 4 * scale, 30 * scale, "#567c58");
    fill(x, y + 10 * scale, 18 * scale, 14 * scale, "#87c980");
    fill(x + 18 * scale, y + 6 * scale, 18 * scale, 16 * scale, "#6bbf72");
    fill(x + 6 * scale, y + 20 * scale, 16 * scale, 12 * scale, "#9ade90");
    fill(x + 18 * scale, y + 20 * scale, 14 * scale, 12 * scale, "#79cf84");
  }

  function drawBookshelf(x, y) {
    fill(x, y, 66, 124, "#5f4637");
    fill(x + 6, y + 8, 54, 10, "#7f5f49");
    fill(x + 6, y + 42, 54, 8, "#7f5f49");
    fill(x + 6, y + 76, 54, 8, "#7f5f49");
    fill(x + 6, y + 108, 54, 8, "#7f5f49");
    fill(x + 10, y + 18, 8, 20, "#8ea3ff");
    fill(x + 20, y + 16, 6, 22, "#ffd166");
    fill(x + 28, y + 14, 10, 24, "#63e6be");
    fill(x + 40, y + 20, 7, 18, "#ff9ec2");
    fill(x + 48, y + 16, 8, 22, "#dce7ff");
    fill(x + 12, y + 52, 12, 20, "#cbe9df");
    fill(x + 28, y + 54, 16, 18, "#7c9bff");
    fill(x + 48, y + 50, 8, 22, "#ffd166");
    fill(x + 10, y + 88, 18, 14, "#d7c3a4");
    fill(x + 34, y + 88, 20, 14, "#a7d7b1");
  }

  function drawCoffeeTable(x, y) {
    fill(x, y, 76, 12, "#9d7657");
    fill(x + 6, y + 12, 8, 22, "#6d4f3b");
    fill(x + 62, y + 12, 8, 22, "#6d4f3b");
    fill(x + 22, y + 2, 14, 10, "#ece8db");
    fill(x + 40, y + 4, 10, 8, "#8ea3ff");
  }

  function drawCabinet(x, y) {
    fill(x, y, 84, 102, "#4f586f");
    fill(x + 6, y + 10, 72, 82, "#67738f");
    fill(x + 6, y + 44, 72, 6, "#4f586f");
    fill(x + 38, y + 20, 8, 8, "#dce7ff");
    fill(x + 38, y + 58, 8, 8, "#dce7ff");
  }

  function drawMeetingTable(x, y) {
    fill(x, y, 138, 18, "#8b654b");
    fill(x + 10, y + 18, 10, 28, "#5f4637");
    fill(x + 118, y + 18, 10, 28, "#5f4637");
    fill(x + 22, y + 4, 14, 10, "#f2ede0");
    fill(x + 50, y + 4, 18, 10, "#dce7ff");
    fill(x + 86, y + 6, 16, 8, "#ffd166");
  }

  function drawBench(x, y, width = 76) {
    fill(x, y, width, 14, "#39476b");
    fill(x + 10, y + 14, 10, 26, "#2a314a");
    fill(x + width - 20, y + 14, 10, 26, "#2a314a");
  }

  function drawDeskClutter(x, y) {
    fill(x, y, 14, 8, "#ece8db");
    fill(x + 18, y + 2, 10, 6, "#cbe9df");
    fill(x + 32, y + 1, 8, 7, "#ffd166");
    fill(x + 44, y, 10, 8, "#dce7ff");
  }

  function drawFloorLamp(x, y) {
    fill(x + 10, y, 28, 16, "#ffe8aa");
    fill(x + 14, y + 4, 20, 8, "#ffd166");
    fill(x + 20, y + 16, 8, 62, "#3a4468");
    fill(x + 8, y + 76, 32, 10, "#2a314a");
  }

  function drawForegroundOcclusion() {
    fill(336, 320, 286, 10, "rgba(255,255,255,0.04)");
    fill(668, 320, 286, 10, "rgba(255,255,255,0.04)");
    fill(350, 332, 260, 14, "rgba(10,14,24,0.18)");
    fill(682, 332, 260, 14, "rgba(10,14,24,0.18)");
    fill(830, 494, 202, 10, "rgba(255,255,255,0.05)");
    fill(818, 524, 214, 18, "rgba(10,14,24,0.34)");
    fill(842, 540, 180, 12, "rgba(10,14,24,0.18)");
    fill(210, 534, 74, 8, "rgba(255,255,255,0.03)");
    fill(548, 542, 86, 10, "rgba(255,255,255,0.03)");
  }

  function drawFloorTiles() {
    for (let x = 0; x < scene.width; x += 40) {
      for (let y = scene.floorTop + 20; y < scene.height; y += 40) {
        const tone = ((x + y) / 40) % 2 === 0 ? "rgba(255,255,255,0.028)" : "rgba(0,0,0,0.03)";
        fill(x, y, 38, 38, tone);
      }
    }
  }

  function drawBackground() {
    fill(0, 0, scene.width, scene.height, "#101625");
    fill(0, 0, scene.width, scene.floorTop, "#6e7fa8");
    fill(0, 88, scene.width, 120, "rgba(255,255,255,0.06)");
    fill(0, scene.floorTop, scene.width, scene.height - scene.floorTop, "#2f3754");
    fill(0, scene.floorTop, scene.width, 18, "#50638d");
    fill(0, scene.corridorY - 12, scene.width, 28, "rgba(148,166,220,0.18)");
    fill(0, scene.corridorY - 2, scene.width, 4, "rgba(255,255,255,0.06)");

    drawFloorTiles();

    fill(86, 74, 248, 146, "#dae4fb");
    fill(102, 90, 216, 112, "#8fe3ff");
    fill(206, 90, 10, 112, "#dce7ff");
    fill(102, 144, 216, 10, "#dce7ff");
    fill(92, 80, 236, 134, "rgba(255,255,255,0.08)");

    fill(332, 220, 300, 22, "#a27b5b");
    fill(344, 242, 278, 82, "#684938");
    fill(376, 208, 56, 36, "#111827");
    fill(382, 214, 44, 24, "#8ea3ff");
    fill(416, 238, 10, 14, "#2f3754");
    fill(452, 212, 26, 22, "#c5d1f6");

    fill(664, 220, 300, 22, "#a27b5b");
    fill(676, 242, 278, 82, "#684938");
    fill(706, 208, 56, 36, "#111827");
    fill(712, 214, 44, 24, "#63e6be");
    fill(746, 238, 10, 14, "#2f3754");
    fill(786, 212, 28, 24, "#cbe9df");
    drawDeskClutter(364, 250);
    drawDeskClutter(696, 250);

    drawOfficeChair(420, 340, "#4b5d89");
    drawOfficeChair(752, 340, "#456a63");
    drawOfficeChair(598, 504, "#5b4a89");

    drawSeatForeground(388);
    drawSeatForeground(720);

    fill(830, 466, 192, 24, "#86a2cf");
    fill(818, 492, 212, 32, "#5b7aa8");
    fill(870, 524, 22, 30, "#2e3f5f");
    fill(960, 524, 22, 30, "#2e3f5f");
    fill(836, 530, 178, 10, "rgba(0,0,0,0.14)");
    drawCoffeeTable(866, 500);
    drawBench(846, 468, 76);
    drawBench(964, 468, 54);

    drawPlantPot(86, 418, 1.3);
    fill(84, 534, 74, 12, "rgba(0,0,0,0.16)");

    fill(210, 486, 72, 18, "#3a4468");
    fill(220, 504, 54, 32, "#222941");
    fill(216, 536, 60, 10, "rgba(0,0,0,0.18)");

    fill(550, 500, 74, 16, "#8f6c52");
    fill(558, 486, 58, 14, "#cdb79a");
    fill(570, 516, 10, 30, "#6b4e39");
    fill(596, 516, 10, 30, "#6b4e39");
    fill(548, 544, 82, 8, "rgba(0,0,0,0.18)");
    drawPlantPot(642, 474, 0.9);
    drawPlantPot(1030, 478, 0.85);
    drawMeetingTable(520, 610);

    fill(1044, 160, 56, 124, "#ffe29b");
    fill(1058, 174, 28, 92, "#ffd166");
    fill(1068, 282, 10, 38, "#3c4766");
    fill(1044, 286, 54, 8, "rgba(255,255,255,0.08)");
    drawFloorLamp(1018, 154);

    fill(206, 518, 62, 20, "rgba(255,209,102,0.16)");
    fill(532, 548, 180, 24, "rgba(124,155,255,0.12)");
    fill(0, 664, scene.width, 96, "rgba(5,8,14,0.42)");
    drawWallDecor();
    drawCabinet(998, 330);
    drawBookshelf(1110, 240);
    drawForegroundOcclusion();
  }

  function drawAgentGlow(agent) {
    const glowColor = agent.state === "waiting" ? "rgba(255,209,102,0.2)" : agent.skin.glow;
    fill(agent.x - 10, agent.y - 8, 54, 62, glowColor);
    fill(agent.x - 4, agent.y + 10, 42, 26, "rgba(255,255,255,0.04)");
  }

  function drawWorkingFx(agent) {
    if (agent.state !== "working") return;
    const pulse = 8 + Math.sin(agent.pulse) * 3;
    fill(agent.x + 2, agent.y - 60, 38 + pulse, 20, agent.action === "running" ? "rgba(255,209,102,0.18)" : "rgba(99,230,190,0.18)");
    fill(agent.x + 8, agent.y + 8, 18, 6, "rgba(255,255,255,0.12)");
    if (agent.action === "reading") {
      fill(agent.x + 26, agent.y + 8, 14, 6, "rgba(143,227,255,0.18)");
    }
    if (agent.action === "writing") {
      fill(agent.x + 26, agent.y + 8, 14, 6, "rgba(99,230,190,0.16)");
    }
    if (agent.helper) {
      fill(agent.x - 2, agent.y - 8, 18, 8, "rgba(255,255,255,0.08)");
    }
  }

  function drawScreenAura(agent, x, y) {
    if (agent.state !== "working") return;
    const tint = agent.screenTint || "#7c9bff";
    fill(x + 28, y - 4, 18, 14, `${tint}22`);
    fill(x + 26, y - 6, 22, 18, `${tint}18`);
    fill(x + 14, y + 12, 18, 8, `${tint}14`);
  }

  function drawActionProp(agent, x, y) {
    if (agent.action === "reading" || agent.action === "researching") {
      fill(x + 30, y + 28, 8, 10, "#dce7ff");
      fill(x + 30, y + 30, 6, 2, "#7c9bff");
      fill(x + 30, y + 34, 6, 2, "#7c9bff");
      return;
    }
    if (agent.action === "writing") {
      fill(x + 29, y + 29, 10, 8, "#f0f4ff");
      fill(x + 38, y + 31, 3, 2, "#7c9bff");
      return;
    }
    if (agent.action === "running") {
      fill(x + 29, y + 28, 12, 10, "#222941");
      fill(x + 31, y + 30, 8, 4, "#ffd166");
    }
  }

  function drawSpeechBubble(agent, text) {
    fill(agent.x - 16, agent.y - 62, 84, 28, "#ffffff");
    fill(agent.x - 10, agent.y - 56, 72, 16, "#f6f8ff");
    fill(agent.x + 12, agent.y - 34, 12, 8, "#ffffff");
    ctx.fillStyle = "#1f2b45";
    ctx.font = "12px monospace";
    ctx.fillText(text, agent.x - 2, agent.y - 44);
  }

  function drawEventCaption(agent) {
    if (!agent.eventSummary) return;
    ctx.fillStyle = "rgba(237,242,255,0.92)";
    ctx.font = "10px monospace";
    ctx.fillText(String(agent.eventSummary).slice(0, 18), Math.round(agent.x) - 6, Math.round(agent.y) - 74);
  }

  function drawWaitingBeacon(agent) {
    fill(agent.x - 6, agent.y - 74, 44, 10, "rgba(255,209,102,0.14)");
    fill(agent.x + 10, agent.y - 80, 10, 18, "#ffd166");
    fill(agent.x + 10, agent.y - 60, 10, 4, "#fff4d7");
  }

  function drawHelperBadge(agent, x, y) {
    if (!agent.helper) return;
    fill(x - 6, y + 10, 10, 10, "#fef3a0");
    fill(x - 4, y + 12, 6, 6, "#fff7c2");
  }

  function drawRoleAccent(agent, x, y, seated) {
    if (agent.role === "planner") {
      fill(x + 6, y + 8, 4, 14, "#eef3ff");
      fill(x + 32, y + 8, 4, 8, "#dce7ff");
    } else if (agent.role === "executor") {
      fill(x + 30, y + 30, 6, 10, "#e6fff6");
      fill(x + 8, y + 30, 4, 6, "#cbfff0");
    } else if (agent.role === "reviewer") {
      fill(x + 8, y + 30, 4, 4, "#ffe8f1");
      fill(x + 32, y + 30, 4, 4, "#ffe8f1");
      if (seated) {
        fill(x + 16, y + 24, 10, 3, "#ffe8f1");
      }
    }
  }

  function drawRoleHalo(agent, x, y) {
    if (agent.role === "planner") {
      fill(x - 4, y - 8, 48, 6, "rgba(142,163,255,0.18)");
    } else if (agent.role === "executor") {
      fill(x - 4, y + 66, 48, 6, "rgba(99,230,190,0.18)");
    } else if (agent.role === "reviewer") {
      fill(x - 4, y - 8, 48, 6, "rgba(255,158,194,0.16)");
      fill(x - 4, y + 66, 48, 6, "rgba(255,158,194,0.12)");
    }
  }

  function drawAgent(agent) {
    if (agent.state === "offline") return;
    const x = Math.round(agent.x);
    const seated = agent.state === "working";
    const y = Math.round(agent.y + Math.sin(agent.bob) * (seated ? 1 : 2));
    fill(x + 8, y + (seated ? 40 : 48), 34, 8, "rgba(0,0,0,0.22)");
    drawRoleHalo(agent, x, y);
    drawAgentGlow(agent);

    fill(x + 10, y + 2, 24, 10, agent.skin.hair);
    fill(x + 12, y + 12, 20, 16, "#f3c8a5");
    fill(x + 8, y + 28, 28, 20, agent.skin.body);
    fill(x + 4, y + 30, 5, 13, "#f3c8a5");
    fill(x + 35, y + 30, 5, 13, "#f3c8a5");
    if (seated) {
      fill(x + 8, y + 26, 28, 4, "rgba(0,0,0,0.08)");
      fill(x + 12, y + 44, 20, 8, "#24314c");
      fill(x + 10, y + 52, 24, 6, "#1d2233");
      fill(x + 8, y + 58, 10, 8, "#24314c");
      fill(x + 26, y + 58, 10, 8, "#24314c");
    } else {
      fill(x + 12, y + 48, 6, 16, "#24314c");
      fill(x + 26, y + 48, 6, 16, "#24314c");
    }
    fill(x + 15, y + 18, 2, 2, "#1b1f2e");
    fill(x + 25, y + 18, 2, 2, "#1b1f2e");
    fill(x + 10, y + 6, 24, 3, agent.skin.body);
    if (seated) {
      fill(x + 8, y + 34, 8, 6, "#f3c8a5");
      fill(x + 28, y + 34, 8, 6, "#f3c8a5");
      fill(x + 14, y + 40, 18, 4, "rgba(0,0,0,0.08)");
    }
    fill(x + 28, y + 32, 7, 7, "#f3f6ff");
    fill(x + 11, y + 31, 6, 7, "rgba(255,255,255,0.08)");
    fill(x + 18, y + 20, 8, 2, "rgba(0,0,0,0.14)");
    drawRoleAccent(agent, x, y, seated);
    drawActionProp(agent, x, y);
    drawScreenAura(agent, x, y);
    drawHelperBadge(agent, x, y);

    drawWorkingFx(agent);

    if (agent.bubbleText && agent.bubbleCooldown > 0) {
      drawSpeechBubble(agent, agent.bubbleText);
      drawEventCaption(agent);
    } else if (agent.state === "working") {
      const label = agent.action === "reading" ? "READ" : agent.action === "writing" ? "WRITE" : agent.action === "running" ? "RUN" : agent.action === "researching" ? "SEARCH" : "WORK";
      drawSpeechBubble(agent, label);
    } else if (agent.state === "waiting") {
      drawSpeechBubble(agent, "?");
      drawWaitingBeacon(agent);
    }

    ctx.fillStyle = "#edf2ff";
    ctx.font = "12px sans-serif";
    const labelText = agent.role && agent.role !== "primary" ? agent.role.toUpperCase() : (agent.helper ? `assist ${agent.label}` : agent.label);
    ctx.fillText(labelText.slice(0, 14), x - 2, y + (seated ? 66 : 76));
  }

  function render() {
    drawBackground();
    const visibleAgents = Array.from(agents.values()).filter((agent) => agent.state !== "offline").sort((a, b) => a.y - b.y);
    visibleAgents.forEach((agent) => drawAgent(agent));
  }

  function tickOfficeFrame(dt) {
    for (const agent of agents.values()) {
      updateAgent(agent, dt);
    }
    render();
  }

  async function initializeOffice() {
    ensureAgent("main", 0);
    await Promise.resolve();
  }

  window.PixelOfficeV2Engine = {
    initializeOffice,
    syncOfficeState,
    tickOfficeFrame,
  };
})();
