(() => {
  const $ = (s) => document.querySelector(s);
  const state = { tab: "all", priority: "", date: "", search: "", page: 1, perPage: 10, total: 0 };
  let editingId = null, deletingId = null, searchTimer;

  // ---------- API ----------
  async function api(path, options = {}) {
    const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
    let data = null;
    try { data = await res.json(); } catch (_) {}
    if (!res.ok) throw data || { error: "Something went wrong. Please try again." };
    return data;
  }

  // ---------- helpers ----------
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = (iso) => (iso ? iso.split("-").reverse().join("/") : "—");
  function toast(msg, isError = false) {
    const t = $("#toast");
    t.textContent = msg;
    t.classList.toggle("err", isError);
    t.classList.add("show");
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => t.classList.remove("show"), 2600);
  }

  const ICON = {
    doc: '<svg viewBox="0 0 24 24"><path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4M12 11v5M9.8 14l2.2 2.2 2.2-2.2"/></svg>',
    edit: '<svg viewBox="0 0 24 24"><path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16z"/><path d="m13.5 6.5 4 4"/></svg>',
    del: '<svg viewBox="0 0 24 24"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/></svg>',
    eye: '<svg viewBox="0 0 24 24"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>',
    dots: '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><circle cx="12" cy="5" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="12" cy="19" r="1.8"/></svg>',
  };
  const cache = {};

  // ---------- load + render ----------
  function query() {
    const p = new URLSearchParams({ page: state.page, per_page: state.perPage });
    if (state.tab === "Pending" || state.tab === "Completed") p.set("status", state.tab);
    if (state.tab === "overdue") p.set("overdue", "true");
    if (state.priority) p.set("priority", state.priority);
    if (state.date) p.set("deadline", state.date);
    if (state.search) p.set("search", state.search);
    return p.toString();
  }

  async function load() {
    try {
      const data = await api("/api/tasks?" + query());
      state.total = data.total;
      // if the current page no longer exists (e.g. last item deleted), step back
      if (!data.items.length && state.page > 1) { state.page--; return load(); }
      render(data);
    } catch (e) {
      toast(e.error || "Could not load tasks.", true);
    }
  }

  function render(data) {
    data.items.forEach((t) => (cache[t.id] = t));
    $("#rows").innerHTML = data.items.map((t) => {
      const done = t.status === "Completed";
      const statusLabel = t.overdue ? "Overdue" : t.status;
      const btn = (act, cls, title, icon) =>
        `<button class="act ${cls}" data-act="${act}" data-id="${t.id}" title="${title}" aria-label="${title}">${icon}</button>`;
      return `<tr class="${done ? "done" : ""}">
        <td class="title">${esc(t.title)}</td>
        <td><span class="pill p-${t.priority}">${t.priority}</span></td>
        <td><span class="pill s-${statusLabel}">${statusLabel}</span></td>
        <td>${esc(t.created_by)}</td>
        <td>${fmt(t.created_at)}</td>
        <td class="${t.overdue ? "due-over" : ""}">${fmt(t.deadline)}</td>
        <td><div class="actions">
          ${btn("download", "doc", "Download task", ICON.doc)}
          ${done ? btn("view", "eye", "View details", ICON.eye)
                 : btn("edit", "edit", "Edit task", ICON.edit) + btn("delete", "del", "Delete task", ICON.del)}
          ${btn("menu", "dots", "More actions", ICON.dots)}
        </div></td></tr>`;
    }).join("");

    $("#empty").hidden = data.items.length > 0;
    const start = data.total ? (data.page - 1) * data.per_page + 1 : 0;
    const end = Math.min(data.page * data.per_page, data.total);
    $("#range").textContent = `${start}-${end} of ${data.total}`;
    $("#prevBtn").disabled = data.page <= 1;
    $("#nextBtn").disabled = end >= data.total;
    const badge = $("#bellBadge");
    badge.hidden = !data.overdue_count;
    badge.textContent = data.overdue_count;
  }

  // ---------- tabs / nav ----------
  function setTab(tab) {
    state.tab = tab; state.page = 1;
    document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
    document.querySelectorAll(".side-btn[data-nav]").forEach((b) => b.classList.toggle("active", b.dataset.nav === tab));
    load();
  }
  document.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.tab)));
  document.querySelectorAll(".side-btn[data-nav]").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.nav)));
  $("#bellBtn").addEventListener("click", () => setTab("overdue"));

  // ---------- filters / search / paging ----------
  $("#filterBtn").addEventListener("click", () => {
    state.priority = $("#priorityFilter").value;
    state.date = $("#dateFilter").value;
    state.page = 1; load();
  });
  $("#resetBtn").addEventListener("click", () => {
    $("#priorityFilter").value = ""; $("#dateFilter").value = ""; $("#searchInput").value = "";
    state.priority = state.date = state.search = "";
    setTab("all");
  });
  $("#searchBtn").addEventListener("click", () => {
    const wrap = $("#searchWrap");
    wrap.classList.toggle("open");
    if (wrap.classList.contains("open")) $("#searchInput").focus();
  });
  $("#searchInput").addEventListener("input", (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { state.search = e.target.value.trim(); state.page = 1; load(); }, 250);
  });
  $("#perPage").addEventListener("change", (e) => { state.perPage = +e.target.value; state.page = 1; load(); });
  $("#prevBtn").addEventListener("click", () => { state.page--; load(); });
  $("#nextBtn").addEventListener("click", () => { state.page++; load(); });

  // ---------- row actions ----------
  const menu = $("#rowMenu");
  const closeMenu = () => { menu.hidden = true; };

  async function toggleStatus(t) {
    const next = t.status === "Completed" ? "Pending" : "Completed";
    try {
      await api(`/api/tasks/${t.id}`, { method: "PATCH", body: JSON.stringify({ status: next }) });
      toast(next === "Completed" ? "Task marked as completed" : "Task marked as pending");
      load();
    } catch (err) { toast(err.error, true); }
  }
  function askDelete(t) {
    deletingId = t.id;
    $("#delText").textContent = `“${t.title}” will be removed permanently.`;
    $("#deleteModal").hidden = false;
  }
  function viewTask(t) {
    const rows = [
      ["Title", t.title], ["Description", t.description || "—"], ["Priority", t.priority],
      ["Status", t.overdue ? "Overdue" : t.status], ["Created by", t.created_by],
      ["Date assigned", fmt(t.created_at)], ["Due date", fmt(t.deadline)],
    ];
    $("#viewBody").innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("");
    $("#viewModal").hidden = false;
  }
  function download(t) {
    const text = [`Title: ${t.title}`, `Description: ${t.description || "-"}`, `Priority: ${t.priority}`,
      `Status: ${t.status}`, `Created by: ${t.created_by}`, `Date assigned: ${fmt(t.created_at)}`,
      `Due date: ${fmt(t.deadline)}`].join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
    a.download = `task-${t.id}.txt`;
    a.click();
    URL.revokeObjectURL(a.href);
  }
  const run = {
    download, view: viewTask, edit: openTaskModal, delete: askDelete, toggle: toggleStatus,
  };

  function openMenu(btn, t) {
    const done = t.status === "Completed";
    menu.innerHTML = [
      ["view", "View details"], ["toggle", done ? "Mark as pending" : "Mark as completed"],
      ["edit", "Edit task"], ["delete", "Delete task"],
    ].map(([a, l]) => `<button data-menu="${a}" class="${a === "delete" ? "danger" : ""}">${l}</button>`).join("");
    menu.hidden = false;
    const r = btn.getBoundingClientRect();
    const w = menu.offsetWidth, h = menu.offsetHeight;
    menu.style.left = Math.max(8, Math.min(r.right - w, window.innerWidth - w - 8)) + "px";
    const below = r.bottom + 6 + h <= window.innerHeight;
    menu.style.top = (below ? r.bottom + 6 : r.top - h - 6) + "px";
    menu.dataset.id = t.id;
  }
  menu.addEventListener("click", (e) => {
    const b = e.target.closest("[data-menu]");
    if (!b) return;
    const t = cache[menu.dataset.id];
    closeMenu();
    if (t) run[b.dataset.menu](t);
  });
  document.addEventListener("click", (e) => { if (!e.target.closest("#rowMenu, [data-act=menu]")) closeMenu(); });
  window.addEventListener("scroll", closeMenu, true);
  window.addEventListener("resize", closeMenu);

  $("#rows").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-act]");
    if (!btn) return;
    const t = cache[btn.dataset.id];
    if (!t) return;
    if (btn.dataset.act === "menu") {
      if (!menu.hidden && menu.dataset.id === String(t.id)) return closeMenu();
      return openMenu(btn, t);
    }
    run[btn.dataset.act](t);
  });

  $("#confirmDelete").addEventListener("click", async () => {
    try {
      await api(`/api/tasks/${deletingId}`, { method: "DELETE" });
      closeModals(); toast("Task deleted"); load();
    } catch (err) { toast(err.error, true); }
  });

  // ---------- modal / form ----------
  const fields = { title: "#fTitle", description: "#fDesc", deadline: "#fDeadline", created_by: "#fCreatedBy" };
  function clearErrors() {
    document.querySelectorAll(".error").forEach((el) => (el.textContent = ""));
    document.querySelectorAll(".modal .invalid").forEach((el) => el.classList.remove("invalid"));
  }
  function showErrors(errors) {
    Object.entries(errors).forEach(([k, msg]) => {
      const el = document.getElementById("e" + k[0].toUpperCase() + k.slice(1));
      if (el) el.textContent = msg;
      if (fields[k]) $(fields[k]).classList.add("invalid");
    });
  }
  function openTaskModal(task = null) {
    clearErrors();
    editingId = task ? task.id : null;
    $("#modalTitle").textContent = task ? "Edit Task" : "Create New Task";
    $("#fTitle").value = task?.title ?? "";
    $("#fDesc").value = task?.description ?? "";
    $("#fDeadline").value = task?.deadline ?? "";
    $("#fCreatedBy").value = task && task.created_by !== "Me" ? task.created_by : "";
    $("#fPriority").value = task?.priority ?? "Medium";
    $("#fStatus").value = task?.status ?? "Pending";
    $("#taskModal").hidden = false;
    $("#fTitle").focus();
  }
  function closeModals() {
    $("#taskModal").hidden = true; $("#deleteModal").hidden = true; $("#viewModal").hidden = true; closeMenu();
    editingId = deletingId = null;
  }
  $("#newBtn").addEventListener("click", () => openTaskModal());
  document.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", closeModals));
  document.querySelectorAll(".overlay").forEach((o) => o.addEventListener("mousedown", (e) => { if (e.target === o) closeModals(); }));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModals(); });

  $("#taskForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    clearErrors();
    const body = {
      title: $("#fTitle").value.trim(),
      description: $("#fDesc").value.trim(),
      deadline: $("#fDeadline").value || null,
      created_by: $("#fCreatedBy").value.trim(),
      priority: $("#fPriority").value,
      status: $("#fStatus").value,
    };
    if (!body.title) return showErrors({ title: "Task title cannot be empty." });
    const btn = $("#saveBtn"); btn.disabled = true;
    try {
      const wasEditing = !!editingId;
      if (wasEditing) await api(`/api/tasks/${editingId}`, { method: "PUT", body: JSON.stringify(body) });
      else await api("/api/tasks", { method: "POST", body: JSON.stringify(body) });
      toast(wasEditing ? "Task updated" : "Task created");
      closeModals(); load();
    } catch (err) {
      if (err.errors) showErrors(err.errors); else toast(err.error || "Could not save task.", true);
    } finally { btn.disabled = false; }
  });

  // ---------- theme ----------
  const applyTheme = (t) => document.documentElement.setAttribute("data-theme", t);
  let saved = "light";
  try { saved = localStorage.getItem("theme") || "light"; } catch (_) {}
  applyTheme(saved);
  $("#themeBtn").addEventListener("click", () => {
    const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    applyTheme(next);
    try { localStorage.setItem("theme", next); } catch (_) {}
  });

  load();
})();
