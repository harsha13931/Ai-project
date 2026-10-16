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
      list.append(el("li", {}, [
        el("div", {}, [el("div", { className: "name", text: doc.name })]),
        el("div", { className: "tags" }, tags),
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
    button.disabled = true;
    try {
      const quiz = await api("/api/quiz", { method: "POST" });
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

  /* ---------- Boot ---------- */

  (async () => {
    try {
      await Promise.all([refreshDocuments(), loadRoles()]);
    } catch (err) {
      setStatus($("upload-status"), "Could not reach the server. Is the API running?", "error");
    }
  })();
})();
