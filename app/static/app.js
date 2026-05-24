const GRID_SIZE = 20;
const DEFAULT_ROSTER_TEMPLATE =
  "組別,學號,系級,姓名\n1,114098000,資管一,王小明\n1,114098001,資管一,李佳蓉\n";

const BLANK_NOTE = "空白";

const BLOCK_CLASS = {
  黑板: "block-board",
  門: "block-door",
};

const colReverseBtn = document.getElementById("col-reverse-btn");
const colReverseHint = document.getElementById("col-reverse-hint");

const courseInput = document.getElementById("course");
const roomNameInput = document.getElementById("room-name");
const runBtn = document.getElementById("run-btn");
const clearRoomBtn = document.getElementById("clear-room-btn");
const previewShuffleBtn = document.getElementById("preview-shuffle-btn");
const editorWrap = document.getElementById("editor-wrap");
const blockPalette = document.getElementById("block-palette");
const eraseBlockBtn = document.getElementById("erase-block-btn");
const selectedReasonText = document.getElementById("selected-reason-text");
const roomInfo = document.getElementById("room-info");
const resultPanel = document.getElementById("result-panel");
const resultText = document.getElementById("result-text");
const seatmapPanel = document.getElementById("seatmap-panel");
const seatmapWrap = document.getElementById("seatmap-wrap");
const downloadLink = document.getElementById("download-link");
const reportLink = document.getElementById("report-link");
const resultActions = document.getElementById("result-actions");
const shufflePanel = document.getElementById("shuffle-panel");
const shuffleList = document.getElementById("shuffle-list");
const rosterEditor = document.getElementById("roster-editor");
const mockRosterHint = document.getElementById("mock-roster-hint");
const rosterCount = document.getElementById("roster-count");
const rosterText = document.getElementById("roster-text");
const rosterFile = document.getElementById("roster-file");
const parseRosterBtn = document.getElementById("parse-roster-btn");
const loadMockTextBtn = document.getElementById("load-mock-text-btn");
const rosterPreviewWrap = document.getElementById("roster-preview-wrap");
const rosterPreviewBody = document.getElementById("roster-preview-body");

let roomBounds = null;
const blocked = new Map();
let dragStart = null;
let dragCurrent = null;
let selectedBlockReason = null;
let eraseBlockMode = false;
let rosterParsed = false;
let rosterDirty = true;
let colReverse = false;
let lastSeatmapPayload = null;
let lastExamId = null;

rosterText.value = DEFAULT_ROSTER_TEMPLATE;

function getEditorMode() {
  return document.querySelector('input[name="editor-mode"]:checked').value;
}

function useMockRoster() {
  return document.querySelector('input[name="roster-source"]:checked').value === "mock";
}

function columnIndices(maxCols) {
  const xs = [];
  for (let x = 1; x <= maxCols; x += 1) xs.push(x);
  return colReverse ? xs.reverse() : xs;
}

function updateColReverseHint() {
  colReverseHint.textContent = colReverse
    ? "目前：最右側為第 1 排"
    : "目前：最左側為第 1 排";
  colReverseBtn.classList.toggle("active-toggle", colReverse);
}

function isBlankNote(note) {
  return (note || "").trim() === BLANK_NOTE;
}

function hasValidStudent(seat) {
  if (!seat) return false;
  const sid = (seat.student_id || "").trim();
  const name = (seat.student_name || "").trim();
  return sid.length >= 4 && name.length > 0 && sid !== name;
}

function blockClassForNote(note) {
  if (isBlankNote(note)) return "block-blank";
  if (!note) return "block-other";
  if (BLOCK_CLASS[note]) return BLOCK_CLASS[note];
  if (note.startsWith("其他")) return "block-other";
  return "block-other";
}

function blockLabelForNote(note) {
  if (isBlankNote(note)) return "✕";
  if (!note) return "";
  if (note === "黑板") return "黑板";
  if (note === "門") return "門";
  return note;
}

function resolveBlockReason() {
  return selectedBlockReason;
}

function updateEditorModeUI() {
  const blockMode = getEditorMode() === "block";
  blockPalette.hidden = !blockMode;
}

