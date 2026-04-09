// 前端不再直连大模型提供商；由你的后端代理 `/api/interpret` 负责模型调用与密钥安全
const API_CONFIG = {
    currentProvider: 'backend',
    backend: {
        // 允许你通过全局变量覆盖（多域名部署时常用）
        baseUrl: (typeof window !== 'undefined' && window.API_BACKEND_BASE_URL) ? window.API_BACKEND_BASE_URL : ''
    }
};

// 兼容你现有页面里对 window.API_CONFIG 的引用
if (typeof window !== 'undefined') {
    window.API_CONFIG = API_CONFIG;
}

// ====== 未登录用户身份（综合指纹）+ 会话ID ======
// 目标：不需要登录，也能在同一台设备/同一浏览器上“找回近期对话”
// 注意：该 clientId 只在本地生成，不上报裸指纹字段；仅把 hash 发给后端。
const _LS_SALT_KEY = 'bazi_fp_salt_v1';
const _LS_CLIENT_ID_KEY = 'bazi_client_id_v1';
const _LS_SESSION_ID_KEY = 'bazi_session_id_v1';
const _LS_SESSION_TS_KEY = 'bazi_session_ts_v1';

function _lsGet(key) {
    try { return localStorage.getItem(key); } catch (e) { return null; }
}
function _lsSet(key, val) {
    try { localStorage.setItem(key, val); } catch (e) {}
}

function _randHex(bytes = 16) {
    const arr = new Uint8Array(bytes);
    crypto.getRandomValues(arr);
    return Array.from(arr).map(b => b.toString(16).padStart(2, '0')).join('');
}

async function _sha256Hex(str) {
    if (!crypto || !crypto.subtle) {
        // fallback：非常轻量的非加密 hash
        let h = 0;
        for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0;
        return String(h);
    }
    const buf = new TextEncoder().encode(str);
    const digest = await crypto.subtle.digest('SHA-256', buf);
    const bytes = new Uint8Array(digest);
    return Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
}

function _safeCanvasFingerprint() {
    try {
        const canvas = document.createElement('canvas');
        canvas.width = 220;
        canvas.height = 50;
        const ctx = canvas.getContext('2d');
        if (!ctx) return '';
        ctx.textBaseline = 'top';
        ctx.font = '14px Arial';
        ctx.fillStyle = '#f60';
        ctx.fillRect(0, 0, 220, 50);
        ctx.fillStyle = '#069';
        ctx.fillText('bazi', 10, 10);
        ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
        ctx.fillText(String(navigator.userAgent).slice(0, 30), 10, 28);
        // toDataURL 不会上传原图，只参与 hash
        return canvas.toDataURL();
    } catch (e) {
        return '';
    }
}

async function getClientIdentity() {
    if (typeof window === 'undefined') return { clientId: '', sessionId: '' };

    let clientId = _lsGet(_LS_CLIENT_ID_KEY);
    if (!clientId) {
        let salt = _lsGet(_LS_SALT_KEY);
        if (!salt) {
            salt = _randHex(16);
            _lsSet(_LS_SALT_KEY, salt);
        }

        const nav = navigator || {};
        const parts = [
            nav.userAgent || '',
            nav.language || '',
            (nav.languages && nav.languages.join(',')) || '',
            nav.platform || '',
            nav.hardwareConcurrency || '',
            nav.deviceMemory || '',
            (Intl && Intl.DateTimeFormat ? Intl.DateTimeFormat().resolvedOptions().timeZone : '') || '',
            screen ? `${screen.width}x${screen.height}` : '',
            screen ? screen.colorDepth : '',
            _safeCanvasFingerprint() || '',
            salt
        ];

        const fp = parts.join('||');
        const hash = await _sha256Hex(fp);
        // 截断减少 payload 体积
        clientId = 'bazi_' + hash.slice(0, 24);
        _lsSet(_LS_CLIENT_ID_KEY, clientId);
    }

    let sessionId = _lsGet(_LS_SESSION_ID_KEY);
    const ts = parseInt(_lsGet(_LS_SESSION_TS_KEY) || '0', 10);
    const now = Date.now();
    const sevenDays = 7 * 24 * 60 * 60 * 1000;
    if (!sessionId || !ts || (now - ts) > sevenDays) {
        sessionId = 's_' + Math.floor(now / 1000) + '_' + _randHex(8);
        _lsSet(_LS_SESSION_ID_KEY, sessionId);
        _lsSet(_LS_SESSION_TS_KEY, String(now));
    }

    // 每次使用都刷新 session 时间戳
    _lsSet(_LS_SESSION_TS_KEY, String(now));

    return { clientId, sessionId };
}

