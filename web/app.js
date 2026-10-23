(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const state = { quizId: null, roles: [] };

  /** Build an element without innerHTML, so document text is never parsed as markup. */
  function el(tag, props = {}, children = []) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props)) {
      if (key === "className") node.className = value;
      else if (key === "text") node.textContent = value;
      else node.setAttribute(key, value);
    }
    for (const child of [].concat(children)) {
      if (child) node.append(child);
    }
    return node;
  }

  async function api(path, options = {}) {
    const init = { ...options, headers: { ...(options.headers || {}) } };
    if (options.body && !(options.body instanceof FormData)) {
      init.headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(options.body);
    }
    const response = await fetch(path, init);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = Array.isArray(payload.detail) ? payload.detail[0]?.msg : payload.detail;
      throw new Error(detail || `Request failed (${response.status})`);
    }
    return payload;
  }

  function setStatus(node, message, kind = "") {
    node.textContent = message;
    node.className = `status ${kind}`.trim();
  }

  /* ---------- Documents ---------- */

  async function refreshDocuments() {
    const docs = await api("/api/documents");
    const list = $("doc-list");
    list.replaceChildren();
    if (!docs.length) {
      list.append(el("li", { className: "muted", text: "None yet." }));
    }
    for (const doc of docs) {
      const tags = [el("span", { className: "tag", text: `${doc.pages} page${doc.pages === 1 ? "" : "s"}` })];
      if (doc.is_resume) tags.push(el("span", { className: "tag resume", text: "Resume detected" }));
      const deleteBtn = el("button", { className: "btn-delete", "aria-label": `Delete ${doc.name}`, text: "×" });
      deleteBtn.addEventListener("click", async () => {
        if (!confirm(`Delete ${doc.name}?`)) return;
        try {
          await api(`/api/documents/${doc.id}`, { method: "DELETE" });
          await refreshDocuments();
        } catch (err) {
          alert(err.message);
        }
      });
      list.append(el("li", {}, [
        el("div", {}, [el("div", { className: "name", text: doc.name })]),
        el("div", { className: "tags" }, [...tags, deleteBtn]),
      ]));
    }
    updateAssessmentHint(docs);
  }

  function updateAssessmentHint(docs) {
    const hasResume = docs.some((d) => d.is_resume);
    $("start-quiz").disabled = !hasResume;
    $("assess-hint").textContent = hasResume
      ? "Resume detected. Your assessment will be personalised to it."
      : "Requires an uploaded resume.";
  }

  const dropzone = $("upload-form");
  ["dragenter", "dragover"].forEach((evt) =>
    dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((evt) =>
    dropzone.addEventListener(evt, () => dropzone.classList.remove("drag")));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    if (e.dataTransfer.files.length) $("file-input").files = e.dataTransfer.files;
  });

  $("upload-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = $("file-input").files[0];
    const status = $("upload-status");
    if (!file) return setStatus(status, "Choose a file first.", "error");

    const button = event.submitter;
    button.disabled = true;
    setStatus(status, `Processing ${file.name}…`);
    try {
      const form = new FormData();
      form.append("file", file);
      const doc = await api("/api/documents", { method: "POST", body: form });
      setStatus(status, doc.is_resume
        ? `Added ${doc.name}. Resume detected, so you can start the assessment.`
        : `Added ${doc.name} with ${doc.chunks} searchable chunks.`, "ok");
      await refreshDocuments();
      $("file-input").value = "";
    } catch (err) {
      setStatus(status, err.message, "error");
    } finally {
      button.disabled = false;
    }
  });

  /* ---------- Ask ---------- */

  $("ask-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = $("question").value.trim();
    const panel = $("answer");
    try {
      const result = await api("/api/ask", { method: "POST", body: { question } });
      $("answer-text").textContent = result.answer;
      $("answer-mode").textContent = result.mode === "llm"
        ? "Written by the language model from the sources below."
        : result.mode === "extractive"
          ? "Extracted from the most relevant passages (no language model configured)."
          : "";
      const sources = $("sources");
      sources.replaceChildren();
      for (const src of result.sources) {
        sources.append(el("li", {}, [
          el("strong", { text: `${src.doc} · page ${src.page} · relevance ${src.score.toFixed(2)}` }),
          el("span", { text: src.excerpt + (src.excerpt.length >= 240 ? "…" : "") }),
        ]));
      }
      panel.hidden = false;
    } catch (err) {
      $("answer-text").textContent = err.message;
      $("answer-mode").textContent = "";
      $("sources").replaceChildren();
      panel.hidden = false;
    }
  });

  /* ---------- Assessment ---------- */

  $("start-quiz").addEventListener("click", async () => {
    const button = $("start-quiz");
    const numQuestions = Number($("num-questions").value) || 10;
    if (numQuestions < 3 || numQuestions > 50) {
      $("assess-hint").textContent = "Choose between 3 and 50 questions.";
      return;
    }
    button.disabled = true;
    $("assess-hint").textContent = "Generating questions from your resume…";
    try {
      const quiz = await api("/api/quiz", {
        method: "POST",
        body: { num_questions: numQuestions },
      });
      state.quizId = quiz.id;
      renderQuiz(quiz);
    } catch (err) {
      $("assess-hint").textContent = err.message;
    } finally {
      button.disabled = false;
    }
  });

  function renderQuiz(quiz) {
    const form = $("quiz-form");
    form.replaceChildren();
    $("results").hidden = true;
    $("results").replaceChildren();
    $("assess-intro").hidden = true;

    form.append(el("p", { className: "progress-line", text: `${quiz.total} multiple-choice questions. Pick one answer per question.` }));

    quiz.questions.forEach((q, index) => {
      const legend = el("legend", { text: `${index + 1}. ${q.q}` });
      const meta = el("p", { className: "q-meta", text: `${q.topic_label}${q.claimed ? " · from your resume" : " · gap check"}` });
      const options = q.options.map((option, optIndex) => {
        const input = el("input", { type: "radio", name: q.id, value: String(optIndex) });
        return el("label", { className: "option" }, [input, el("span", { text: option })]);
      });
      form.append(el("div", { className: "question" }, [
        meta,
        el("fieldset", {}, [legend, ...options]),
      ]));
    });

    form.append(el("button", { className: "btn btn-primary", type: "submit", text: "Submit answers" }));
    form.hidden = false;
    form.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  $("quiz-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const answers = {};
    for (const radio of form.querySelectorAll('input[type="radio"]:checked')) {
      answers[radio.name] = Number(radio.value);
    }
    const total = new Set([...form.querySelectorAll('input[type="radio"]')].map((r) => r.name)).size;
    if (Object.keys(answers).length < total) {
      const unanswered = total - Object.keys(answers).length;
      return alert(`Please answer every question. ${unanswered} left.`);
    }
    try {
      const result = await api(`/api/quiz/${state.quizId}/submit`, { method: "POST", body: { answers } });
      renderResults(result);
      form.hidden = true;
      $("roadmap").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      alert(err.message);
    }
  });

  function renderResults(result) {
    const box = $("results");
    box.replaceChildren();

    const bar = el("div", { className: "bar", role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": String(result.percent), "aria-label": "Overall score" }, [
      el("span", { style: `width:${result.percent}%` }),
    ]);
    box.append(el("div", { className: "score-card" }, [
      el("div", { className: "score-big", text: `${result.percent}%` }),
      el("strong", { text: `${result.level} · ${result.score} of ${result.total} correct` }),
      el("p", { className: "muted", text: result.advice }),
      bar,
    ]));

    box.append(el("h3", { text: "Skill breakdown" }));
    for (const topic of result.topics) {
      const header = el("header", {}, [
        el("span", { text: topic.label }),
        el("span", { text: `${topic.percent}% (${topic.correct}/${topic.total})` }),
      ]);
      const rowChildren = [header, el("div", { className: "bar" }, [el("span", { style: `width:${topic.percent}%` })])];
      if (topic.flag) rowChildren.push(el("span", { className: "flag", text: topic.flag }));
      if (topic.guidance) rowChildren.push(el("p", { className: "guidance", text: `Guidance: ${topic.guidance}` }));
      box.append(el("div", { className: "topic-row" }, rowChildren));
    }

    const items = result.review.map((r) => el("li", {}, [
      el("span", { className: r.correct ? "ok" : "no", text: r.correct ? "Correct" : "Review" }),
      el("p", { style: "margin:0.3rem 0 0.2rem", text: `${r.topic}: ${r.explanation}` }),
      el("p", { className: "muted small", style: "margin:0", text: r.correct ? "" : `Correct answer: ${r.right_answer}` }),
    ]));
    box.append(el("div", { className: "score-card" }, [
      el("h3", { text: "Answer review" }),
      el("ul", { className: "review", style: "padding:0;margin:0" }, items),
    ]));

    box.append(el("div", { className: "score-card" }, [
      el("h3", { text: "Last step: which role do you want?" }),
      el("p", { className: "muted", text: "Choose a target role below. Your gaps are placed at the front of the plan." }),
    ]));
    box.hidden = false;
    state.lastResult = result;
  }

  /* ---------- Roadmap ---------- */

  async function loadRoles() {
    state.roles = await api("/api/roles");
    const grid = $("role-grid");
    state.roles.forEach((role, index) => {
      const input = el("input", { type: "radio", name: "role", value: role.key, ...(index === 0 ? { checked: "checked" } : {}) });
      grid.append(el("label", { className: "role-card" }, [
        input,
        el("strong", { text: role.label }),
        el("span", { text: role.summary }),
      ]));
    });
  }

  $("build-roadmap").addEventListener("click", async () => {
    const status = $("roadmap-status");
    const role = document.querySelector('input[name="role"]:checked')?.value;
    const weeks = Number($("weeks").value);
    const hours = Number($("hours").value);
    if (!role) return setStatus(status, "Pick a role first.", "error");
    if (!(weeks >= 4 && weeks <= 26) || !(hours >= 2 && hours <= 40)) {
      return setStatus(status, "Weeks must be 4–26 and hours per week 2–40.", "error");
    }

    setStatus(status, "Building your roadmap…");
    try {
      const plan = await api("/api/roadmap", {
        method: "POST",
        body: { role, weeks, hours_per_week: hours, quiz_id: state.quizId },
      });
      renderRoadmap(plan);
      setStatus(status, `Roadmap ready: ${plan.total_weeks} weeks, ${plan.total_hours} hours.`, "ok");
    } catch (err) {
      setStatus(status, err.message, "error");
    }
  });

  function renderRoadmap(plan) {
    $("roadmap-heading").textContent = `${plan.role}: ${plan.summary}`;

    const phases = $("phases");
    phases.replaceChildren();
    for (const phase of plan.phases) {
      phases.append(el("article", { className: "phase" }, [
        el("h3", { text: phase.name }),
        el("p", { className: "muted small", text: `Weeks ${phase.start_week}–${phase.start_week + phase.weeks - 1}` }),
        el("ul", {}, phase.topics.map((t) => el("li", { text: t }))),
        el("p", { className: "deliverable", text: `Milestone: ${phase.deliverable}` }),
      ]));
    }

    const body = $("timetable-body");
    body.replaceChildren();
    for (const row of plan.timetable) {
      body.append(el("tr", { className: row.milestone ? "milestone" : "" }, [
        el("td", { text: `W${row.week}` }),
        el("td", { text: row.phase }),
        el("td", { text: row.topics }),
        el("td", { text: `${row.hours} h` }),
        el("td", { text: row.milestone || "—" }),
      ]));
    }
    $("roadmap-out").hidden = false;
  }

  /* ---------- Pipeline Graph ---------- */

  const NODE_COLORS = {
    input: "#4f46e5",
    process: "#7c3aed",
    condition: "#b45309",
    fallback: "#b91c1c",
    output: "#15803d",
  };

  let graphTooltip = null;

  function ensureTooltip() {
    if (graphTooltip) return graphTooltip;
    graphTooltip = document.createElement("div");
    graphTooltip.className = "graph-tooltip";
    document.body.appendChild(graphTooltip);
    return graphTooltip;
  }

  function layoutGraph(graph) {
    const nodes = graph.nodes;
    const nodeMap = {};
    nodes.forEach((n, i) => { nodeMap[n.id] = i; });

    const cols = [];
    const placed = new Set();
    const edges = graph.edges;

    // topological layers
    const incoming = {};
    nodes.forEach((n) => { incoming[n.id] = 0; });
    edges.forEach((e) => { incoming[e.to] = (incoming[e.to] || 0) + 1; });

    let queue = nodes.filter((n) => incoming[n.id] === 0).map((n) => n.id);
    while (queue.length) {
      cols.push([...queue]);
      queue.forEach((id) => placed.add(id));
      const next = [];
      for (const id of queue) {
        for (const e of edges) {
          if (e.from === id && !placed.has(e.to)) {
            incoming[e.to]--;
            if (incoming[e.to] <= 0 && !next.includes(e.to)) next.push(e.to);
          }
        }
      }
      queue = next;
    }
    // catch any remaining
    nodes.forEach((n) => { if (!placed.has(n.id)) cols[cols.length - 1].push(n.id); });

    const nodeW = 150, nodeH = 48, colGap = 80, rowGap = 28;
    const totalW = cols.length * (nodeW + colGap) - colGap;
    const maxRows = Math.max(...cols.map((c) => c.length));
    const totalH = maxRows * (nodeH + rowGap) - rowGap;
    const padX = 40, padY = 40;
    const positions = {};

    cols.forEach((col, ci) => {
      const x = padX + ci * (nodeW + colGap);
      const colH = col.length * (nodeH + rowGap) - rowGap;
      const offsetY = padY + (totalH - colH) / 2;
      col.forEach((id, ri) => {
        positions[id] = { x, y: offsetY + ri * (nodeH + rowGap), w: nodeW, h: nodeH };
      });
    });

    return { positions, width: totalW + padX * 2, height: totalH + padY * 2 };
  }

  function renderGraphSVG(graph) {
    const { positions, width, height } = layoutGraph(graph);
    const svg = $("graph-svg");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.innerHTML = "";

    const ns = "http://www.w3.org/2000/svg";

    // marker for arrowheads
    const defs = document.createElementNS(ns, "defs");
    const marker = document.createElementNS(ns, "marker");
    marker.setAttribute("id", "arrow");
    marker.setAttribute("viewBox", "0 0 10 10");
    marker.setAttribute("refX", "10");
    marker.setAttribute("refY", "5");
    marker.setAttribute("markerWidth", "8");
    marker.setAttribute("markerHeight", "8");
    marker.setAttribute("orient", "auto-start-reverse");
    const arrowPath = document.createElementNS(ns, "path");
    arrowPath.setAttribute("d", "M 0 0 L 10 5 L 0 10 z");
    arrowPath.setAttribute("fill", "var(--muted)");
    marker.appendChild(arrowPath);
    defs.appendChild(marker);
    svg.appendChild(defs);

    // edges
    for (const edge of graph.edges) {
      const from = positions[edge.from];
      const to = positions[edge.to];
      if (!from || !to) continue;

      const x1 = from.x + from.w;
      const y1 = from.y + from.h / 2;
      const x2 = to.x;
      const y2 = to.y + to.h / 2;

      const midX = (x1 + x2) / 2;
      const path = document.createElementNS(ns, "path");
      path.setAttribute("d", `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`);
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", "var(--border)");
      path.setAttribute("stroke-width", "2");
      path.setAttribute("marker-end", "url(#arrow)");
      svg.appendChild(path);

      if (edge.label) {
        const lx = midX;
        const ly = (y1 + y2) / 2 - 6;
        const text = document.createElementNS(ns, "text");
        text.setAttribute("x", String(lx));
        text.setAttribute("y", String(ly));
        text.setAttribute("text-anchor", "middle");
        text.setAttribute("fill", "var(--muted)");
        text.setAttribute("font-size", "11");
        text.setAttribute("font-weight", "600");
        text.textContent = edge.label;
        svg.appendChild(text);
      }
    }

    // nodes
    for (const node of graph.nodes) {
      const pos = positions[node.id];
      const color = NODE_COLORS[node.type] || NODE_COLORS.process;
      const g = document.createElementNS(ns, "g");
      g.setAttribute("class", "graph-node");
      g.style.cursor = node.detail ? "pointer" : "default";

      const isCondition = node.type === "condition";
      if (isCondition) {
        const diamond = document.createElementNS(ns, "polygon");
        const cx = pos.x + pos.w / 2, cy = pos.y + pos.h / 2;
        const rx = pos.w / 2, ry = pos.h / 2;
        diamond.setAttribute("points", `${cx},${cy - ry} ${cx + rx},${cy} ${cx},${cy + ry} ${cx - rx},${cy}`);
        diamond.setAttribute("fill", color);
        diamond.setAttribute("opacity", "0.12");
        diamond.setAttribute("stroke", color);
        diamond.setAttribute("stroke-width", "2");
        g.appendChild(diamond);
      } else {
        const rect = document.createElementNS(ns, "rect");
        rect.setAttribute("x", String(pos.x));
        rect.setAttribute("y", String(pos.y));
        rect.setAttribute("width", String(pos.w));
        rect.setAttribute("height", String(pos.h));
        rect.setAttribute("rx", node.type === "input" || node.type === "output" ? "24" : "10");
        rect.setAttribute("fill", color);
        rect.setAttribute("opacity", "0.12");
        rect.setAttribute("stroke", color);
        rect.setAttribute("stroke-width", "2");
        g.appendChild(rect);
      }

      const text = document.createElementNS(ns, "text");
      text.setAttribute("x", String(pos.x + pos.w / 2));
      text.setAttribute("y", String(pos.y + pos.h / 2 + 5));
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("fill", "var(--text)");
      text.setAttribute("font-size", "13");
      text.setAttribute("font-weight", "600");
      text.textContent = node.label;
      g.appendChild(text);

      if (node.detail) {
        g.addEventListener("mouseenter", (evt) => {
          const tt = ensureTooltip();
          tt.innerHTML = `<div class="tt-label">${node.label}</div><div class="tt-detail">${node.detail}</div>`;
          tt.classList.add("visible");
          const r = evt.target.closest("g").getBoundingClientRect();
          tt.style.left = `${r.left + r.width / 2 - 140}px`;
          tt.style.top = `${r.bottom + 8}px`;
        });
        g.addEventListener("mouseleave", () => {
          ensureTooltip().classList.remove("visible");
        });
      }

      svg.appendChild(g);
    }
  }

  function renderGraphMeta(meta) {
    const box = $("graph-meta");
    box.replaceChildren();
    const items = [
      { color: NODE_COLORS.input, text: "Input" },
      { color: NODE_COLORS.process, text: "Process" },
      { color: NODE_COLORS.condition, text: "Condition" },
      { color: NODE_COLORS.fallback, text: "Fallback" },
      { color: NODE_COLORS.output, text: "Output" },
    ];
    for (const item of items) {
      const dot = el("span", { className: "dot", style: `background:${item.color}` });
      box.append(el("span", {}, [dot, document.createTextNode(` ${item.text}`)]));
    }
    box.append(el("span", { text: `Framework: ${meta.framework}` }));
    box.append(el("span", { text: `Embeddings: ${meta.embeddings}` }));
    box.append(el("span", { text: `Vector: ${meta.vector_store} + ${meta.lexical}` }));
    if (meta.llm_provider !== "none") {
      box.append(el("span", { text: `LLM: ${meta.llm_provider} / ${meta.llm_model}` }));
    }
  }

  async function loadPipelineGraph() {
    try {
      const data = await api("/api/pipeline-graph");
      const tabBar = $("graph-tabs");
      tabBar.replaceChildren();

      data.graphs.forEach((graph, index) => {
        const btn = el("button", {
          className: "graph-tab",
          role: "tab",
          "aria-selected": index === 0 ? "true" : "false",
          text: graph.label,
        });
        btn.addEventListener("click", () => {
          tabBar.querySelectorAll(".graph-tab").forEach((t) => t.setAttribute("aria-selected", "false"));
          btn.setAttribute("aria-selected", "true");
          renderGraphSVG(graph);
        });
        tabBar.append(btn);
      });

      if (data.graphs.length) renderGraphSVG(data.graphs[0]);
      renderGraphMeta(data.meta);
    } catch (err) {
      $("graph-viewport").textContent = "Could not load pipeline graph.";
    }
  }

  /* ---------- Boot ---------- */

  (async () => {
    try {
      await Promise.all([refreshDocuments(), loadRoles(), loadPipelineGraph()]);
    } catch (err) {
      setStatus($("upload-status"), "Could not reach the server. Is the API running?", "error");
    }
  })();
})();