function selectBlockReason(reason) {
  // 選原因即離開清除模式
  if (eraseBlockMode) exitEraseMode();
  selectedBlockReason = reason;
  document.querySelectorAll(".reason-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.reason === reason);
  });
  selectedReasonText.textContent = resolveBlockReason() || "（尚未選擇）";
}

function enterEraseMode() {
  eraseBlockMode = true;
  selectedBlockReason = null;
  document.querySelectorAll(".reason-btn").forEach((b) => b.classList.remove("active"));
  selectedReasonText.textContent = "清除模式：拖曳框選要清除的格子";
  eraseBlockBtn.classList.add("active-toggle");
  eraseBlockBtn.textContent = "結束清除模式";
}

function exitEraseMode() {
  eraseBlockMode = false;
  if (!selectedBlockReason) {
    selectedReasonText.textContent = "（尚未選擇）";
  }
  eraseBlockBtn.classList.remove("active-toggle");
  eraseBlockBtn.textContent = "清除框選區標記";
}

function updateRosterUI() {
  const mock = useMockRoster();
  rosterEditor.hidden = mock;
  mockRosterHint.hidden = !mock;
  if (mock) {
    rosterCount.textContent = "使用 mock 名單";
    rosterParsed = true;
    rosterDirty = false;
  } else {
    rosterCount.textContent =
      rosterParsed && !rosterDirty
        ? `已解析 ${rosterPreviewBody.dataset.total || "?"} 人`
        : "尚未解析（請按「解析名單」）";
  }
}

function markRosterDirty() {
  rosterDirty = true;
  rosterParsed = false;
  rosterPreviewWrap.hidden = true;
  updateRosterUI();
}

