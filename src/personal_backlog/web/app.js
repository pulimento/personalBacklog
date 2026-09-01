const states = [
  { key: "todo", cards: "todo-cards", count: "todo-count" },
  { key: "in_progress", cards: "in-progress-cards", count: "in-progress-count" },
  { key: "done", cards: "done-cards", count: "done-count" },
];

const elements = {
  project: document.querySelector("#project-name"),
  path: document.querySelector("#backlog-path"),
  version: document.querySelector("#version"),
  summary: document.querySelector("#summary"),
  message: document.querySelector("#message"),

  // Toolbar & controls
  viewBoardBtn: document.querySelector("#view-board-btn"),
  viewEditorBtn: document.querySelector("#view-editor-btn"),
  releaseFilter: document.querySelector("#release-filter"),
  readonlyToggle: document.querySelector("#readonly-toggle"),
  readonlyStatusText: document.querySelector("#readonly-status-text"),
  readonlySwitchContainer: document.querySelector("#readonly-switch-container"),
  refreshBtn: document.querySelector("#refresh-btn"),
  newTaskBtn: document.querySelector("#new-task"),
  footerMode: document.querySelector("#footer-mode-text"),

  // Views
  boardView: document.querySelector("#board-view"),
  editorView: document.querySelector("#editor-view"),

  // Editor pane elements
  stateFilter: document.querySelector("#state-filter"),
  taskList: document.querySelector("#task-list"),
  taskCount: document.querySelector("#task-count"),
  editor: document.querySelector("#editor"),
  emptyEditor: document.querySelector("#empty-editor"),
  emptyEditorText: document.querySelector("#empty-editor-text"),
  taskDetail: document.querySelector("#task-detail"),
  taskForm: document.querySelector("#task-form"),
  taskId: document.querySelector("#task-id"),
  editorTitle: document.querySelector("#editor-title"),
  title: document.querySelector("#title"),
  state: document.querySelector("#state"),
  priority: document.querySelector("#priority"),
  size: document.querySelector("#size"),
  release: document.querySelector("#release"),
  tags: document.querySelector("#tags"),
  body: document.querySelector("#body"),
  preview: document.querySelector("#body-preview"),
  previewToggle: document.querySelector("#preview-toggle"),
  timestamps: document.querySelector("#timestamps"),
  cancel: document.querySelector("#cancel"),
  close: document.querySelector("#close-editor"),

  // Board elements
  template: document.querySelector("#task-card-template"),
  dialog: document.querySelector("#task-dialog"),
  dialogDetail: document.querySelector("#dialog-task-detail"),
};

let tasks = [];
let currentTask = null;
let currentView = localStorage.getItem("personal-backlog-view") || "board";
let serverReadOnly = false;
let userReadOnly = localStorage.getItem("personal-backlog-readonly") === "true";
let defaultRelease = null;
let defaultReleaseApplied = false;
let previewing = false;
let messageTimer = null;

const { renderMarkdown, render: renderTaskDetail } = window.PersonalBacklogTaskDetail;

