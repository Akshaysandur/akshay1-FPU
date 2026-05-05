const STORAGE_KEY = "fpu_independent_state_v1";
const IST_TIMEZONE = "Asia/Kolkata";

const OPERATION_CATALOG = [
  { name: "Drilling", machine: "Machine 1", minutes: 8, description: "Basic drilling" },
  { name: "Turning", machine: "Machine 2", minutes: 7, description: "Lathe turning" },
  { name: "Assembly", machine: "Machine 3", minutes: 10, description: "Manual assembly" },
  { name: "Inspection", machine: "Machine 4", minutes: 6, description: "Quality inspection" },
  { name: "Welding", machine: "Machine 5", minutes: 12, description: "Welding and joining" },
];

const FPU_INFO = [
  ["Scheduler", "Static / Dynamic"],
  ["Loading", "Zero time"],
  ["Unloading", "Zero time"],
  ["Execution", "Step-by-step order progress"],
];

const defaultState = {
  activeTab: "orders",
  schedulerMode: "Dynamic",
  nextOrderNo: 1,
  selectedOrderId: "",
  executionFocusOrder: "",
  orderLocked: false,
  fieldHistory: { customer: [], item_name: [], notes: [] },
  metadata: {
    customer: "",
    itemName: "",
    dueDate: istDate(),
    notes: "",
    priority: 3,
  },
  operationPicker: OPERATION_CATALOG[0].name,
  operationMinutesByName: Object.fromEntries(OPERATION_CATALOG.map((op) => [op.name, op.minutes])),
  draftOps: [],
  orders: [],
  lastSaved: "Never",
};

let state = normalizeState(loadState());

const el = {
  liveClock: document.getElementById("liveClock"),
  sidebarMode: document.getElementById("sidebarMode"),
  sidebarNextOrder: document.getElementById("sidebarNextOrder"),
  sidebarIstDate: document.getElementById("sidebarIstDate"),
  sidebarLastSaved: document.getElementById("sidebarLastSaved"),
  summaryGrid: document.getElementById("summaryGrid"),
  orderIdField: document.getElementById("orderIdField"),
  customerField: document.getElementById("customerField"),
  itemNameField: document.getElementById("itemNameField"),
  dueDateField: document.getElementById("dueDateField"),
  priorityField: document.getElementById("priorityField"),
  priorityValue: document.getElementById("priorityValue"),
  notesField: document.getElementById("notesField"),
  operationPicker: document.getElementById("operationPicker"),
  machineField: document.getElementById("machineField"),
  timeField: document.getElementById("timeField"),
  customerSuggestions: document.getElementById("customerSuggestions"),
  itemSuggestions: document.getElementById("itemSuggestions"),
  notesSuggestions: document.getElementById("notesSuggestions"),
  catalogTable: document.getElementById("catalogTable"),
  catalogTableFull: document.getElementById("catalogTableFull"),
  basicsTable: document.getElementById("basicsTable"),
  draftPreview: document.getElementById("draftPreview"),
  ordersTable: document.getElementById("ordersTable"),
  orderDetails: document.getElementById("orderDetails"),
  queueTable: document.getElementById("queueTable"),
  executionList: document.getElementById("executionList"),
  modeStaticBtn: document.getElementById("modeStaticBtn"),
  modeDynamicBtn: document.getElementById("modeDynamicBtn"),
  tabButtons: Array.from(document.querySelectorAll(".tab-btn")),
  tabPanels: {
    orders: document.getElementById("tab-orders"),
    scheduling: document.getElementById("tab-scheduling"),
    execution: document.getElementById("tab-execution"),
    catalog: document.getElementById("tab-catalog"),
  },
  addOperationBtn: document.getElementById("addOperationBtn"),
  clearDraftBtn: document.getElementById("clearDraftBtn"),
  finishOrderBtn: document.getElementById("finishOrderBtn"),
  runSchedulerBtn: document.getElementById("runSchedulerBtn"),
  timeUpBtn: document.getElementById("timeUpBtn"),
  timeDownBtn: document.getElementById("timeDownBtn"),
};

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function normalizeState(incoming) {
  const merged = structuredClone(defaultState);
  if (!incoming) return merged;

  merged.activeTab = incoming.activeTab || merged.activeTab;
  merged.schedulerMode = incoming.schedulerMode || merged.schedulerMode;
  merged.nextOrderNo = Number.isFinite(incoming.nextOrderNo) ? incoming.nextOrderNo : merged.nextOrderNo;
  merged.selectedOrderId = incoming.selectedOrderId || "";
  merged.executionFocusOrder = incoming.executionFocusOrder || "";
  merged.orderLocked = Boolean(incoming.orderLocked);
  merged.lastSaved = incoming.lastSaved || merged.lastSaved;

  if (incoming.metadata) {
    merged.metadata.customer = String(incoming.metadata.customer || "");
    merged.metadata.itemName = String(incoming.metadata.itemName || "");
    merged.metadata.dueDate = String(incoming.metadata.dueDate || istDate());
    merged.metadata.notes = String(incoming.metadata.notes || "");
    merged.metadata.priority = clampInt(incoming.metadata.priority ?? 3, 1, 5);
  }

  if (incoming.operationPicker && OPERATION_CATALOG.some((op) => op.name === incoming.operationPicker)) {
    merged.operationPicker = incoming.operationPicker;
  }

  if (incoming.operationMinutesByName) {
    for (const op of OPERATION_CATALOG) {
      const value = incoming.operationMinutesByName[op.name];
      merged.operationMinutesByName[op.name] = clampInt(value ?? op.minutes, 1, 99);
    }
  }

  if (Array.isArray(incoming.draftOps)) {
    merged.draftOps = incoming.draftOps
      .map((op) => ({
        name: OPERATION_CATALOG.some((entry) => entry.name === op.name) ? op.name : OPERATION_CATALOG[0].name,
        minutes: clampInt(op.minutes ?? 1, 1, 99),
      }))
      .filter((op) => op.name);
  }

  if (Array.isArray(incoming.orders)) {
    merged.orders = incoming.orders.map(normalizeOrder);
  }

  if (incoming.fieldHistory && typeof incoming.fieldHistory === "object") {
    merged.fieldHistory = {
      customer: sanitizeHistory(incoming.fieldHistory.customer),
      item_name: sanitizeHistory(incoming.fieldHistory.item_name),
      notes: sanitizeHistory(incoming.fieldHistory.notes),
    };
  }

  return merged;
}