function renderRosterPreview(students) {
  rosterPreviewBody.innerHTML = "";
  rosterPreviewBody.dataset.total = String(students.length);
  students.forEach((s) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(s.group_name)}</td>
      <td>${escapeHtml(s.student_id)}</td>
      <td>${escapeHtml(s.department_grade === "-" ? "" : s.department_grade)}</td>
      <td>${escapeHtml(s.student_name)}</td>
    `;
    rosterPreviewBody.appendChild(tr);
  });
  rosterPreviewWrap.hidden = false;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

async function parseRoster() {
  const text = rosterText.value.trim();
  if (!text) throw new Error("請貼上或上傳學生名單");
  const res = await fetch("/api/parse-roster", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ roster_text: text }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "解析失敗");
  renderRosterPreview(data.students);
  rosterParsed = true;
  rosterDirty = false;
  rosterCount.textContent = `已解析 ${data.student_count} 人`;
}

function getRosterPayload() {
  if (useMockRoster()) return { use_mock_students: true };
  if (!rosterParsed || rosterDirty) {
    throw new Error("請先按「解析名單」確認資料正確");
  }
  return { roster_text: rosterText.value.trim() };
}

function cellKey(r, c) {
  return `${r},${c}`;
}

function normalizeBounds(a, b) {
  return {
    r0: Math.min(a.r, b.r),
    c0: Math.min(a.c, b.c),
    r1: Math.max(a.r, b.r),
    c1: Math.max(a.c, b.c),
  };
}

function inRoom(r, c) {
  if (!roomBounds) return false;
  return r >= roomBounds.r0 && r <= roomBounds.r1 && c >= roomBounds.c0 && c <= roomBounds.c1;
}

function toRoomCoord(r, c) {
  return { x: c - roomBounds.c0 + 1, y: r - roomBounds.r0 + 1 };
}

function iterCellsInBounds(bounds) {
  const cells = [];
  for (let r = bounds.r0; r <= bounds.r1; r += 1) {
    for (let c = bounds.c0; c <= bounds.c1; c += 1) {
      if (inRoom(r, c)) cells.push({ r, c });
    }
  }
  return cells;
}

function computeEditorNumbering() {
  // 算出「真正會坐學生的橫排與直排」並依序編號 1, 2, 3, ...
  // - 整橫排有黑板 → 該排跳過
  // - 整橫排或整直排全部都是 block（門、柱子等）→ 跳過
  // - col_reverse=true 時，直排編號由右往左排
  if (!roomBounds) return { colNumbers: new Map(), rowNumbers: new Map() };

  const blackboardRows = new Set();
  for (let r = roomBounds.r0; r <= roomBounds.r1; r += 1) {
    for (let c = roomBounds.c0; c <= roomBounds.c1; c += 1) {
      if (blocked.get(cellKey(r, c)) === "黑板") {
        blackboardRows.add(r);
        break;
      }
    }
  }

  const isSeatable = (r, c) => {
    if (blackboardRows.has(r)) return false;
    return !blocked.has(cellKey(r, c));
  };

  const usableRows = [];
  for (let r = roomBounds.r0; r <= roomBounds.r1; r += 1) {
    for (let c = roomBounds.c0; c <= roomBounds.c1; c += 1) {
      if (isSeatable(r, c)) {
        usableRows.push(r);
        break;
      }
    }
  }

  const usableCols = [];
  for (let c = roomBounds.c0; c <= roomBounds.c1; c += 1) {
    for (let r = roomBounds.r0; r <= roomBounds.r1; r += 1) {
      if (isSeatable(r, c)) {
        usableCols.push(c);
        break;
      }
    }
  }

  const rowNumbers = new Map();
  usableRows.forEach((r, idx) => rowNumbers.set(r, idx + 1));

  const colNumbers = new Map();
  const totalCols = usableCols.length;
  usableCols.forEach((c, idx) => {
    colNumbers.set(c, colReverse ? totalCols - idx : idx + 1);
  });

  return { colNumbers, rowNumbers };
}

function buildEditorGrid() {
  editorWrap.innerHTML = "";
  const table = document.createElement("table");
  table.className = "editor-grid";

  // ── 欄號標頭列（第 0 列，不是實際座位）
  const headerTr = document.createElement("tr");
  const cornerTh = document.createElement("th");
  cornerTh.className = "grid-axis-label";
  headerTr.appendChild(cornerTh);
  for (let c = 0; c < GRID_SIZE; c += 1) {
    const th = document.createElement("th");
    th.className = "grid-axis-label grid-col-label";
    th.dataset.c = String(c);
    th.textContent = String(c + 1);
    headerTr.appendChild(th);
  }
  table.appendChild(headerTr);

  // ── 資料列（每列最左側加排號標頭）
  for (let r = 0; r < GRID_SIZE; r += 1) {
    const tr = document.createElement("tr");
    const rowTh = document.createElement("th");
    rowTh.className = "grid-axis-label grid-row-label";
    rowTh.dataset.r = String(r);
    rowTh.textContent = String(r + 1);
    tr.appendChild(rowTh);
    for (let c = 0; c < GRID_SIZE; c += 1) {
      const td = document.createElement("td");
      td.dataset.r = String(r);
      td.dataset.c = String(c);
      td.addEventListener("mousedown", onCellMouseDown);
      td.addEventListener("mouseenter", onCellMouseEnter);
      tr.appendChild(td);
    }
    table.appendChild(tr);
  }
  editorWrap.appendChild(table);
  document.addEventListener("mouseup", onMouseUp);
  paintEditor();
}

function paintEditor() {
  const cells = editorWrap.querySelectorAll("td");
  const previewBounds =
    dragStart && dragCurrent ? normalizeBounds(dragStart, dragCurrent) : null;

  cells.forEach((td) => {
    const r = Number(td.dataset.r);
    const c = Number(td.dataset.c);
    const key = cellKey(r, c);
    td.className = "outside";
    td.textContent = "";
    td.title = "";

    if (previewBounds && r >= previewBounds.r0 && r <= previewBounds.r1 && c >= previewBounds.c0 && c <= previewBounds.c1) {
      if (getEditorMode() === "room" && !roomBounds) {
        td.className = "selecting";
      } else if (getEditorMode() === "block" && inRoom(r, c)) {
        td.className = "selecting-block";
      }
    } else if (inRoom(r, c)) {
      const note = blocked.get(key);
      if (note) {
        td.className = `blocked-edit ${blockClassForNote(note)}`;
        td.textContent = blockLabelForNote(note);
        td.title = isBlankNote(note) ? "空白（不坐人）" : note;
      } else {
        td.className = "in-room";
      }
    }
  });

  if (roomBounds && !dragStart) {
    const rows = roomBounds.r1 - roomBounds.r0 + 1;
    const cols = roomBounds.c1 - roomBounds.c0 + 1;
    const usable = rows * cols - blocked.size;
    roomInfo.textContent = `教室大小：${rows} 列 × ${cols} 欄（可用約 ${usable} 格）`;
  } else if (!dragStart) {
    roomInfo.textContent = "尚未框選教室（在格線上拖曳滑鼠框選矩形區域）";
  }

  // 更新軸標籤：依「實際座位排」編號
  const { colNumbers, rowNumbers } = computeEditorNumbering();
  editorWrap.querySelectorAll(".grid-col-label").forEach((th) => {
    const c = Number(th.dataset.c);
    if (!roomBounds) {
      // 尚未框選教室，淡淡的 1~20 標號也跟著 col_reverse 翻轉
      th.textContent = String(colReverse ? GRID_SIZE - c : c + 1);
      th.classList.remove("axis-in-room");
    } else if (colNumbers.has(c)) {
      th.textContent = String(colNumbers.get(c));
      th.classList.add("axis-in-room");
    } else {
      th.textContent = "";
      th.classList.remove("axis-in-room");
    }
  });
  editorWrap.querySelectorAll(".grid-row-label").forEach((th) => {
    const r = Number(th.dataset.r);
    if (!roomBounds) {
      th.textContent = String(r + 1);
      th.classList.remove("axis-in-room");
    } else if (rowNumbers.has(r)) {
      th.textContent = String(rowNumbers.get(r));
      th.classList.add("axis-in-room");
    } else {
      th.textContent = "";
      th.classList.remove("axis-in-room");
    }
  });
}

function onCellMouseDown(e) {
  if (getEditorMode() === "block" && !roomBounds) {
    alert("請先框選教室範圍");
    return;
  }
  const td = e.currentTarget;
  dragStart = { r: Number(td.dataset.r), c: Number(td.dataset.c) };
  dragCurrent = { ...dragStart };
  paintEditor();
}

function onCellMouseEnter(e) {
  if (!dragStart) return;
  const td = e.currentTarget;
  dragCurrent = { r: Number(td.dataset.r), c: Number(td.dataset.c) };
  paintEditor();
}

function onMouseUp() {
  if (!dragStart || !dragCurrent) return;
  const bounds = normalizeBounds(dragStart, dragCurrent);

  if (getEditorMode() === "room") {
    roomBounds = bounds;
  } else if (getEditorMode() === "block") {
    if (eraseBlockMode) {
      iterCellsInBounds(bounds).forEach(({ r, c }) => blocked.delete(cellKey(r, c)));
      // 清除模式維持開啟，使用者要再按一次按鈕才結束
    } else {
      const reason = resolveBlockReason();
      if (!reason) {
        alert("請先選擇不可用原因（黑板／門／不坐人）");
      } else {
        // 黑板僅標記框選格本身，整排不再自動補齊；
        // 排位時後端會自動跳過該橫排，且座位表的排數編號也會跳過。
        iterCellsInBounds(bounds).forEach(({ r, c }) => {
          blocked.set(cellKey(r, c), reason);
        });
      }
    }
  }

  dragStart = null;
  dragCurrent = null;
  paintEditor();
}

function clearRoom() {
  roomBounds = null;
  blocked.clear();
  dragStart = null;
  dragCurrent = null;
  paintEditor();
}

eraseBlockBtn.addEventListener("click", () => {
  if (eraseBlockMode) exitEraseMode();
  else enterEraseMode();
});

function getLayoutPayload() {
  if (!roomBounds) throw new Error("請先框選教室範圍");
  const rows = roomBounds.r1 - roomBounds.r0 + 1;
  const cols = roomBounds.c1 - roomBounds.c0 + 1;
  const blockedPayload = [];
  blocked.forEach((note, key) => {
    const [r, c] = key.split(",").map(Number);
    const rel = toRoomCoord(r, c);
    blockedPayload.push({ x: rel.x, y: rel.y, note });
  });
  return { rows, cols, blocked: blockedPayload };
}

function fillSeatCell(td, seat) {
  if (!seat || seat.is_usable === 0) {
    const note = seat?.block_note || "";
    if (isBlankNote(note)) {
      td.className = "block-blank";
      td.textContent = "✕";
      td.title = "不坐人";
      return;
    }
    td.className = blockClassForNote(note);
    td.textContent = blockLabelForNote(note);
    td.title = note || "不可用";
    return;
  }
  if (!hasValidStudent(seat)) {
    td.className = "empty";
    td.textContent = "";
    return;
  }
  td.className = "assigned";
  td.innerHTML = `
    <div class="cell-id">${escapeHtml(seat.student_id.trim())}</div>
    <div class="cell-name">${escapeHtml(seat.student_name.trim())}</div>
  `;
  td.title = `${seat.student_id} ${seat.student_name}`;
}

function updateExportLinks(examId) {
  const q = colReverse ? "?col_reverse=1" : "";
  downloadLink.href = `/api/exam/${examId}/download${q}`;
  reportLink.href = `/api/exam/${examId}/report${q}`;
}

function computeSeatmapNumbering(room, seats) {
  // 依「會坐學生的排與直排」重新編號；門/黑板/柱子整排都跳過
  const byXY = new Map();
  seats.forEach((s) => byXY.set(`${s.grid_x}-${s.grid_y}`, s));

  const blackboardRows = new Set();
  seats.forEach((s) => {
    if ((s.block_note || "").trim() === "黑板") blackboardRows.add(s.grid_y);
  });

  const isSeatable = (s) => {
    if (!s) return false;
    if (s.is_usable !== 1) return false;
    if (blackboardRows.has(s.grid_y)) return false;
    return true;
  };

  const usableRows = [];
  for (let y = 1; y <= room.max_rows; y += 1) {
    for (let x = 1; x <= room.max_cols; x += 1) {
      if (isSeatable(byXY.get(`${x}-${y}`))) {
        usableRows.push(y);
        break;
      }
    }
  }
  const usableCols = [];
  for (let x = 1; x <= room.max_cols; x += 1) {
    for (let y = 1; y <= room.max_rows; y += 1) {
      if (isSeatable(byXY.get(`${x}-${y}`))) {
        usableCols.push(x);
        break;
      }
    }
  }

  const rowLabel = new Map();
  usableRows.forEach((y, idx) => rowLabel.set(y, idx + 1));
  const colLabel = new Map();
  const total = usableCols.length;
  usableCols.forEach((x, idx) => {
    colLabel.set(x, colReverse ? total - idx : idx + 1);
  });
  return { byXY, rowLabel, colLabel };
}

function renderSeatMap(payload) {
  lastSeatmapPayload = payload;
  seatmapWrap.innerHTML = "";
  if (payload.exam) {
    payload.exam.col_reverse = colReverse ? 1 : 0;
  }
  updateColReverseHint();

  payload.rooms.forEach((roomBlock) => {
    const room = roomBlock.room;
    const seats = roomBlock.seats;
    const { byXY, rowLabel, colLabel } = computeSeatmapNumbering(room, seats);

    // 只畫到最後一位學生為止；多餘的空格不渲染
    let maxStudentX = 0;
    let maxStudentY = 0;
    seats.forEach((s) => {
      if ((s.student_id || "").trim()) {
        if (s.grid_x > maxStudentX) maxStudentX = s.grid_x;
        if (s.grid_y > maxStudentY) maxStudentY = s.grid_y;
      }
    });
    const showCols = maxStudentX || room.max_cols;
    const showRows = maxStudentY || room.max_rows;

    const cols = [];
    for (let x = 1; x <= showCols; x += 1) cols.push(x);

    const table = document.createElement("table");
    table.className = "seatmap-table";

    const headTr = document.createElement("tr");
    headTr.appendChild(Object.assign(document.createElement("th"), { className: "axis", textContent: "" }));
    cols.forEach((x) => {
      const th = document.createElement("th");
      th.className = "axis";
      th.textContent = colLabel.has(x) ? String(colLabel.get(x)) : "";
      headTr.appendChild(th);
    });
    table.appendChild(headTr);

    for (let y = 1; y <= showRows; y += 1) {
      const tr = document.createElement("tr");
      const rowTh = document.createElement("th");
      rowTh.className = "axis";
      rowTh.textContent = rowLabel.has(y) ? String(rowLabel.get(y)) : "";
      tr.appendChild(rowTh);
      cols.forEach((x) => {
        const td = document.createElement("td");
        fillSeatCell(td, byXY.get(`${x}-${y}`));
        tr.appendChild(td);
      });
      table.appendChild(tr);
    }
    seatmapWrap.appendChild(table);
  });
  seatmapPanel.hidden = false;
}

function renderShufflePreview(shuffled) {
  shuffleList.innerHTML = "";
  shuffled.slice(0, 20).forEach((s) => {
    const li = document.createElement("li");
    const dept = s.department_grade && s.department_grade !== "-" ? `，${s.department_grade}` : "";
    li.textContent = `${s.student_id} ${s.student_name}（組別${s.group_name}${dept}）`;
    shuffleList.appendChild(li);
  });
  shufflePanel.hidden = false;
}

async function previewShuffle() {
  const res = await fetch("/api/preview-shuffle", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(getRosterPayload()),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "預覽失敗");
  renderShufflePreview(data.shuffled_students);
}

async function loadMockText() {
  const res = await fetch("/api/students");
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "載入失敗");
  const lines = ["組別,學號,系級,姓名"];
  data.students.forEach((s) => {
    const dept = s.department_grade && s.department_grade !== "-" ? s.department_grade : "";
    lines.push(`${s.group_name},${s.student_id},${dept},${s.student_name}`);
  });
  rosterText.value = lines.join("\n");
  document.querySelector('input[name="roster-source"][value="custom"]').checked = true;
  markRosterDirty();
  updateRosterUI();
  await parseRoster();
}

async function runAssignment() {
  runBtn.disabled = true;
  runBtn.textContent = "排位中...";
  try {
    const layout = getLayoutPayload();
    const res = await fetch("/api/run-assignment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...layout,
        ...getRosterPayload(),
        course_name: courseInput.value.trim() || "SmartSeat DEMO",
        room_name: roomNameInput.value.trim() || "考場",
        col_reverse: colReverse,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "排位失敗");

    resultPanel.hidden = false;
    resultText.textContent =
      `已安排 ${data.assigned_count} 人，未安排 ${data.unassigned_count} 人` +
      `（共 ${data.student_count} 人，可用座位 ${data.usable_seats} 格）`;

    lastExamId = data.exam_id;
    updateExportLinks(data.exam_id);
    resultActions.hidden = false;

    const mapRes = await fetch(`/api/exam/${data.exam_id}/seatmap`);
    const mapData = await mapRes.json();
    if (!mapRes.ok) throw new Error(mapData.error || "讀取座位圖失敗");
    renderSeatMap(mapData);
  } catch (err) {
    alert(err.message);
  } finally {
    runBtn.disabled = false;
    runBtn.textContent = "一鍵排位";
  }
}

document.querySelectorAll(".reason-btn").forEach((btn) => {
  btn.addEventListener("click", () => selectBlockReason(btn.dataset.reason));
});

runBtn.addEventListener("click", runAssignment);
clearRoomBtn.addEventListener("click", clearRoom);
previewShuffleBtn.addEventListener("click", () => {
  previewShuffle().catch((err) => alert(err.message));
});
parseRosterBtn.addEventListener("click", () => {
  parseRoster().catch((err) => alert(err.message));
});
loadMockTextBtn.addEventListener("click", () => {
  loadMockText().catch((err) => alert(err.message));
});
rosterText.addEventListener("input", markRosterDirty);
rosterFile.addEventListener("change", (e) => {
  const file = e.target.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    rosterText.value = reader.result;
    markRosterDirty();
    updateRosterUI();
  };
  reader.readAsText(file, "UTF-8");
  e.target.value = "";
});
document.querySelectorAll('input[name="editor-mode"]').forEach((el) => {
  el.addEventListener("change", () => {
    updateEditorModeUI();
    paintEditor();
  });
});
document.querySelectorAll('input[name="roster-source"]').forEach((el) => {
  el.addEventListener("change", updateRosterUI);
});

colReverseBtn.addEventListener("click", () => {
  colReverse = !colReverse;
  updateColReverseHint();
  paintEditor();   // ← 編輯器排數標號即時跟著翻轉
  if (lastExamId) updateExportLinks(lastExamId);
  if (lastSeatmapPayload) renderSeatMap(lastSeatmapPayload);
});

buildEditorGrid();
updateEditorModeUI();
updateColReverseHint();
updateRosterUI();
