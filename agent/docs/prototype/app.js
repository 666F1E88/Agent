/* ============================================================
   TaskMate 课程资料第二大脑 · 原型交互逻辑
   - 纯原生 JS，无外部依赖，离线可用
   - 包含 9 项核心交互 + 若干增强交互
   ============================================================ */

/* ---------- 通用工具：HTML 转义，防止用户输入破坏结构 ---------- */
function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  });
}

/* ---------- 通用工具：Toast 提示（右上角滑入） ---------- */
function showToast(message, type) {
  type = type || 'success';
  var container = document.getElementById('toastContainer');
  var toast = document.createElement('div');
  toast.className = 'toast' + (type === 'alert' ? ' alert' : '');
  var icon = type === 'alert'
    ? '<svg viewBox="0 0 24 24"><path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/></svg>'
    : '<svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>';
  toast.innerHTML = icon + '<span>' + escapeHtml(message) + '</span>';
  container.appendChild(toast);
  // 触发滑入动画
  requestAnimationFrame(function () { toast.classList.add('show'); });
  // 3 秒后滑出并移除
  setTimeout(function () {
    toast.classList.remove('show');
    setTimeout(function () { toast.remove(); }, 400);
  }, 3000);
}

/* ============================================================
   交互 1 & 2：导航切换 + 前台/后台模式切换
   ============================================================ */
var PAGES = ['p1','p2','p3','p4','p5','p6','p7','p8','p9','p10','p11','p12','p13'];
var FRONT_PAGES = PAGES.slice(0, 8);   // p1 - p8
var ADMIN_PAGES = PAGES.slice(8);      // p9 - p13

