const states = [
  { key: "todo", cards: "todo-cards", count: "todo-count" },
  { key: "in_progress", cards: "in-progress-cards", count: "in-progress-count" },
  { key: "done", cards: "done-cards", count: "done-count" },
];

const elements = {
  project: document.querySelector("#project-name"),
  path: document.querySelector("#backlog-path"),
  release: document.querySelector("#release-filter"),
  refresh: document.querySelector("#refresh"),
  summary: document.querySelector("#summary"),
  version: document.querySelector("#version"),
  template: document.querySelector("#task-card-template"),
  dialog: document.querySelector("#task-dialog"),
  detail: document.querySelector("#task-detail"),
};

let tasks = [];
let defaultRelease = null;
let defaultReleaseApplied = false;

async function api(path) {
  const response = await fetch(path);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
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

function renderReleaseFilter() {
  const selected = elements.release.value;
  const releases = [...new Set(tasks.map(releaseKey))].sort(compareReleases);
  elements.release.replaceChildren(new Option("All releases", ""));
  releases.forEach((release) => {
    elements.release.add(new Option(releaseLabel(release), release));
  });
  if (releases.includes(selected)) {
    elements.release.value = selected;
  } else if (!defaultReleaseApplied && defaultRelease && releases.includes(defaultRelease)) {
    elements.release.value = defaultRelease;
  }
  defaultReleaseApplied = true;
}

function taskCard(task) {
  const card = elements.template.content.firstElementChild.cloneNode(true);
  card.dataset.priority = task.priority;
  card.tabIndex = 0;
  card.setAttribute("role", "button");
  card.setAttribute("aria-label", `Show details for ${task.title}`);
  card.addEventListener("click", () => openTask(task.id));
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openTask(task.id);
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

async function openTask(id) {
  try {
    const task = await api(`/api/tasks/${encodeURIComponent(id)}`);
    window.PersonalBacklogTaskDetail.render(elements.detail, task, {
      onClose: () => elements.dialog.close(),
    });
    elements.dialog.showModal();
  } catch (error) {
    elements.summary.textContent = error.message;
    elements.summary.classList.add("error");
  }
}

function emptyLane() {
  const empty = document.createElement("p");
  empty.className = "empty-lane";
  empty.textContent = "No tasks here.";
  return empty;
}

function renderBoard() {
  const selectedRelease = elements.release.value;
  const visible = tasks.filter((task) => !selectedRelease || releaseKey(task) === selectedRelease);

  states.forEach((state) => {
    const laneTasks = visible.filter((task) => task.state === state.key);
    const container = document.querySelector(`#${state.cards}`);
    document.querySelector(`#${state.count}`).textContent = laneTasks.length;
    container.replaceChildren(...(laneTasks.length ? laneTasks.map(taskCard) : [emptyLane()]));
  });

  const releaseText = selectedRelease ? ` in ${releaseLabel(selectedRelease)}` : "";
  elements.summary.textContent = `${visible.length} task${visible.length === 1 ? "" : "s"}${releaseText} · 3 states`;
}

async function refresh() {
  elements.refresh.disabled = true;
  elements.refresh.textContent = "Refreshing…";
  try {
    tasks = await api("/api/tasks");
    renderReleaseFilter();
    renderBoard();
  } catch (error) {
    elements.summary.textContent = error.message;
    elements.summary.classList.add("error");
  } finally {
    elements.refresh.disabled = false;
    elements.refresh.textContent = "Refresh";
  }
}

elements.release.addEventListener("change", renderBoard);
elements.refresh.addEventListener("click", refresh);

Promise.all([api("/api/meta"), refresh()])
  .then(([meta]) => {
    defaultRelease = meta.current_release || null;
    defaultReleaseApplied = false;
    renderReleaseFilter();
    renderBoard();
    elements.project.textContent = meta.project || "Project";
    elements.path.textContent = meta.backlog;
    elements.version.textContent = `· v${meta.version}`;
    document.title = `${meta.project || "Backlog"} board`;
  })
  .catch((error) => {
    elements.summary.textContent = error.message;
    elements.summary.classList.add("error");
  });