function isReadOnly() {
  return serverReadOnly || userReadOnly;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: options.body ? { "Content-Type": "application/json" } : {},
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

function notify(message, isError = false) {
  clearTimeout(messageTimer);
  elements.message.textContent = message;
  elements.message.className = `message show${isError ? " error" : ""}`;
  messageTimer = setTimeout(() => { elements.message.className = "message"; }, 3500);
}

function stateLabel(state) {
  return { todo: "Todo", in_progress: "In progress", done: "Done" }[state] || state;
}

function releaseKey(task) {
  return task.release ?? "__none__";
}

function releaseLabel(release) {
  return release === "__none__" ? "Unassigned" : release;
}

function compareReleases(a, b) {
  if (a === "__none__") return 1;
  if (b === "__none__") return -1;
  if (a === "next") return 1;
  if (b === "next") return -1;
  return a.localeCompare(b, undefined, { numeric: true });
}

function updateReadOnlyUI() {
  const readOnly = isReadOnly();
  elements.readonlyToggle.checked = readOnly;

  if (serverReadOnly) {
    elements.readonlyToggle.disabled = true;
    elements.readonlySwitchContainer.classList.add("locked");
    elements.readonlyStatusText.textContent = "Read only (server)";
    elements.readonlySwitchContainer.title = "Server is running with --read-only";
  } else {
    elements.readonlyToggle.disabled = false;
    elements.readonlySwitchContainer.classList.remove("locked");
    elements.readonlyStatusText.textContent = "Read only";
    elements.readonlySwitchContainer.title = "Toggle read-only mode";
  }

  elements.newTaskBtn.hidden = readOnly;
  elements.footerMode.textContent = readOnly ? "Read only" : "Read / Write mode";
  elements.emptyEditorText.textContent = readOnly
    ? "Choose a task to view details."
    : "Choose something from the backlog, or create a new task.";

  if (readOnly && !elements.taskForm.hidden) {
    closeForm();
  } else if (currentTask && !elements.taskDetail.hidden) {
    showTaskDetail(currentTask);
  }
}

function setView(view) {
  currentView = view;
  localStorage.setItem("personal-backlog-view", view);

  if (view === "board") {
    elements.viewBoardBtn.classList.add("active");
    elements.viewBoardBtn.setAttribute("aria-pressed", "true");
    elements.viewEditorBtn.classList.remove("active");
    elements.viewEditorBtn.setAttribute("aria-pressed", "false");
    elements.boardView.hidden = false;
    elements.editorView.hidden = true;
    renderBoard();
  } else {
    elements.viewEditorBtn.classList.add("active");
    elements.viewEditorBtn.setAttribute("aria-pressed", "true");
    elements.viewBoardBtn.classList.remove("active");
    elements.viewBoardBtn.setAttribute("aria-pressed", "false");
    elements.boardView.hidden = true;
    elements.editorView.hidden = false;
    renderListTasks();
  }
}

function renderReleaseFilter() {
  const selected = elements.releaseFilter.value;
  const releases = [...new Set(tasks.map(releaseKey))].sort(compareReleases);
  elements.releaseFilter.replaceChildren(new Option("All releases", ""));
  releases.forEach((release) => {
    elements.releaseFilter.add(new Option(releaseLabel(release), release));
  });
  if (releases.includes(selected)) {
    elements.releaseFilter.value = selected;
  } else if (!defaultReleaseApplied && defaultRelease && releases.includes(defaultRelease)) {
    elements.releaseFilter.value = defaultRelease;
  }
  defaultReleaseApplied = true;
}

function taskBoardCard(task) {
  const card = elements.template.content.firstElementChild.cloneNode(true);
  card.dataset.priority = task.priority;
  card.tabIndex = 0;
  card.setAttribute("role", "button");
  card.setAttribute("aria-label", `Show details for ${task.title}`);
  card.addEventListener("click", () => openDialogTask(task.id));
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openDialogTask(task.id);
    }
  });
  card.querySelector(".task-id").textContent = task.id;
  card.querySelector(".priority").textContent = `P${task.priority}`;
  card.querySelector("h3").textContent = task.title;
  card.querySelector(".release").textContent = task.release || "Unassigned";
  card.querySelector(".size").textContent = task.size || "—";
  if (task.tags?.length) {
    const tags = card.querySelector(".tags");
    tags.hidden = false;
    tags.querySelector("dd").textContent = task.tags.join(", ");
  }
  return card;
}

function emptyLane() {
  const empty = document.createElement("p");
  empty.className = "empty-lane";
  empty.textContent = "No tasks here.";
  return empty;
}