// 跳转到指定页面：自动切换对应模式与导航高亮
function goToPage(pageId) {
  if (PAGES.indexOf(pageId) === -1) return;
  // 隐藏所有 section，只显示目标页
  PAGES.forEach(function (id) {
    document.getElementById(id).classList.toggle('active', id === pageId);
  });
  var isAdmin = ADMIN_PAGES.indexOf(pageId) !== -1;
  // 同步模式切换按钮
  document.querySelectorAll('.mode-btn').forEach(function (btn) {
    var active = (btn.dataset.mode === 'admin') === isAdmin;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  // 同步导航分组显示
  document.querySelector('.nav-group[data-group="frontend"]').hidden = isAdmin;
  document.querySelector('.nav-group[data-group="admin"]').hidden = !isAdmin;
  // 同步导航项高亮
  document.querySelectorAll('.nav-item').forEach(function (item) {
    item.classList.toggle('active', item.dataset.page === pageId);
  });
  // 更新地址栏锚点（不触发滚动）
  history.replaceState(null, '', '#' + pageId);
  var main = document.getElementById('content');
  if (main) main.scrollTop = 0;
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// 侧边栏导航点击
document.querySelectorAll('.nav-item').forEach(function (item) {
  item.addEventListener('click', function (e) {
    e.preventDefault();
    goToPage(item.dataset.page);
  });
});

// 页面内「快捷入口 / 查看全部」等 data-go 按钮点击
document.querySelectorAll('[data-go]').forEach(function (el) {
  el.addEventListener('click', function () { goToPage(el.dataset.go); });
});

// 模式切换：跳到对应分组第一页（前台 p1 / 后台 p9）
document.querySelectorAll('.mode-btn').forEach(function (btn) {
  btn.addEventListener('click', function () {
    goToPage(btn.dataset.mode === 'admin' ? 'p9' : 'p1');
  });
});

// 支持浏览器地址栏 #pX 直接打开对应页
(function initFromHash() {
  var id = location.hash.replace('#', '');
  goToPage(PAGES.indexOf(id) !== -1 ? id : 'p1');
})();

/* ============================================================
   P1：登录 / 注册 Tab 切换 + 隐私声明控制登录按钮
   ============================================================ */
document.querySelectorAll('.auth-tab').forEach(function (tab) {
  tab.addEventListener('click', function () {
    document.querySelectorAll('.auth-tab').forEach(function (t) { t.classList.remove('active'); });
    tab.classList.add('active');
    document.getElementById('authSubmit').textContent = tab.dataset.auth === 'register' ? '注 册' : '登 录';
  });
});
document.getElementById('authSubmit').addEventListener('click', function () {
  showToast('登录成功，欢迎回到 TaskMate');
  setTimeout(function () { goToPage('p2'); }, 500);
});
var authConsent = document.getElementById('authConsent');
var authSubmit = document.getElementById('authSubmit');
function syncAuthBtn() { authSubmit.disabled = !authConsent.checked; }
authConsent.addEventListener('change', syncAuthBtn);
syncAuthBtn();

/* ============================================================
   P3：拖拽上传 + 解析进度动画 + 隐私声明控制上传按钮
   ============================================================ */
var dropzone = document.getElementById('dropzone');
var fileInput = document.getElementById('fileInput');
var parsePanel = document.getElementById('parsePanel');
var parseFileName = document.getElementById('parseFileName');
var parseStatus = document.getElementById('parseStatus');
var progressFill = document.getElementById('progressFill');
var parsePercent = document.getElementById('parsePercent');
var parseStep = document.getElementById('parseStep');
var uploadConsent = document.getElementById('uploadConsent');
var uploadBtn = document.getElementById('uploadBtn');

// 拖拽高亮效果
['dragenter', 'dragover'].forEach(function (evt) {
  dropzone.addEventListener(evt, function (e) { e.preventDefault(); dropzone.classList.add('drag-over'); });
});
['dragleave', 'drop'].forEach(function (evt) {
  dropzone.addEventListener(evt, function (e) { e.preventDefault(); dropzone.classList.remove('drag-over'); });
});
dropzone.addEventListener('drop', function (e) {
  if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
});
// 点击整个拖拽区也可打开文件选择器
dropzone.addEventListener('click', function () { fileInput.click(); });
fileInput.addEventListener('change', function () {
  if (fileInput.files.length) handleFile(fileInput.files[0]);
});

// 读取文件信息并设置解析面板
function handleFile(file) {
  var ext = file.name.split('.').pop().toLowerCase();
  if (ext !== 'pdf' && ext !== 'pptx') {
    showToast('仅支持 PDF / PPTX 格式', 'alert');
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    showToast('文件超过 10MB 上限', 'alert');
    return;
  }
  parseFileName.textContent = file.name;
  parsePanel.hidden = false;
  progressFill.style.width = '0%';
  parsePercent.textContent = '0%';
  parseStatus.textContent = '解析中';
  parseStatus.className = 'badge badge-info';
}

// 交互 6：隐私声明未勾选 → 上传按钮置灰
function syncUploadBtn() { uploadBtn.disabled = !uploadConsent.checked; }
uploadConsent.addEventListener('change', syncUploadBtn);
syncUploadBtn();

// 开始上传：模拟解析进度条动画
uploadBtn.addEventListener('click', function () {
  if (uploadBtn.disabled) return;
  var steps = [
    { p: 15, t: '正在正则脱敏敏感信息…' },
    { p: 38, t: '正在按页提取纯文本…' },
    { p: 62, t: '正在标记 DDL 句子…' },
    { p: 85, t: '正在构建 BM25 索引…' },
    { p: 100, t: '解析完成，可以开始问答' }
  ];
  var i = 0;
  var timer = setInterval(function () {
    if (i >= steps.length) {
      clearInterval(timer);
      parseStatus.textContent = '解析完成';
      parseStatus.className = 'badge badge-success';
      showToast('资料解析完成，共提取 24 页');
      return;
    }
    progressFill.style.width = steps[i].p + '%';
    parsePercent.textContent = steps[i].p + '%';
    parseStep.textContent = steps[i].t;
    i++;
  }, 500);
});

/* ============================================================
   交互 3：复习卡片 3D 翻转 + 掌握度标记
   ============================================================ */
document.querySelectorAll('.flashcard-inner').forEach(function (inner) {
  inner.addEventListener('click', function () {
    inner.parentElement.classList.toggle('flipped');
  });
});

// 掌握度按钮（阻止冒泡，避免触发翻转）
var masteredCards = new Set([1, 2]); // 初始 2 张已掌握，与进度条 50% 一致
function updateMasteryUI() {
  var count = masteredCards.size;
  document.querySelector('.mastery-fill').style.width = (count / 4 * 100) + '%';
  document.querySelector('.mastery-text').textContent = count + ' / 4 已掌握';
}
document.querySelectorAll('.fc-btn').forEach(function (btn) {
  btn.addEventListener('click', function (e) {
    e.stopPropagation();
    var card = btn.closest('.flashcard');
    var id = parseInt(card.dataset.card, 10);
    if (btn.dataset.action === 'mastered') {
      masteredCards.add(id);
      card.querySelector('.fc-got').classList.add('marked');
      card.querySelector('.fc-review').classList.remove('marked');
      showToast('已标记为掌握');
    } else {
      masteredCards.delete(id);
      card.querySelector('.fc-review').classList.add('marked');
      card.querySelector('.fc-got').classList.remove('marked');
      showToast('已加入再复习清单', 'alert');
    }
    updateMasteryUI();
  });
});
updateMasteryUI();

/* ============================================================
   交互 4：溯源问答发送消息（关键词模拟逻辑）
   - 含「无关」等 → 拒答；「DDL/作业/截止」→ 带页码回答；其他 → 通用带页码回答
   ============================================================ */
var chatMessages = document.getElementById('chatMessages');
var chatInput = document.getElementById('chatInput');
var chatSend = document.getElementById('chatSend');

var AI_AVATAR = '<svg viewBox="0 0 24 24"><rect x="1" y="1" width="22" height="22" rx="7" fill="#4F46E5"/><circle cx="8" cy="12" r="1.6" fill="#fff"/><circle cx="16" cy="12" r="1.6" fill="#fff"/><path d="M8 16h8" stroke="#fff" stroke-width="1.5"/></svg>';

function appendUserMessage(text) {
  var el = document.createElement('div');
  el.className = 'msg msg-user';
  el.innerHTML = '<div class="msg-avatar user">钟</div>' +
    '<div class="msg-body"><div class="msg-bubble">' + escapeHtml(text) + '</div></div>';
  chatMessages.appendChild(el);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendAiMessage(html, sourcePage) {
  var el = document.createElement('div');
  el.className = 'msg msg-ai';
  var sourceHtml = sourcePage
    ? '<div class="source-badges"><span class="source-badge">来源：课件第 ' + sourcePage + ' 页</span></div>'
    : '';
  el.innerHTML = '<div class="msg-avatar ai">' + AI_AVATAR + '</div>' +
    '<div class="msg-body"><div class="msg-bubble">' + html + '</div>' + sourceHtml + '</div>';
  chatMessages.appendChild(el);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showTyping() {
  var el = document.createElement('div');
  el.className = 'msg msg-ai';
  el.id = 'typingIndicator';
  el.innerHTML = '<div class="msg-avatar ai">' + AI_AVATAR + '</div>' +
    '<div class="msg-body"><div class="msg-bubble"><span class="typing-dot"><i></i><i></i><i></i></span></div></div>';
  chatMessages.appendChild(el);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function getAnswer(text) {
  var t = text.toLowerCase();
  // 拒答：无关问题（A4）
  if (/无关|天气|娱乐|游戏|新闻|股票|怎么买|谁赢了/.test(t)) {
    return { html: '资料中未找到相关内容。这个问题超出了当前课件知识库的范围，建议更换与课程相关的问题。', page: null };
  }
  // DDL / 作业 / 截止 → 第 8 页（A2 + A5）
  if (/ddl|作业|截止|什么时候|几点|日期|提交/.test(t)) {
    return { html: '根据课件，第二次团队作业需在 <b>2026-11-22 23:59</b> 前提交，内容包括原型设计、概要设计（UML 图与数据库设计）及说明书。可到「DDL 待办」页确认并同步到待办。', page: 8 };
  }
  // 卡片 / 测试 → 第 12 页
  if (/测试|黑盒|白盒|卡片/.test(t)) {
    return { html: '软件测试分为黑盒测试与白盒测试：黑盒测试依据需求规格说明检查功能，不关心内部逻辑；白盒测试依据程序内部逻辑结构设计用例，覆盖代码路径。', page: 12 };
  }
  // 通用：需求分析 → 第 3 页
  return { html: '需求分析的基本任务是回答"系统必须做什么"，包括确定系统综合要求、分析数据要求、导出逻辑模型以及修正开发计划。主要获取方法有访谈、自顶向下逐步求精、应用规格说明技术与快速原型。', page: 3 };
}

function sendChat() {
  var text = chatInput.value.trim();
  if (!text) { showToast('请输入问题', 'alert'); return; }
  appendUserMessage(text);
  chatInput.value = '';
  showTyping();
  setTimeout(function () {
    var typing = document.getElementById('typingIndicator');
    if (typing) typing.remove();
    var answer = getAnswer(text);
    appendAiMessage(answer.html, answer.page);
  }, 750);
}
chatSend.addEventListener('click', sendChat);
chatInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') sendChat(); });

/* ============================================================
   交互 5：DDL「确认同步」→ Toast 成功提示
   ============================================================ */
document.querySelectorAll('.sync-btn').forEach(function (btn) {
  btn.addEventListener('click', function () {
    var name = btn.dataset.todo;
    // 调用上一版 add_todo（原型中用 toast 模拟同步成功）
    showToast('已同步「' + name + '」到 TaskMate 待办');
    btn.textContent = '已同步';
    btn.disabled = true;
    btn.classList.remove('btn-primary');
    btn.classList.add('btn-ghost');
    var row = btn.closest('tr');
    var statusCell = row.children[4];
    statusCell.innerHTML = '<span class="badge badge-success">已同步</span>';
  });
});

/* ============================================================
   P8：历史问答列表点击切换详情
   ============================================================ */
var HISTORY_DATA = {
  q1: { date: '2026-11-19 10:24', user: '钟楚楠', q: '第二次团队作业什么时候截止？', a: '根据课件，第二次团队作业需在 2026-11-22 23:59 前提交，内容包括原型设计、概要设计（UML 图与数据库设计）及说明书。建议尽早完成 DDL 同步。', page: 8, material: '软件工程-第3章-需求分析.pptx', qa: 'QA-0086' },
  q2: { date: '2026-11-18 21:06', user: '钟楚楠', q: '需求分析阶段有哪些主要任务？', a: '基本任务是回答"系统必须做什么"。主要任务：确定系统综合要求、分析数据要求、导出逻辑模型、修正开发计划。', page: 3, material: '软件工程-第3章-需求分析.pptx', qa: 'QA-0085' },
  q3: { date: '2026-11-17 15:40', user: '钟楚楠', q: '黑盒测试和白盒测试的区别是什么？', a: '黑盒测试不关心程序内部逻辑，依据需求规格说明检查功能；白盒测试依据内部逻辑结构设计用例，覆盖代码路径。', page: 12, material: '软件测试基础-单元测试.pdf', qa: 'QA-0084' },
  q4: { date: '2026-11-16 09:12', user: '钟楚楠', q: 'UML 用例图的作用是什么？', a: '用例图从用户视角描述系统功能需求，展示参与者与用例之间的交互关系，常用于需求分析阶段。', page: 5, material: 'UML建模与类图.pptx', qa: 'QA-0083' },
  q5: { date: '2026-11-14 20:31', user: '钟楚楠', q: '什么是高内聚低耦合？', a: '耦合度量模块间连接紧密程度，内聚度量模块内部元素结合紧密程度。优秀设计追求"高内聚、低耦合"。', page: 9, material: '软件工程-第3章-需求分析.pptx', qa: 'QA-0082' }
};
document.querySelectorAll('.history-item').forEach(function (item) {
  item.addEventListener('click', function () {
    var d = HISTORY_DATA[item.dataset.id];
    if (!d) return;
    document.querySelectorAll('.history-item').forEach(function (i) { i.classList.remove('active'); });
    item.classList.add('active');
    document.getElementById('historyDetail').innerHTML =
      '<div class="hd-head"><span class="hd-date">' + d.date + '</span><span class="badge badge-success">已溯源</span></div>' +
      '<div class="hd-block"><div class="hd-label">我的问题</div><div class="hd-q">' + escapeHtml(d.q) + '</div></div>' +
      '<div class="hd-block"><div class="hd-label">AI 回答</div><div class="hd-a">' + escapeHtml(d.a) + '</div>' +
      '<div class="source-badges"><span class="source-badge">来源：课件第 ' + d.page + ' 页</span></div></div>' +
      '<div class="hd-foot">关联资料：' + escapeHtml(d.material) + '　|　问答编号：' + d.qa + '</div>';
  });
});

/* ============================================================
   交互 8：表格搜索 / 筛选基础过滤
   - 通用过滤：按关键词匹配行文本
   ============================================================ */
function setupTableFilter(inputId, tableId, filterId) {
  var input = document.getElementById(inputId);
  var table = document.getElementById(tableId);
  var filter = filterId ? document.getElementById(filterId) : null;
  if (!input || !table) return;
  function apply() {
    var kw = input.value.trim().toLowerCase();
    var status = filter ? filter.value : 'all';
    table.querySelectorAll('tbody tr').forEach(function (row) {
      var text = row.textContent.toLowerCase();
      var matchKw = !kw || text.indexOf(kw) !== -1;
      // 状态筛选：匹配第 6 列（解析状态）
      var matchStatus = true;
      if (status && status !== 'all') {
        var cell = row.children[5];
        matchStatus = cell && cell.textContent.trim() === status;
      }
      row.style.display = (matchKw && matchStatus) ? '' : 'none';
    });
  }
  input.addEventListener('input', apply);
  if (filter) filter.addEventListener('change', apply);
}
setupTableFilter('userSearch', 'userTable');
setupTableFilter('materialSearch', 'materialTable', 'materialFilter');
setupTableFilter('qaSearch', 'qaTable');
setupTableFilter('historySearch', null); // 历史列表单独处理见下

// 历史问题搜索（过滤左侧列表）
var historySearch = document.getElementById('historySearch');
if (historySearch) {
  historySearch.addEventListener('input', function () {
    var kw = historySearch.value.trim().toLowerCase();
    document.querySelectorAll('.history-item').forEach(function (item) {
      item.style.display = item.textContent.toLowerCase().indexOf(kw) !== -1 ? '' : 'none';
    });
  });
}

/* ============================================================
   P10：用户管理 启用 / 停用 切换
   ============================================================ */
document.querySelectorAll('.toggle-user').forEach(function (btn) {
  btn.addEventListener('click', function () {
    var row = btn.closest('tr');
    var statusCell = row.children[4];
    var isEnabled = statusCell.textContent.trim() === '启用';
    if (isEnabled) {
      statusCell.innerHTML = '<span class="badge badge-muted">停用</span>';
      btn.textContent = '启用';
      showToast('已停用该用户');
    } else {
      statusCell.innerHTML = '<span class="badge badge-success">启用</span>';
      btn.textContent = '停用';
      showToast('已启用该用户');
    }
  });
});

/* ============================================================
   P11：资料管理 删除（原型中移除该行）
   ============================================================ */
document.querySelectorAll('.del-btn').forEach(function (btn) {
  btn.addEventListener('click', function () {
    var row = btn.closest('tr');
    var name = row.children[0].textContent.trim();
    row.remove();
    showToast('已删除资料：' + name, 'alert');
  });
});

/* ============================================================
   P12：问答监控 点击「查看」弹出完整问答
   ============================================================ */
var qaModal = document.getElementById('qaModal');
var qaModalBody = document.getElementById('qaModalBody');
document.querySelectorAll('.qa-detail').forEach(function (btn) {
  btn.addEventListener('click', function () {
    var row = btn.closest('tr');
    var cells = row.children;
    var user = cells[0].textContent.trim();
    var question = cells[1].textContent.trim();
    var summary = cells[2].textContent.trim();
    var page = cells[3].textContent.trim();
    var time = cells[4].textContent.trim();
    qaModalBody.innerHTML =
      '<div class="hd-head"><span class="hd-date">用户：' + escapeHtml(user) + ' · ' + escapeHtml(time) + '</span><span class="badge badge-success">已归档</span></div>' +
      '<div class="hd-block"><div class="hd-label">问题</div><div class="hd-q">' + escapeHtml(question) + '</div></div>' +
      '<div class="hd-block"><div class="hd-label">回答摘要</div><div class="hd-a">' + escapeHtml(summary) + '</div>' +
      '<div class="source-badges"><span class="source-badge">' + escapeHtml(page) + '</span></div></div>' +
      '<div class="hd-foot">问答来源：全站问答审计日志　|　溯源校验：通过</div>';
    qaModal.hidden = false;
  });
});
document.getElementById('qaModalClose').addEventListener('click', function () { qaModal.hidden = true; });
qaModal.addEventListener('click', function (e) { if (e.target === qaModal) qaModal.hidden = true; });
document.addEventListener('keydown', function (e) { if (e.key === 'Escape') qaModal.hidden = true; });

/* ============================================================
   交互 7 & 补充：系统配置 滑块 / 恢复默认 / 保存
   ============================================================ */
var cfgThreshold = document.getElementById('cfgThreshold');
var thresholdVal = document.getElementById('thresholdVal');
cfgThreshold.addEventListener('input', function () {
  thresholdVal.textContent = (cfgThreshold.value / 100).toFixed(2);
});
// 保存配置 → Toast 提示
document.getElementById('cfgSave').addEventListener('click', function () {
  var model = document.getElementById('cfgModel').selectedOptions[0].textContent;
  showToast('配置已保存：当前模型 ' + model + '，BM25 阈值 ' + thresholdVal.textContent);
});
// 恢复默认
document.getElementById('cfgReset').addEventListener('click', function () {
  document.getElementById('cfgModel').value = 'deepseek';
  cfgThreshold.value = 45;
  thresholdVal.textContent = '0.45';
  document.getElementById('cfgSize').value = '10';
  document.getElementById('cfgPrivacy').value = 'v1.2（2026-11-01 生效）';
  showToast('已恢复默认配置');
});
