/* 悬浮客服弹窗（聊天式 + 支持复用页面已生成八字） */

(function () {
  function byId(id) {
    return document.getElementById(id);
  }

  function safeTrim(v) {
    return v == null ? "" : String(v).trim();
  }

  function ensureOpenState(open) {
    const modal = byId("chatModal");
    const overlay = byId("chatModalOverlay");
    if (!modal || !overlay) return;
    if (open) {
      modal.classList.add("is-open");
      modal.setAttribute("aria-hidden", "false");
    } else {
      modal.classList.remove("is-open");
      modal.setAttribute("aria-hidden", "true");
    }
  }

  function renderMessage(container, role, text) {
    const wrap = document.createElement("div");
    wrap.className = `chat-bubble ${role}`;
    // 用户消息保持纯文本；助手消息按 markdown 简单渲染，提升可读性
    if (role === "assistant") {
      wrap.innerHTML = parseMd(text || "");
    } else {
      wrap.textContent = text || "";
    }
    container.appendChild(wrap);
    const scroller = container.closest(".chat-body") || container;
    scroller.scrollTop = scroller.scrollHeight;
  }

  function parseMd(text) {
    if (!text) return "";
    // 先转义，避免模型返回 HTML 注入
    let html = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // 标题
    html = html
      .replace(
        /^####\s*(.+)$/gm,
        '<h4 style="color:#FFD700;margin:14px 0 8px;font-size:14px">$1</h4>',
      )
      .replace(
        /^### (.+)$/gm,
        '<h4 style="color:#FFD700;margin:16px 0 8px;font-size:15px">$1</h4>',
      )
      .replace(
        /^## (.+)$/gm,
        '<h3 style="color:#FFD700;margin:18px 0 10px;font-size:16px">$1</h3>',
      )
      .replace(
        /^# (.+)$/gm,
        '<h2 style="color:#FFD700;margin:20px 0 12px;font-size:18px">$1</h2>',
      );

    // 粗体/斜体
    html = html
      .replace(/\*\*(.+?)\*\*/g, '<strong style="color:#ffffff">$1</strong>')
      .replace(/\*(.+?)\*/g, '<em style="color:#e0e0e0">$1</em>');

    // 分割线
    html = html.replace(
      /^---+$/gm,
      '<hr style="border:none;border-top:1px solid #333;margin:12px 0">',
    );

    // 引用（简化）
    html = html.replace(
      /^&gt; (.+)$/gm,
      '<blockquote style="border-left:3px solid #FFD700;padding:4px 12px;margin:8px 0;color:#c0c0c0">$1</blockquote>',
    );

    // 列表：- xxx / 1. xxx
    html = html
      .replace(
        /^\s*[-*] (.+)$/gm,
        '<li style="margin:3px 0 3px 16px;color:#d0d0d0">$1</li>',
      )
      .replace(
        /^\s*\d+\. (.+)$/gm,
        '<li style="margin:3px 0 3px 16px;color:#d0d0d0">$1</li>',
      );

    // 段落/换行
    html = html
      .replace(
        /\n{2,}/g,
        '</p><p style="margin:8px 0;line-height:1.8;color:#d8d8d8">',
      )
      .replace(/\n/g, "<br>");

    html =
      '<p style="margin:8px 0;line-height:1.8;color:#d8d8d8">' + html + "</p>";
    html = html.replace(/<p[^>]*><br><\/p>/g, "");
    return html;
  }

  function getWidgetBaziInputs() {
    return {
      calendarType: byId("chatCalendarType")?.value || "solar",
      year: parseInt(byId("chatYear")?.value, 10),
      month: parseInt(byId("chatMonth")?.value, 10),
      day: parseInt(byId("chatDay")?.value, 10),
      birthTimeStr: byId("chatBirthTime")?.value || "20:20",
      gender: parseInt(byId("chatGender")?.value, 10) || 1,
      sect: parseInt(byId("chatSect")?.value, 10) || 2,
      location: safeTrim(byId("chatLocation")?.value) || "",
    };
  }

  function computeBaziFromWidget() {
    if (typeof window.calculateBazi !== "function") {
      throw new Error("八字计算器未加载（calculateBazi 未找到）");
    }
    const inputs = getWidgetBaziInputs();

    const { year, month, day, gender, sect, location } = inputs;
    const [birthHour, birthMinute] = safeTrim(inputs.birthTimeStr)
      .split(":")
      .map(Number);

    if (!year || !month || !day || isNaN(birthHour) || isNaN(birthMinute)) {
      throw new Error("请先填写完整的出生信息（年/月/日/时）");
    }

    let y = year;
    let m = month;
    let d = day;
    const calendarType = inputs.calendarType;

    if (calendarType === "lunar") {
      if (!window.Lunar || !Lunar.fromYmdHms) {
        throw new Error("lunar-javascript 未加载，无法计算农历转公历");
      }
      const lunarObj = Lunar.fromYmdHms(y, m, d, birthHour, birthMinute, 0);
      const solar = lunarObj.getSolar();
      y = solar.getYear();
      m = solar.getMonth();
      d = solar.getDay();
    }

    const options = { sect, gender };
    const baziData = calculateBazi(y, m, d, birthHour, birthMinute, options);
    return { baziData, location };
  }

  document.addEventListener("DOMContentLoaded", function () {
    const launcher = byId("chatLauncherBtn");
    const modal = byId("chatModal");
    const modalClose = byId("chatCloseBtn");
    const modalMax = byId("chatMaxBtn");
    const scrollTopBtn = byId("chatScrollTopBtn");
    const scrollBottomBtn = byId("chatScrollBottomBtn");
    const overlay = byId("chatModalOverlay");
    const sendBtn = byId("chatSendBtn");
    const input = byId("chatInput");
    const messages = byId("chatMessages");
    const usePageBaziBtn = byId("chatUsePageBaziBtn");
    const resizeHandle = byId("chatResizeHandle");

    if (!launcher || !modal || !modalClose || !overlay || !sendBtn || !input || !messages)
      return;

    const state = {
      messages: [], // provider format: [{role, content}, ...]
      lastBaziSource: "page", // 'page' | 'widget'
    };

    function ensureInitialAssistant() {
      if (state.__inited) return;
      state.__inited = true;
      renderMessage(
        messages,
        "assistant",
        "您好！我是八字智能客服。你可以直接问“我的事业/感情/性格”之类的问题。",
      );
    }

    let historyLoaded = false;
    async function loadHistoryOnce() {
      if (historyLoaded) return;
      historyLoaded = true;
      try {
        if (typeof window.baziGetClientIdentity !== "function" || typeof window.callHistory !== "function") {
          ensureInitialAssistant();
          return;
        }

        const identity = await window.baziGetClientIdentity();
        const items = await window.callHistory(identity.clientId, identity.sessionId, 20);

        // 清空当前 UI/上下文
        messages.innerHTML = "";
        state.messages = [];
        state.__inited = false;

        if (!Array.isArray(items) || items.length === 0) {
          ensureInitialAssistant();
          return;
        }

        items.forEach((it) => {
          const role = it.role === "user" ? "user" : "assistant";
          const content = it.content || "";
          state.messages.push({ role, content });
          renderMessage(messages, role, content);
        });

        // 避免再插入欢迎语
        state.__inited = true;
      } catch (e) {
        console.error("历史记录加载失败:", e);
        ensureInitialAssistant();
      }
    }

    async function onSend() {
      const text = safeTrim(input.value);
      if (!text) return;

      input.value = "";
      renderMessage(messages, "user", text);
      state.messages.push({ role: "user", content: text });

      // 选取八字上下文：优先用页面已生成的八字
      let baziData = null;
      let location = "";
      if (window.__lastBaziData && window.__lastBaziData.fullBazi) {
        state.lastBaziSource = "page";
        baziData = window.__lastBaziData;
        location = window.__lastBaziLocation || "";
      } else {
        state.lastBaziSource = "widget";
        const computed = computeBaziFromWidget();
        baziData = computed.baziData;
        location = computed.location;
      }

      try {
        sendBtn.disabled = true;
        // 创建一个助手消息容器，用于流式增量渲染
        let aiText = "";
        const assistantWrap = document.createElement("div");
        assistantWrap.className = "chat-bubble assistant";
        assistantWrap.innerHTML = parseMd("正在解读，请稍候...");
        messages.appendChild(assistantWrap);

        let renderTimer = null;
      const scroller = messages.closest(".chat-body") || messages;
        const scheduleRender = () => {
          if (renderTimer) return;
          renderTimer = setTimeout(() => {
            assistantWrap.innerHTML = parseMd(aiText || "");
          // 流式更新后同步滚动到底部
          scroller.scrollTop = scroller.scrollHeight;
            renderTimer = null;
          }, 60);
        };

        const payload = {
          // 后端会从 fullBazi / baziData 提取八字上下文
          fullBazi: baziData.fullBazi,
          baziData,
          location,
          today: (function () {
            const today = new Date();
            return {
              solar: `${today.getFullYear()}年${today.getMonth() + 1}月${today.getDate()}日`,
              lunar: typeof Lunar !== 'undefined' && Lunar.fromDate ? Lunar.fromDate(today).toString() : ''
            };
          })(),
          // 将前端 JS 计算的大运摘要传给后端（可序列化）
          dayun: (function () {
            try {
              const raw = baziData && baziData.config && baziData.config.rawBaziObject;
              const genderEl = document.getElementById("chatGender");
              const genderVal = parseInt(genderEl && genderEl.value, 10) || 1;
              if (!raw || typeof raw.getYun !== "function") return "";
              const yun = raw.getYun(genderVal);
              if (!yun || typeof yun.getDaYun !== "function") return "";
              const list = yun.getDaYun() || [];
              const items = list
                .map((dy) => ({
                  ganZhi: dy.getGanZhi ? dy.getGanZhi() : "",
                  startYear: dy.getStartYear ? dy.getStartYear() : null,
                  endYear: dy.getEndYear ? dy.getEndYear() : null,
                  startAge: dy.getStartAge ? dy.getStartAge() : null,
                  endAge: dy.getEndAge ? dy.getEndAge() : null,
                }))
                .filter((x) => x.ganZhi);
              return items;
            } catch (e) {
              return "";
            }
          })(),
          messages: state.messages.slice(-8),
          temperature: 0.7,
          // 提高输出上限，避免“结尾断句/截断”
          max_tokens: 1800,
        };

        if (typeof window.callAIStream !== "function") {
          throw new Error("callAIStream 未加载（请确认页面已引入 js/api.js）");
        }

        await window.callAIStream(payload, (delta) => {
          aiText += delta;
          scheduleRender();
        });

        // 最终渲染一次，保证完整内容展示
        assistantWrap.innerHTML = parseMd(aiText || "");
        state.messages.push({ role: "assistant", content: aiText });
      } catch (e) {
        console.error("客服解读错误:", e);
        const errWrap = document.createElement("div");
        errWrap.className = "chat-bubble assistant";
        errWrap.textContent = `抱歉，解读失败：${e && e.message ? e.message : String(e)}`;
        messages.appendChild(errWrap);
      } finally {
        sendBtn.disabled = false;
      }
    }

    launcher.addEventListener("click", function () {
      ensureOpenState(true);
      loadHistoryOnce();

      // 上报客服弹窗点击
      try {
        const cid = (typeof _getClientId === 'function')
          ? _getClientId()
          : (localStorage.getItem('bazi_client_id_v1') || '');
        const base = (typeof window !== 'undefined' && window.API_BACKEND_BASE_URL)
          ? window.API_BACKEND_BASE_URL : '';
        fetch(base + '/api/visitor/chat-click', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ clientId: cid }),
        }).catch(function () { /* 静默失败 */ });
      } catch (_) { /* 静默失败 */ }

      // 打开后聚焦输入框
      setTimeout(function () {
        input.focus();
      }, 50);
    });

    modalClose.addEventListener("click", function () {
      ensureOpenState(false);
    });

    // 不使用遮挡层，所以不绑定 overlay 点击关闭

    if (scrollTopBtn) {
      scrollTopBtn.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const scroller = messages.closest(".chat-body") || messages;
        scroller.scrollTo({ top: 0, behavior: "smooth" });
      });
    }

    if (scrollBottomBtn) {
      scrollBottomBtn.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const scroller = messages.closest(".chat-body") || messages;
        scroller.scrollTo({ top: scroller.scrollHeight, behavior: "smooth" });
      });
    }

    // ====== 一键放大 / 拖拽移动 / 右下角拖拽缩放 ======
    let drag = null;
    let resize = null;
    let lastBounds = null; // 保存放大前样式

    function isMaximized() {
      return modal.classList.contains("is-maximized");
    }

    function saveBounds() {
      lastBounds = {
        left: modal.style.left || "",
        top: modal.style.top || "",
        right: modal.style.right || "",
        bottom: modal.style.bottom || "",
        width: modal.style.width || "",
        height: modal.style.height || "",
      };
    }

    function restoreBounds() {
      if (!lastBounds) return;
      modal.style.left = lastBounds.left;
      modal.style.top = lastBounds.top;
      modal.style.right = lastBounds.right;
      modal.style.bottom = lastBounds.bottom;
      modal.style.width = lastBounds.width;
      modal.style.height = lastBounds.height;
    }

    if (modalMax) {
      modalMax.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        if (isMaximized()) {
          modal.classList.remove("is-maximized");
          restoreBounds();
        } else {
          saveBounds();
          modal.classList.add("is-maximized");
        }
      });
    }

    // 1) 拖拽移动：用 header（不在最大化状态）
    const header = modal.querySelector(".chat-header");
    if (header) {
      header.addEventListener("pointerdown", function (e) {
        if (isMaximized()) return;
        // 点到按钮时不触发拖拽
        if (e.target && e.target.closest && e.target.closest("button")) return;

        const rect = modal.getBoundingClientRect();
        // 转换成 left/top 模式，便于拖拽
        modal.style.left = rect.left + "px";
        modal.style.top = rect.top + "px";
        modal.style.right = "auto";
        modal.style.bottom = "auto";

        drag = {
          startX: e.clientX,
          startY: e.clientY,
          startLeft: rect.left,
          startTop: rect.top,
          width: rect.width,
          height: rect.height,
        };
        e.preventDefault();
      });

      window.addEventListener("pointermove", function (e) {
        if (!drag) return;
        const dx = e.clientX - drag.startX;
        const dy = e.clientY - drag.startY;
        let newLeft = drag.startLeft + dx;
        let newTop = drag.startTop + dy;

        const maxLeft = window.innerWidth - drag.width;
        const maxTop = window.innerHeight - drag.height;
        newLeft = Math.max(0, Math.min(maxLeft, newLeft));
        newTop = Math.max(0, Math.min(maxTop, newTop));

        modal.style.left = newLeft + "px";
        modal.style.top = newTop + "px";
        modal.style.right = "auto";
        modal.style.bottom = "auto";
      });

      window.addEventListener("pointerup", function () {
        drag = null;
      });
    }

    // 2) 拖拽缩放：右下角手柄
    if (resizeHandle) {
      resizeHandle.addEventListener("pointerdown", function (e) {
        if (isMaximized()) return;
        e.preventDefault();
        e.stopPropagation();

        const rect = modal.getBoundingClientRect();
        modal.style.left = rect.left + "px";
        modal.style.top = rect.top + "px";
        modal.style.right = "auto";
        modal.style.bottom = "auto";

        resize = {
          startX: e.clientX,
          startY: e.clientY,
          startLeft: rect.left,
          startTop: rect.top,
          startWidth: rect.width,
          startHeight: rect.height,
        };
      });

      window.addEventListener("pointermove", function (e) {
        if (!resize) return;
        const dx = e.clientX - resize.startX;
        const dy = e.clientY - resize.startY;

        let newWidth = resize.startWidth + dx;
        let newHeight = resize.startHeight + dy;

        const minW = 260;
        const minH = 360;
        const maxW = window.innerWidth - resize.startLeft;
        const maxH = window.innerHeight - resize.startTop;
        newWidth = Math.max(minW, Math.min(maxW, newWidth));
        newHeight = Math.max(minH, Math.min(maxH, newHeight));

        modal.style.width = newWidth + "px";
        modal.style.height = newHeight + "px";
      });

      window.addEventListener("pointerup", function () {
        resize = null;
      });
    }

    sendBtn.addEventListener("click", onSend);

    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        onSend();
      }
    });

    if (usePageBaziBtn) {
      usePageBaziBtn.addEventListener("click", function () {
        state.lastBaziSource = "page";
        if (window.__lastBaziData && window.__lastBaziData.fullBazi) {
          renderMessage(
            messages,
            "assistant",
            "已使用你在页面里生成的八字作为上下文。",
          );
        } else {
          renderMessage(
            messages,
            "assistant",
            "我还没有找到页面的八字数据。你可以先在主页面点“生成八字解读”。",
          );
        }
      });
    }
  });
})();