function renderBoard() {
  const selectedRelease = elements.releaseFilter.value;
  const visible = tasks.filter((task) => !selectedRelease || releaseKey(task) === selectedRelease);

  states.forEach((state) => {
    const laneTasks = visible.filter((task) => task.state === state.key);
    const container = document.querySelector(`#${state.cards}`);
    document.querySelector(`#${state.count}`).textContent = laneTasks.length;
    container.replaceChildren(...(laneTasks.length ? laneTasks.map(taskBoardCard) : [emptyLane()]));
  });

  const releaseText = selectedRelease ? ` in ${releaseLabel(selectedRelease)}` : "";
  elements.summary.textContent = `${visible.length} task${visible.length === 1 ? "" : "s"}${releaseText} · 3 states`;
}

async function openDialogTask(id) {
  try {
    const task = await api(`/api/tasks/${encodeURIComponent(id)}`);
    renderTaskDetail(elements.dialogDetail, task, {
      onClose: () => elements.dialog.close(),
      onEdit: isReadOnly() ? null : () => {
        elements.dialog.close();
        setView("editor");
        showForm(task);
      },
    });
    elements.dialog.showModal();
  } catch (error) {
    notify(error.message, true);
  }
}

function renderListTasks() {
  const state = elements.stateFilter.value;
  const release = elements.releaseFilter.value;
  const visible = tasks.filter((task) => {
    const rKey = releaseKey(task);
    return (!state || task.state === state) && (!release || rKey === release);
  });
  elements.taskCount.textContent = `${visible.length} task${visible.length === 1 ? "" : "s"}`;
  elements.list = elements.taskList;
  elements.list.replaceChildren();

  if (!visible.length) {
    const empty = document.createElement("p");
    empty.className = "empty-list";
    empty.textContent = tasks.length ? "No tasks match these filters." : "Nothing here yet. Add the first task.";
    elements.list.append(empty);
    return;
  }

  visible.forEach((task) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = `list-card${currentTask?.id === task.id ? " active" : ""}`;
    card.addEventListener("click", () => openListTask(task.id));

    const priority = document.createElement("span");
    priority.className = "list-priority";
    priority.textContent = `P${task.priority}`;

    const titleBox = document.createElement("span");
    titleBox.className = "list-title-box";
    const title = document.createElement("strong");
    title.textContent = task.title;
    const meta = document.createElement("span");
    meta.className = "list-meta";
    meta.textContent = [task.id, task.release || "unassigned", task.size, ...(task.tags || [])].filter(Boolean).join(" · ");
    titleBox.append(title, meta);

    const statePill = document.createElement("span");
    statePill.className = `state-pill state-${task.state}`;
    statePill.textContent = stateLabel(task.state);
    card.append(priority, titleBox, statePill);
    elements.list.append(card);
  });
}

function setPreview(enabled) {
  previewing = enabled;
  elements.body.hidden = enabled;
  elements.preview.hidden = !enabled;
  elements.previewToggle.textContent = enabled ? "Edit" : "Preview";
  elements.previewToggle.setAttribute("aria-pressed", String(enabled));
  if (enabled) elements.preview.innerHTML = renderMarkdown(elements.body.value);
}

function showTaskDetail(task) {
  currentTask = task;
  elements.emptyEditor.hidden = true;
  elements.taskForm.hidden = true;
  elements.taskDetail.hidden = false;
  renderTaskDetail(elements.taskDetail, task, {
    onClose: closeForm,
    onEdit: isReadOnly() ? null : () => showForm(task),
  });
  renderListTasks();
}

async function openListTask(id) {
  try {
    const task = await api(`/api/tasks/${encodeURIComponent(id)}`);
    showTaskDetail(task);
  } catch (error) {
    notify(error.message, true);
    await refresh();
  }
}

function showForm(task = null) {
  if (isReadOnly()) {
    notify("Cannot edit in read-only mode", true);
    return;
  }
  currentTask = task;
  elements.emptyEditor.hidden = true;
  elements.taskDetail.hidden = true;
  elements.taskForm.hidden = false;
  elements.taskId.textContent = task?.id || "NEW TASK";
  elements.editorTitle.textContent = task ? "Edit task" : "Add to the backlog";
  elements.title.value = task?.title || "";
  elements.state.value = task?.state || "todo";
  elements.priority.value = task?.priority || 3;
  elements.size.value = task?.size || "";
  elements.release.value = task?.release || "";
  elements.tags.value = (task?.tags || []).join(", ");
  elements.body.value = task?.body || "";
  setPreview(false);
  elements.timestamps.textContent = task
    ? `Created ${task.created}${task.done ? ` · Done ${task.done}` : ""}`
    : "ID and timestamps are generated automatically.";
  renderListTasks();
  elements.title.focus();
  if (window.innerWidth <= 840) elements.editor.scrollIntoView({ behavior: "smooth" });
}