async function callHistory(clientId, sessionId, limit = 20) {
    const backendBaseUrl = getBackendBaseUrl();
    const url = `${backendBaseUrl}/api/history?clientId=${encodeURIComponent(clientId)}&sessionId=${encodeURIComponent(sessionId)}&limit=${encodeURIComponent(limit)}`;
    const response = await fetch(url, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
    });
    if (!response.ok) {
        let errBody = '';
        try { errBody = await response.text(); } catch (e) {}
        throw new Error(`历史记录加载失败(${response.status}): ${errBody}`);
    }
    const data = await response.json();
    return Array.isArray(data.messages) ? data.messages : [];
}

function getBackendBaseUrl() {
    const baseUrl = (API_CONFIG.backend && API_CONFIG.backend.baseUrl) ? API_CONFIG.backend.baseUrl : '';
    return String(baseUrl).replace(/\/$/, '');
}

async function callAI(baziData) {
    const payload = Object.assign({}, baziData || {});

    // 为未登录用户挂上身份标识，便于存储/读取历史
    const identity = await getClientIdentity();
    payload.clientId = identity.clientId;
    payload.sessionId = identity.sessionId;

    // lunar-javascript 的部分对象（如 config.rawBaziObject/rawLunarObject）包含循环引用，
    // 不能直接 JSON.stringify，否则会在前端报：
    // "Converting circular structure to JSON"
    function sanitizeBaziData(baziObj) {
        if (!baziObj || typeof baziObj !== 'object') return baziObj;

        const safe = {};
        if (baziObj.year) safe.year = baziObj.year;
        if (baziObj.month) safe.month = baziObj.month;
        if (baziObj.day) safe.day = baziObj.day;
        if (baziObj.hour) safe.hour = baziObj.hour;
        if (typeof baziObj.fullBazi === 'string') safe.fullBazi = baziObj.fullBazi;
        if (baziObj.details) safe.details = baziObj.details;
        if (baziObj.lunar) safe.lunar = baziObj.lunar;
        if (baziObj.solarTerms) safe.solarTerms = baziObj.solarTerms;

        // 只保留 sect（其他 raw 对象会导致循环引用/体积过大）
        if (baziObj.config && typeof baziObj.config === 'object') {
            if (typeof baziObj.config.sect !== 'undefined') safe.config = { sect: baziObj.config.sect };
        }
        return safe;
    }

    // 兼容两种结构：
    // 1) 直接传 baziData（baziObj 自身就是 calculateBazi(...) 的返回）
    // 2) 聊天组件传 { ..., baziData: calculateBazi(...) }
    if (payload && payload.baziData) {
        payload.baziData = sanitizeBaziData(payload.baziData);
    }
    if (payload && payload.fullBazi && payload.config && payload.config.sect) {
        // 如果 payload 自己就是 baziData（或包含 baziData 的关键字段），也做安全化处理
        const safeBazi = sanitizeBaziData(payload);
        // 保留额外字段（如 prompt/location/messages等）
        payload.year = safeBazi.year;
        payload.month = safeBazi.month;
        payload.day = safeBazi.day;
        payload.hour = safeBazi.hour;
        payload.fullBazi = safeBazi.fullBazi;
        payload.details = safeBazi.details;
        payload.lunar = safeBazi.lunar;
        payload.solarTerms = safeBazi.solarTerms;
        payload.config = safeBazi.config;
    }

    // 兼容：表单页会传 prompt；聊天页可能传 messages；都可以
    if (!payload.prompt && payload.fullBazi) {
        payload.prompt = generatePrompt(payload);
    }

    // 透传 dayun（若前端已计算并提供），后端会把它写入 system prompt
    // 这里不做计算，只负责传输
    if (payload.dayun && typeof payload.dayun !== 'string') {
        try {
            payload.dayun = JSON.stringify(payload.dayun);
        } catch (e) {
            // ignore
        }
    }

    const backendBaseUrl = getBackendBaseUrl();
    const url = `${backendBaseUrl}/api/interpret`;

    const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });

    if (!response.ok) {
        let errBody = '';
        try {
            errBody = await response.text();
        } catch (e) {
            errBody = '';
        }
        throw new Error(`后端解读服务调用失败(${response.status}): ${errBody}`);
    }

    const data = await response.json();
    if (!data || typeof data.text !== 'string') {
        throw new Error('后端返回格式不正确');
    }
    return data.text;
}

