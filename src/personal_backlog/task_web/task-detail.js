(function () {
  function escapeHtml(value) {
    return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;");
  }

  function renderInline(markdown) {
    let value = escapeHtml(markdown);
    value = value.replace(/`([^`]+)`/g, "<code>$1</code>");
    value = value.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    value = value.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    return value.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (match, label, href) => (
      /^(https?:\/\/|mailto:)/i.test(href)
        ? `<a href="${href}" target="_blank" rel="noopener noreferrer">${label}</a>`
        : label
    ));
  }

  function renderMarkdown(markdown) {
    const lines = markdown.replaceAll("\r\n", "\n").split("\n");
    const output = [];
    let paragraph = [];
    let listType = null;
    const flushParagraph = () => {
      if (paragraph.length) output.push(`<p>${renderInline(paragraph.join("\n")).replaceAll("\n", "<br>")}</p>`);
      paragraph = [];
    };
    const closeList = () => { if (listType) output.push(`</${listType}>`); listType = null; };
    for (const line of lines) {
      const heading = /^(#{1,3})\s+(.+)$/.exec(line);
      const unordered = /^[-*]\s+(.+)$/.exec(line);
      const ordered = /^\d+[.)]\s+(.+)$/.exec(line);
      if (heading) {
        flushParagraph(); closeList();
        const level = heading[1].length;
        output.push(`<h${level}>${renderInline(heading[2])}</h${level}>`);
      } else if (/^\s*([-*_])\1\1+\s*$/.test(line)) {
        flushParagraph(); closeList(); output.push("<hr>");
      } else if (unordered || ordered) {
        flushParagraph();
        const nextType = unordered ? "ul" : "ol";
        if (listType && listType !== nextType) closeList();
        if (!listType) { output.push(`<${nextType}>`); listType = nextType; }
        output.push(`<li>${renderInline((unordered || ordered)[1])}</li>`);
      } else if (!line.trim()) {
        flushParagraph(); closeList();
      } else {
        closeList(); paragraph.push(line);
      }
    }
    flushParagraph(); closeList();
    return output.join("") || "<p class=\"detail-empty\">No notes yet.</p>";
  }

  function stateLabel(state) {
    return { todo: "Todo", in_progress: "In progress", done: "Done" }[state] || state;
  }

  function renderTags(tags) {
    if (!tags || !tags.length) return "";
    return `<div class="detail-tags"><dt>Tags</dt><dd>${tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}</dd></div>`;
  }

  function render(container, task, options = {}) {
    const actions = [
      options.onClose ? '<button class="detail-close secondary" type="button">Close</button>' : "",
      options.onEdit ? '<button class="detail-edit primary" type="button">Edit</button>' : "",
    ].join("");
    container.innerHTML = `
      <section class="task-detail" aria-label="Task details">
        <div class="detail-heading">
          <div><p class="detail-id">${escapeHtml(task.id)}</p><h2>${escapeHtml(task.title)}</h2></div>
          <div class="detail-actions">${actions}</div>
        </div>
        <dl class="detail-meta">
          <div><dt>State</dt><dd>${escapeHtml(stateLabel(task.state))}</dd></div>
          <div><dt>Priority</dt><dd>P${task.priority}</dd></div>
          <div><dt>Size</dt><dd>${escapeHtml(task.size || "None")}</dd></div>
          <div><dt>Release</dt><dd>${escapeHtml(task.release || "Unassigned")}</dd></div>
          ${renderTags(task.tags)}
        </dl>
        <article class="detail-body markdown-preview">${renderMarkdown(task.body || "")}</article>
        <p class="detail-timestamps">Created ${escapeHtml(task.created)}${task.done ? ` · Done ${escapeHtml(task.done)}` : ""}</p>
      </section>`;
    if (options.onClose) container.querySelector(".detail-close").addEventListener("click", options.onClose);
    if (options.onEdit) container.querySelector(".detail-edit").addEventListener("click", options.onEdit);
  }

  window.PersonalBacklogTaskDetail = { render, renderMarkdown };
}());