function normalizeOrder(order) {
  return {
    orderId: String(order.orderId || order.order_id || ""),
    customer: String(order.customer || ""),
    itemName: String(order.itemName || order.item_name || ""),
    priority: clampInt(order.priority ?? 3, 1, 5),
    createdAt: Number(order.createdAt || order.created_at || Date.now()),
    dueDate: String(order.dueDate || order.due_date || ""),
    notes: String(order.notes || ""),
    status: String(order.status || "Queued"),
    currentStepIndex: clampInt(order.currentStepIndex ?? 0, 0, 999),
    queueSecondsRemaining: clampInt(order.queueSecondsRemaining ?? order.queue_seconds_remaining ?? 0, 0, 9999),
    operations: Array.isArray(order.operations)
      ? order.operations.map((step) => ({
          name: String(step.name || ""),
          machine: String(step.machine || ""),
          minutes: clampInt(step.minutes ?? 0, 0, 999),
          status: String(step.status || "Pending"),
        }))
      : [],
  };
}

function sanitizeHistory(list) {
  if (!Array.isArray(list)) return [];
  const cleaned = [];
  for (const item of list) {
    const value = String(item || "").trim();
    if (!value) continue;
    if (!/^[A-Za-z][A-Za-z\s.'/-]*$/.test(value)) continue;
    if (!cleaned.includes(value)) cleaned.push(value);
  }
  return cleaned.slice(0, 12);
}

function persistState() {
  state.lastSaved = formatISTDateTime(new Date());
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  renderSidebar();
}

function istDate(date = new Date()) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: IST_TIMEZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

function istDateTime(date = new Date()) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone: IST_TIMEZONE,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    })
      .formatToParts(date)
      .map((part) => [part.type, part.value]),
  );
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second}`;
}

function formatISTDateTime(date) {
  return `${istDateTime(date)} IST`;
}

function clampInt(value, min, max) {
  const num = Number.parseInt(value, 10);
  if (Number.isNaN(num)) return min;
  return Math.max(min, Math.min(max, num));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function currentOperationTemplate() {
  return OPERATION_CATALOG.find((op) => op.name === state.operationPicker) || OPERATION_CATALOG[0];
}

function setTab(tabName) {
  state.activeTab = tabName;
  persistState();
  renderTabs();
}

function renderTabs() {
  el.tabButtons.forEach((btn) => {
    const active = btn.dataset.tab === state.activeTab;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-selected", active ? "true" : "false");
  });
  Object.entries(el.tabPanels).forEach(([tab, panel]) => {
    panel.classList.toggle("active", tab === state.activeTab);
  });
}

function recordHistory(fieldName, value) {
  const cleaned = String(value || "").trim();
  if (!cleaned || !/^[A-Za-z][A-Za-z\s.'/-]*$/.test(cleaned)) return;
  const list = state.fieldHistory[fieldName] || (state.fieldHistory[fieldName] = []);
  if (!list.includes(cleaned)) {
    list.push(cleaned);
    list.splice(12);
  }
}

function matchingHistory(fieldName, currentValue) {
  const prefix = String(currentValue || "").trim().toLowerCase();
  if (!prefix) return [];
  return (state.fieldHistory[fieldName] || [])
    .filter((value) => value.toLowerCase().startsWith(prefix))
    .slice(0, 6);
}

function renderSuggestions(container, fieldName, currentValue, setter) {
  const matches = matchingHistory(fieldName, currentValue);
  container.innerHTML = matches.length
    ? matches.map((match) => `<button class="chip" type="button" data-suggest-for="${fieldName}" data-value="${escapeHtml(match)}">${escapeHtml(match)}</button>`).join("")
    : "";
  container.dataset.targetSetter = setter;
}

function renderSidebar() {
  el.sidebarMode.textContent = state.schedulerMode;
  el.sidebarNextOrder.textContent = `ORD-${String(state.nextOrderNo).padStart(3, "0")}`;
  el.sidebarIstDate.textContent = istDate();
  el.sidebarLastSaved.textContent = state.lastSaved;
  el.liveClock.textContent = `IST ${istDateTime(new Date()).slice(11, 16)}`;
}

function renderSummary() {
  const totalOrders = state.orders.length;
  const activeOrders = state.orders.filter((order) => !["Completed", "Cancelled"].includes(order.status)).length;
  const focusOrder = state.executionFocusOrder || state.selectedOrderId || "None";
  const cards = [
    ["Orders", totalOrders, "Created in this session"],
    ["Active Jobs", activeOrders, "Waiting or running now"],
    ["Focused Job", focusOrder, "Execution selection"],
    ["IST Clock", istDateTime(new Date()).slice(0, 16), "Auto-filled due date source"],
  ];

  const classes = ["summary-card", "summary-card", "summary-card", "summary-card"];
  el.summaryGrid.innerHTML = cards
    .map(
      ([label, value, foot], index) => `
        <div class="${classes[index]}">
          <div class="summary-label">${escapeHtml(label)}</div>
          <div class="summary-value">${escapeHtml(value)}</div>
          <div class="summary-foot">${escapeHtml(foot)}</div>
        </div>`,
    )
    .join("");
}

function renderFields() {
  el.orderIdField.value = `ORD-${String(state.nextOrderNo).padStart(3, "0")}`;
  el.customerField.value = state.metadata.customer;
  el.itemNameField.value = state.metadata.itemName;
  el.dueDateField.value = state.metadata.dueDate;
  el.priorityField.value = String(state.metadata.priority);
  el.priorityValue.textContent = String(state.metadata.priority);
  el.notesField.value = state.metadata.notes;
  el.operationPicker.innerHTML = OPERATION_CATALOG.map((op) => `<option value="${escapeHtml(op.name)}">${escapeHtml(op.name)}</option>`).join("");
  el.operationPicker.value = state.operationPicker;
  el.machineField.value = currentOperationTemplate().machine;
  el.timeField.value = `${state.operationMinutesByName[state.operationPicker]} min`;

  renderSuggestions(el.customerSuggestions, "customer", state.metadata.customer, "customerField");
  renderSuggestions(el.itemSuggestions, "item_name", state.metadata.itemName, "itemNameField");
  renderSuggestions(el.notesSuggestions, "notes", state.metadata.notes, "notesField");
}

function renderCatalogTables() {
  const headers = `<thead><tr><th>Operation</th><th>Machine</th><th>Time</th><th>Description</th></tr></thead>`;
  const body = `<tbody>${OPERATION_CATALOG.map((op) => `<tr><td>${escapeHtml(op.name)}</td><td>${escapeHtml(op.machine)}</td><td>${op.minutes}</td><td>${escapeHtml(op.description)}</td></tr>`).join("")}</tbody>`;
  const html = headers + body;
  el.catalogTable.innerHTML = html;
  el.catalogTableFull.innerHTML = html;
  el.basicsTable.innerHTML = `<thead><tr><th>Item</th><th>Value</th></tr></thead><tbody>${FPU_INFO.map(([k, v]) => `<tr><td>${escapeHtml(k)}</td><td>${escapeHtml(v)}</td></tr>`).join("")}</tbody>`;
}

function renderDraft() {
  if (!state.draftOps.length) {
    el.draftPreview.innerHTML = `<div class="details-empty">No operations added yet.</div>`;
    return;
  }

  const rows = [
    { seq: 0, step: "Loading", machine: "-", time: 0 },
    ...state.draftOps.map((op, index) => {
      const template = OPERATION_CATALOG.find((item) => item.name === op.name) || OPERATION_CATALOG[0];
      return { seq: index + 1, step: template.name, machine: template.machine, time: op.minutes };
    }),
    { seq: state.draftOps.length + 1, step: "Unloading", machine: "-", time: 0 },
  ];
  el.draftPreview.innerHTML = `<table class="data-table"><thead><tr><th>Seq</th><th>Step</th><th>Machine</th><th>Time (min)</th></tr></thead><tbody>${rows
    .map((row) => `<tr><td>${row.seq}</td><td>${escapeHtml(row.step)}</td><td>${escapeHtml(row.machine)}</td><td>${row.time}</td></tr>`)
    .join("")}</tbody></table>`;
}

function sortOrders() {
  const orders = [...state.orders];
  if (state.schedulerMode === "Static") {
    return orders.sort((a, b) => orderNumber(a.orderId) - orderNumber(b.orderId));
  }
  return orders.sort((a, b) => {
    if (a.priority !== b.priority) return b.priority - a.priority;
    if (a.createdAt !== b.createdAt) return a.createdAt - b.createdAt;
    return orderNumber(a.orderId) - orderNumber(b.orderId);
  });
}

function orderNumber(orderId) {
  const match = /(\d+)$/.exec(orderId || "");
  return match ? Number.parseInt(match[1], 10) : 0;
}

function nextStep(order) {
  if (order.currentStepIndex < order.operations.length) {
    const step = order.operations[order.currentStepIndex];
    return `${step.name} / ${step.machine}`;
  }
  return "Unloading";
}

function queueSummary(order) {
  return {
    orderId: order.orderId,
    customer: order.customer,
    itemName: order.itemName,
    priority: order.priority,
    ops: order.operations.length,
    status: order.status,
    nextStep: nextStep(order),
    queueTime: `${order.queueSecondsRemaining}s`,
  };
}

function renderOrdersTable() {
  const orders = sortOrders();
  if (!orders.length) {
    el.ordersTable.innerHTML = `<thead><tr><th>Order ID</th><th>Customer</th><th>Item</th><th>Priority</th><th>Ops</th><th>Status</th><th>Next Step</th><th>Queue Time</th></tr></thead><tbody><tr><td colspan="8">No orders created yet.</td></tr></tbody>`;
    el.orderDetails.className = "details-empty";
    el.orderDetails.textContent = "Select an order row to inspect the details and route flow.";
    return;
  }

  el.ordersTable.innerHTML = `<thead><tr><th>Order ID</th><th>Customer</th><th>Item</th><th>Priority</th><th>Ops</th><th>Status</th><th>Next Step</th><th>Queue Time</th></tr></thead><tbody>${orders
    .map((order) => {
      const selected = order.orderId === state.selectedOrderId ? "selected" : "";
      const summary = queueSummary(order);
      return `<tr class="${selected}" data-order-id="${escapeHtml(order.orderId)}"><td><strong>${escapeHtml(summary.orderId)}</strong></td><td>${escapeHtml(summary.customer)}</td><td>${escapeHtml(summary.itemName)}</td><td>${summary.priority}</td><td>${summary.ops}</td><td>${escapeHtml(summary.status)}</td><td>${escapeHtml(summary.nextStep)}</td><td>${escapeHtml(summary.queueTime)}</td></tr>`;
    })
    .join("")}</tbody>`;
}

function currentRouteIndex(order) {
  if (order.status === "Completed") return order.operations.length + 1;
  if (order.status === "Unloading") return order.operations.length + 1;
  return Math.min(order.currentStepIndex, order.operations.length);
}

function renderOrderDetails() {
  const order = state.orders.find((item) => item.orderId === state.selectedOrderId);
  if (!order) {
    el.orderDetails.className = "details-empty";
    el.orderDetails.textContent = "Select an order row to inspect the details and route flow.";
    return;
  }

  const detailRows = [
    ["Customer", order.customer],
    ["Item", order.itemName],
    ["Priority", order.priority],
    ["Status", order.status],
    ["Created", formatISTDateTime(new Date(order.createdAt))],
    ["Due Date", order.dueDate || "--"],
  ];

  const nodes = [
    { seq: 0, step: "Loading", machine: "-", status: "Fixed", current: order.status !== "Completed" && order.currentStepIndex === 0 },
    ...order.operations.map((step, index) => ({
      seq: index + 1,
      step: step.name,
      machine: step.machine,
      status: step.status,
      current: order.status !== "Completed" && order.status !== "Cancelled" && order.currentStepIndex === index + 1,
    })),
    { seq: order.operations.length + 1, step: "Unloading", machine: "-", status: "Fixed", current: order.status === "Unloading" || order.status === "Completed" },
  ];

  el.orderDetails.className = "";
  el.orderDetails.innerHTML = `
    <div class="details-grid">
      <section class="panel" style="margin:0;">
        <h2>Order Details</h2>
        <div class="detail-list">
          ${detailRows.map(([label, value]) => `<div class="detail-item"><strong>${escapeHtml(label)}:</strong><span>${escapeHtml(value)}</span></div>`).join("")}
        </div>
      </section>
      <section class="panel" style="margin:0;">
        <h2>Route Flow</h2>
        <div class="route-flow">
          ${nodes
            .map(
              (node, index) => `
                <div class="route-node ${node.current ? "current" : ""}">
                  <div class="route-seq">Seq ${node.seq}</div>
                  <div class="route-step">${escapeHtml(node.step)}</div>
                  <div class="route-machine">${escapeHtml(node.machine)}</div>
                  <div class="route-status">Status: ${escapeHtml(node.status)}</div>
                </div>
                ${index < nodes.length - 1 ? `<div class="route-arrow">➜</div>` : ""}
              `,
            )
            .join("")}
        </div>
      </section>
    </div>`;
}

function renderQueueTable() {
  const orders = sortOrders();
  el.queueTable.innerHTML = `<thead><tr><th>Order ID</th><th>Customer</th><th>Item</th><th>Priority</th><th>Ops</th><th>Status</th><th>Next Step</th><th>Queue Time</th></tr></thead><tbody>${orders
    .map((order) => {
      const summary = queueSummary(order);
      return `<tr><td><strong>${escapeHtml(summary.orderId)}</strong></td><td>${escapeHtml(summary.customer)}</td><td>${escapeHtml(summary.itemName)}</td><td>${summary.priority}</td><td>${summary.ops}</td><td>${escapeHtml(summary.status)}</td><td>${escapeHtml(summary.nextStep)}</td><td>${escapeHtml(summary.queueTime)}</td></tr>`;
    })
    .join("")}</tbody>`;
}

function renderExecutionList() {
  const orders = sortOrders().filter((order) => !["Completed", "Cancelled"].includes(order.status));
  if (!orders.length) {
    el.executionList.innerHTML = `<div class="details-empty">No active orders available.</div>`;
    return;
  }

  el.executionList.innerHTML = orders
    .map((order) => {
      const focused = order.orderId === state.executionFocusOrder;
      const progress = order.operations.length ? Math.round((order.currentStepIndex / order.operations.length) * 100) : 0;
      return `
        <div class="execution-card ${focused ? "focused" : ""}" data-exec-id="${escapeHtml(order.orderId)}">
          <div class="execution-header">
            <div>${focused ? `Active Order: ${escapeHtml(order.orderId)}` : escapeHtml(order.orderId)}</div>
            <div>${escapeHtml(order.status)}</div>
          </div>
          <div class="execution-meta">
            <div><strong>Customer:</strong> ${escapeHtml(order.customer)}</div>
            <div><strong>Item:</strong> ${escapeHtml(order.itemName)}</div>
            <div><strong>Current Step:</strong> ${escapeHtml(nextStep(order))}</div>
            <div><strong>Queue Time Remaining:</strong> ${escapeHtml(`${order.queueSecondsRemaining}s`)}</div>
          </div>
          <div class="progress-bar"><div class="progress-fill" style="width:${progress}%"></div></div>
          <div class="execution-actions">
            ${
              focused
                ? `
                  <button class="btn" type="button" data-action="previous" data-order-id="${escapeHtml(order.orderId)}">Previous</button>
                  <button class="btn" type="button" data-action="advance" data-order-id="${escapeHtml(order.orderId)}">Advance</button>
                  <button class="btn" type="button" data-action="complete" data-order-id="${escapeHtml(order.orderId)}">Complete</button>
                `
                : `<button class="btn" type="button" data-action="focus" data-order-id="${escapeHtml(order.orderId)}">Focus</button>`
            }
          </div>
        </div>
      `;
    })
    .join("");
}

function setDefaultOperationMinutes(name) {
  const template = OPERATION_CATALOG.find((op) => op.name === name) || OPERATION_CATALOG[0];
  if (!(name in state.operationMinutesByName)) {
    state.operationMinutesByName[name] = template.minutes;
  }
  state.operationPicker = name;
}

function addOperation() {
  state.draftOps.push({
    name: state.operationPicker,
    minutes: clampInt(state.operationMinutesByName[state.operationPicker], 1, 99),
  });
  state.orderLocked = true;
  persistState();
  renderAll();
}

function clearDraft() {
  state.draftOps = [];
  state.orderLocked = false;
  persistState();
  renderAll();
}

function finishOrder() {
  if (!state.metadata.customer.trim() || !state.metadata.itemName.trim() || !state.draftOps.length) {
    alert("Fill metadata and add at least one operation before finishing.");
    return;
  }

  const orderId = `ORD-${String(state.nextOrderNo).padStart(3, "0")}`;
  const newOrder = {
    orderId,
    customer: state.metadata.customer.trim(),
    itemName: state.metadata.itemName.trim(),
    priority: state.metadata.priority,
    createdAt: Date.now(),
    dueDate: state.metadata.dueDate,
    notes: state.metadata.notes.trim(),
    status: "Queued",
    currentStepIndex: 0,
    queueSecondsRemaining: 0,
    operations: state.draftOps.map((op) => {
      const template = OPERATION_CATALOG.find((entry) => entry.name === op.name) || OPERATION_CATALOG[0];
      return {
        name: template.name,
        machine: template.machine,
        minutes: clampInt(op.minutes, 1, 99),
        status: "Pending",
      };
    }),
  };

  state.orders.push(newOrder);
  state.selectedOrderId = newOrder.orderId;
  state.executionFocusOrder = newOrder.orderId;
  state.nextOrderNo += 1;
  recordHistory("customer", state.metadata.customer);
  recordHistory("item_name", state.metadata.itemName);
  recordHistory("notes", state.metadata.notes);
  state.draftOps = [];
  state.orderLocked = true;
  persistState();
  renderAll();
  alert(`Order ${orderId} added.`);
}

function runScheduler() {
  const ordered = sortOrders();
  ordered.forEach((order) => {
    if (order.status === "Queued" && order.queueSecondsRemaining === 0) {
      order.queueSecondsRemaining = Math.max(2, order.operations.length + 1);
    }
  });
  if (ordered.length) {
    const first = ordered[0];
    state.selectedOrderId = first.orderId;
    if (first.status === "Queued") {
      first.status = "Running";
      first.queueSecondsRemaining = Math.max(2, first.operations.length);
    }
  }
  persistState();
  renderAll();
}

function tickScheduler() {
  const activeFound = { value: false };
  const ordered = [...state.orders].sort((a, b) => {
    if (a.status !== "Running" && b.status === "Running") return 1;
    if (a.status === "Running" && b.status !== "Running") return -1;
    if (a.priority !== b.priority) return b.priority - a.priority;
    if (a.createdAt !== b.createdAt) return a.createdAt - b.createdAt;
    return orderNumber(a.orderId) - orderNumber(b.orderId);
  });

  for (const order of ordered) {
    if (["Completed", "Cancelled"].includes(order.status)) continue;
    if (order.status === "Running" && !activeFound.value) {
      activeFound.value = true;
      if (order.queueSecondsRemaining > 0) {
        order.queueSecondsRemaining -= 1;
      }
      if (order.queueSecondsRemaining === 0 && order.currentStepIndex < order.operations.length) {
        advanceOrder(order);
      } else if (order.queueSecondsRemaining === 0 && order.currentStepIndex >= order.operations.length) {
        order.status = "Completed";
      }
    } else if (!activeFound.value && order.status === "Queued") {
      order.status = "Running";
      activeFound.value = true;
      if (order.queueSecondsRemaining === 0) order.queueSecondsRemaining = 3;
    } else if (order.status === "Unloading") {
      if (order.queueSecondsRemaining > 0) {
        order.queueSecondsRemaining -= 1;
      }
      if (order.queueSecondsRemaining === 0) {
        completeOrder(order);
      }
    }
  }
}

function advanceOrder(order) {
  if (["Completed", "Cancelled"].includes(order.status)) return;
  if (order.currentStepIndex < order.operations.length) {
    order.operations[order.currentStepIndex].status = "Done";
    order.currentStepIndex += 1;
    if (order.currentStepIndex < order.operations.length) {
      order.status = "Running";
    } else {
      order.status = "Unloading";
      order.queueSecondsRemaining = 2;
    }
  } else {
    order.status = "Completed";
  }
  if (order.status === "Completed") {
    order.operations.forEach((step) => {
      if (step.status !== "Done") step.status = "Done";
    });
  }
}

function completeOrder(order) {
  order.status = "Completed";
  order.currentStepIndex = order.operations.length;
  order.queueSecondsRemaining = 0;
  order.operations.forEach((step) => (step.status = "Done"));
}

function nextExecutionFocus(currentId = "") {
  const active = sortOrders().filter((order) => !["Completed", "Cancelled"].includes(order.status));
  if (!active.length) return "";
  const ids = active.map((order) => order.orderId);
  if (currentId && ids.includes(currentId)) {
    const idx = ids.indexOf(currentId);
    return ids[idx + 1] || ids[idx - 1] || ids[0];
  }
  return ids[0];
}

function focusOrder(orderId) {
  state.executionFocusOrder = orderId;
  state.selectedOrderId = orderId;
  persistState();
  renderAll();
}

function handleExecutionAction(action, orderId) {
  const order = state.orders.find((item) => item.orderId === orderId);
  if (!order) return;
  if (action === "focus") {
    focusOrder(orderId);
    return;
  }
  if (action === "previous") {
    if (order.currentStepIndex > 0) {
      order.currentStepIndex -= 1;
      order.operations[order.currentStepIndex].status = "Pending";
      order.status = "Running";
    }
  } else if (action === "advance") {
    advanceOrder(order);
  } else if (action === "complete") {
    const nextFocus = nextExecutionFocus(orderId);
    completeOrder(order);
    state.executionFocusOrder = nextFocus;
    state.selectedOrderId = nextFocus;
  }
  persistState();
  renderAll();
}

function renderAll() {
  renderTabs();
  renderSidebar();
  renderSummary();
  renderFields();
  renderCatalogTables();
  renderDraft();
  renderOrdersTable();
  renderOrderDetails();
  renderQueueTable();
  renderExecutionList();
}

function bindEvents() {
  el.tabButtons.forEach((button) => {
    button.addEventListener("click", () => setTab(button.dataset.tab));
  });

  el.customerField.addEventListener("input", (event) => {
    state.metadata.customer = event.target.value;
    persistState();
    renderFields();
  });
  el.itemNameField.addEventListener("input", (event) => {
    state.metadata.itemName = event.target.value;
    persistState();
    renderFields();
  });
  el.notesField.addEventListener("input", (event) => {
    state.metadata.notes = event.target.value;
    persistState();
    renderFields();
  });
  el.priorityField.addEventListener("input", (event) => {
    state.metadata.priority = clampInt(event.target.value, 1, 5);
    persistState();
    renderFields();
  });

  el.operationPicker.addEventListener("change", (event) => {
    setDefaultOperationMinutes(event.target.value);
    persistState();
    renderFields();
  });

  el.timeUpBtn.addEventListener("click", () => {
    const name = state.operationPicker;
    state.operationMinutesByName[name] = Math.min(99, clampInt(state.operationMinutesByName[name], 1, 99) + 1);
    persistState();
    renderFields();
  });
  el.timeDownBtn.addEventListener("click", () => {
    const name = state.operationPicker;
    state.operationMinutesByName[name] = Math.max(1, clampInt(state.operationMinutesByName[name], 1, 99) - 1);
    persistState();
    renderFields();
  });

  el.addOperationBtn.addEventListener("click", addOperation);
  el.clearDraftBtn.addEventListener("click", clearDraft);
  el.finishOrderBtn.addEventListener("click", finishOrder);
  el.runSchedulerBtn.addEventListener("click", runScheduler);

  el.modeStaticBtn.addEventListener("click", () => {
    state.schedulerMode = "Static";
    persistState();
    renderAll();
  });
  el.modeDynamicBtn.addEventListener("click", () => {
    state.schedulerMode = "Dynamic";
    persistState();
    renderAll();
  });

  document.addEventListener("click", (event) => {
    const chip = event.target.closest("[data-suggest-for]");
    if (chip) {
      const value = chip.dataset.value || "";
      const field = chip.dataset.suggestFor;
      if (field === "customer") {
        state.metadata.customer = value;
      } else if (field === "item_name") {
        state.metadata.itemName = value;
      } else if (field === "notes") {
        state.metadata.notes = value;
      }
      persistState();
      renderAll();
      return;
    }

    const orderRow = event.target.closest("[data-order-id]");
    if (orderRow && orderRow.closest("#ordersTable")) {
      state.selectedOrderId = orderRow.dataset.orderId;
      persistState();
      renderAll();
      return;
    }

    const execButton = event.target.closest("[data-action]");
    if (execButton && execButton.closest("#executionList")) {
      handleExecutionAction(execButton.dataset.action, execButton.dataset.orderId);
    }
  });
}

function tick() {
  state.orders.forEach((order) => {
    if (order.status === "Queued" && order.queueSecondsRemaining === 0 && order.operations.length) {
      order.queueSecondsRemaining = Math.max(2, order.operations.length + 1);
    }
  });
  tickScheduler();
  state.orders.forEach((order) => {
    if (order.status === "Completed" && order.currentStepIndex >= order.operations.length) {
      order.operations.forEach((step) => {
        if (step.status !== "Done") step.status = "Done";
      });
    }
  });
  persistState();
  renderAll();
}

bindEvents();
renderAll();
setInterval(tick, 1000);