async function callAIStream(baziData, onDelta) {
    const payload = Object.assign({}, baziData || {});

    // 为未登录用户挂上身份标识，便于存储/读取历史
    const identity = await getClientIdentity();
    payload.clientId = identity.clientId;
    payload.sessionId = identity.sessionId;

    function sanitizeBaziData(baziObj) {
        if (!baziObj || typeof baziObj !== "object") return baziObj;
        const safe = {};
        if (baziObj.year) safe.year = baziObj.year;
        if (baziObj.month) safe.month = baziObj.month;
        if (baziObj.day) safe.day = baziObj.day;
        if (baziObj.hour) safe.hour = baziObj.hour;
        if (typeof baziObj.fullBazi === "string") safe.fullBazi = baziObj.fullBazi;
        if (baziObj.details) safe.details = baziObj.details;
        if (baziObj.lunar) safe.lunar = baziObj.lunar;
        if (baziObj.solarTerms) safe.solarTerms = baziObj.solarTerms;
        if (baziObj.today) safe.today = baziObj.today;
        if (baziObj.config && typeof baziObj.config === "object") {
            if (typeof baziObj.config.sect !== "undefined") safe.config = { sect: baziObj.config.sect };
        }
        return safe;
    }

    if (payload && payload.baziData) {
        payload.baziData = sanitizeBaziData(payload.baziData);
    }
    if (payload && payload.fullBazi && payload.config && payload.config.sect) {
        const safeBazi = sanitizeBaziData(payload);
        payload.year = safeBazi.year;
        payload.month = safeBazi.month;
        payload.day = safeBazi.day;
        payload.hour = safeBazi.hour;
        payload.fullBazi = safeBazi.fullBazi;
        payload.details = safeBazi.details;
        payload.lunar = safeBazi.lunar;
        payload.solarTerms = safeBazi.solarTerms;
        payload.today = safeBazi.today;
        payload.config = safeBazi.config;
    }

    if (!payload.prompt && payload.fullBazi) {
        payload.prompt = generatePrompt(payload);
    }

    // 透传 dayun（若前端已计算并提供）
    if (payload.dayun && typeof payload.dayun !== 'string') {
        try {
            payload.dayun = JSON.stringify(payload.dayun);
        } catch (e) {
            // ignore
        }
    }

    payload.stream = true;

    const backendBaseUrl = getBackendBaseUrl();
    const url = `${backendBaseUrl}/api/interpret`;

    const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

    if (!response.ok) {
        let errBody = "";
        try {
            errBody = await response.text();
        } catch (e) {
            errBody = "";
        }
        throw new Error(`后端解读服务流式调用失败(${response.status}): ${errBody}`);
    }

    if (!response.body || typeof response.body.getReader !== "function") {
        // 兜底：不支持流式就退回整段返回
        const data = await response.json();
        if (!data || typeof data.text !== "string") throw new Error("后端返回格式不正确");
        return data.text;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let full = "";

    while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        if (value) {
            const chunk = decoder.decode(value, { stream: true });
            if (chunk) {
                full += chunk;
                if (typeof onDelta === "function") {
                    // 逐个字符地处理响应数据
                    for (let i = 0; i < chunk.length; i++) {
                        onDelta(chunk[i]);
                    }
                }
            }
        }
    }

    // final flush
    try {
        full += decoder.decode();
    } catch (e) {
        // ignore
    }
    return full;
}

function generatePrompt(baziData) {
    let prompt = '';
    
    // 在提示词开头明确当前日期
    if (baziData.today && baziData.today.solar) {
        prompt += `当前日期：${baziData.today.solar}\n`;
        if (baziData.today.lunar) {
            prompt += `农历：${baziData.today.lunar}\n`;
        }
        prompt += '\n';
    }
    
    prompt += `请根据以下八字信息，提供简洁的命理解读：

八字：${baziData.fullBazi}

请从以下几个方面进行简要解读：
1. 性格特点
2. 优势特长
3. 发展建议
4. 注意事项

请用简洁、实用的语言，控制在200字以内。`;
    
    return prompt;
}

// 兼容旧代码：后端密钥在服务端配置，不再需要前端 setApiKey/switchProvider
function setApiKey() { return false; }
function switchProvider() { return false; }

// 发送聊天消息
async function sendChatMessage(data) {
    const backendBaseUrl = getBackendBaseUrl();
    const url = `${backendBaseUrl}/api/chat/send`;
    
    const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    
    if (!response.ok) {
        let errBody = '';
        try {
            errBody = await response.text();
        } catch (e) {
            errBody = '';
        }
        throw new Error(`发送消息失败(${response.status}): ${errBody}`);
    }
    
    const result = await response.json();
    return result;
}

// 获取聊天历史
async function getChatHistory(sessionId, limit = 50) {
    const backendBaseUrl = getBackendBaseUrl();
    const url = `${backendBaseUrl}/api/chat/history/${sessionId}?limit=${encodeURIComponent(limit)}`;
    
    const response = await fetch(url, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
    });
    
    if (!response.ok) {
        let errBody = '';
        try {
            errBody = await response.text();
        } catch (e) {
            errBody = '';
        }
        throw new Error(`获取历史记录失败(${response.status}): ${errBody}`);
    }
    
    const result = await response.json();
    return result;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { callAI, callAIStream, callHistory, getClientIdentity, setApiKey, switchProvider, sendChatMessage, getChatHistory };
}

// 挂到 window，供 chat_widget.js 直接调用
if (typeof window !== 'undefined') {
    window.baziGetClientIdentity = getClientIdentity;
    window.callHistory = callHistory;
    window.api = {
        sendChatMessage: sendChatMessage,
        getChatHistory: getChatHistory
    };
}