function closeForm() {
  currentTask = null;
  elements.taskForm.hidden = true;
  elements.taskDetail.hidden = true;
  elements.emptyEditor.hidden = false;
  renderListTasks();
}

async function saveTask(event) {
  event.preventDefault();
  if (isReadOnly()) {
    notify("Cannot save: currently in read-only mode", true);
    return;
  }
  const payload = {
    title: elements.title.value.trim(),
    state: elements.state.value,
    priority: Number(elements.priority.value),
    size: elements.size.value || null,
    release: elements.release.value.trim() || null,
    tags: elements.tags.value.split(",").map((tag) => tag.trim()).filter(Boolean),
    body: elements.body.value,
  };
  try {
    let saved;
    if (currentTask) {
      payload.revision = currentTask.revision;
      saved = await api(`/api/tasks/${encodeURIComponent(currentTask.id)}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    } else {
      saved = await api("/api/tasks", { method: "POST", body: JSON.stringify(payload) });
    }
    notify(`${saved.id} saved.`);
    await refresh();
    showTaskDetail(saved);
  } catch (error) {
    notify(error.message, true);
    if (error.message.includes("changed since") && currentTask) await openListTask(currentTask.id);
  }
}

async function refresh() {
  elements.refreshBtn.disabled = true;
  elements.refreshBtn.textContent = "Refreshing…";
  try {
    tasks = await api("/api/tasks");
    renderReleaseFilter();
    if (currentView === "board") {
      renderBoard();
    } else {
      renderListTasks();
    }
  } catch (error) {
    notify(error.message, true);
  } finally {
    elements.refreshBtn.disabled = false;
    elements.refreshBtn.textContent = "Refresh";
  }
}

// Event Listeners
elements.viewBoardBtn.addEventListener("click", () => setView("board"));
elements.viewEditorBtn.addEventListener("click", () => setView("editor"));

elements.readonlyToggle.addEventListener("change", (e) => {
  if (serverReadOnly) return;
  userReadOnly = e.target.checked;
  localStorage.setItem("personal-backlog-readonly", String(userReadOnly));
  updateReadOnlyUI();
});

elements.releaseFilter.addEventListener("change", () => {
  if (currentView === "board") renderBoard();
  else renderListTasks();
});

elements.stateFilter.addEventListener("change", renderListTasks);
elements.refreshBtn.addEventListener("click", refresh);

elements.newTaskBtn.addEventListener("click", () => {
  if (currentView !== "editor") setView("editor");
  showForm();
});

elements.taskForm.addEventListener("submit", saveTask);
elements.cancel.addEventListener("click", closeForm);
elements.close.addEventListener("click", closeForm);
elements.previewToggle.addEventListener("click", () => setPreview(!previewing));
elements.body.addEventListener("input", () => {
  if (previewing) elements.preview.innerHTML = renderMarkdown(elements.body.value);
});

// Initial Bootstrap
Promise.all([api("/api/meta"), refresh()])
  .then(([meta]) => {
    serverReadOnly = Boolean(meta.read_only);
    defaultRelease = meta.current_release || null;
    defaultReleaseApplied = false;

    elements.project.textContent = meta.project || "Project";
    elements.path.textContent = meta.backlog;
    elements.version.textContent = `· v${meta.version}`;
    document.title = `${meta.project || "Backlog"} · Personal Backlog`;

    updateReadOnlyUI();
    renderReleaseFilter();
    setView(currentView);
  })
  .catch((error) => {
    notify(error.message, true);
  });
