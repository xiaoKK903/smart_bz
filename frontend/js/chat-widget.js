class ChatWidget extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this.sessionId = this._generateSessionId();
    this.messages = [];
    this.isOpen = false;
  }

  static get observedAttributes() {
    return ['api-url', 'tenant-id', 'theme-color', 'welcome-message', 'avatar'];
  }

  attributeChangedCallback(name, oldValue, newValue) {
    if (name === 'theme-color') {
      this._updateThemeColor(newValue);
    }
  }

  connectedCallback() {
    this.render();
    this._attachEventListeners();
  }

  disconnectedCallback() {
    // 清理事件监听器
  }

  _generateSessionId() {
    return 'chat_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
  }

  _updateThemeColor(color) {
    const style = this.shadowRoot.querySelector('style');
    if (style) {
      style.textContent = style.textContent.replace(/--theme-color: [^;]+;/, `--theme-color: ${color};`);
    }
  }

  _attachEventListeners() {
    const launcher = this.shadowRoot.getElementById('chat-launcher');
    const closeBtn = this.shadowRoot.getElementById('chat-close');
    const sendBtn = this.shadowRoot.getElementById('chat-send');
    const input = this.shadowRoot.getElementById('chat-input');

    if (launcher) {
      launcher.addEventListener('click', () => this._openChat());
    }

    if (closeBtn) {
      closeBtn.addEventListener('click', () => this._closeChat());
    }

    if (sendBtn) {
      sendBtn.addEventListener('click', () => this._sendMessage());
    }

    if (input) {
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this._sendMessage();
        }
      });
    }
  }

  _openChat() {
    this.isOpen = true;
    this.render();
    this._loadHistory();
  }

  _closeChat() {
    this.isOpen = false;
    this.render();
  }

  async _loadHistory() {
    try {
      const apiUrl = this.getAttribute('api-url') || 'http://localhost:8000/api';
      const response = await fetch(`${apiUrl}/chat/history`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          session_id: this.sessionId,
          user_id: this._getUserId(),
          tenant_id: this.getAttribute('tenant-id') || 'default'
        })
      });

      if (response.ok) {
        const data = await response.json();
        if (data.history) {
          this.messages = data.history;
          this.render();
        }
      }
    } catch (error) {
      console.error('Failed to load chat history:', error);
    }
  }

  async _sendMessage() {
    const input = this.shadowRoot.getElementById('chat-input');
    const message = input.value.trim();
    
    if (!message) return;

    // 添加用户消息到界面
    this.messages.push({ role: 'user', content: message });
    input.value = '';
    this.render();

    try {
      const apiUrl = this.getAttribute('api-url') || 'http://localhost:8000/api';
      const response = await fetch(`${apiUrl}/chat/message`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          session_id: this.sessionId,
          user_id: this._getUserId(),
          tenant_id: this.getAttribute('tenant-id') || 'default',
          message: message
        })
      });

      if (response.ok) {
        const data = await response.json();
        if (data.reply) {
          // 添加助手回复到界面
          this.messages.push({ role: 'assistant', content: data.reply });
          this.render();
        }
      } else {
        throw new Error('Failed to get response');
      }
    } catch (error) {
      console.error('Failed to send message:', error);
      // 添加错误消息到界面
      this.messages.push({ role: 'assistant', content: '抱歉，系统暂时无法响应，请稍后再试。' });
      this.render();
    }
  }

  _getUserId() {
    let userId = localStorage.getItem('chat_user_id');
    if (!userId) {
      userId = 'user_' + Math.random().toString(36).substr(2, 9);
      localStorage.setItem('chat_user_id', userId);
    }
    return userId;
  }

  _renderMessages() {
    if (this.messages.length === 0) {
      const welcomeMessage = this.getAttribute('welcome-message') || '您好！我是智能客服助手，有什么可以帮助您的吗？';
      return `
        <div class="message bot-message">
          <div class="message-content">${welcomeMessage}</div>
        </div>
      `;
    }

    return this.messages.map(msg => `
      <div class="message ${msg.role === 'user' ? 'user-message' : 'bot-message'}">
        <div class="message-content">${this._parseMarkdown(msg.content)}</div>
      </div>
    `).join('');
  }

  _parseMarkdown(text) {
    if (!text) return '';
    
    // 简单的Markdown解析
    return text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/\n/g, '<br>');
  }

  render() {
    const themeColor = this.getAttribute('theme-color') || '#4A90E2';
    const avatar = this.getAttribute('avatar') || '';

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          --theme-color: ${themeColor};
          display: block;
          position: fixed;
          bottom: 20px;
          right: 20px;
          z-index: 9999;
        }

        .chat-launcher {
          width: 60px;
          height: 60px;
          border-radius: 50%;
          background-color: var(--theme-color);
          color: white;
          border: none;
          box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 24px;
          transition: all 0.3s ease;
        }

        .chat-launcher:hover {
          transform: scale(1.1);
          box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
        }

        .chat-container {
          display: ${this.isOpen ? 'block' : 'none'};
          width: 360px;
          height: 500px;
          background-color: white;
          border-radius: 10px;
          box-shadow: 0 5px 25px rgba(0, 0, 0, 0.2);
          flex-direction: column;
          overflow: hidden;
        }

        .chat-header {
          background-color: var(--theme-color);
          color: white;
          padding: 15px;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .chat-header h2 {
          margin: 0;
          font-size: 16px;
        }

        .chat-close {
          background: none;
          border: none;
          color: white;
          font-size: 18px;
          cursor: pointer;
        }

        .chat-body {
          flex: 1;
          padding: 15px;
          overflow-y: auto;
          background-color: #f5f5f5;
        }

        .message {
          margin-bottom: 15px;
          max-width: 80%;
        }

        .user-message {
          align-self: flex-end;
          margin-left: auto;
        }

        .bot-message {
          align-self: flex-start;
        }

        .message-content {
          padding: 10px 15px;
          border-radius: 18px;
          line-height: 1.4;
        }

        .user-message .message-content {
          background-color: var(--theme-color);
          color: white;
          border-bottom-right-radius: 4px;
        }

        .bot-message .message-content {
          background-color: white;
          color: #333;
          border-bottom-left-radius: 4px;
          box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
        }

        .chat-footer {
          padding: 10px;
          background-color: white;
          border-top: 1px solid #e0e0e0;
          display: flex;
        }

        .chat-input {
          flex: 1;
          padding: 10px;
          border: 1px solid #e0e0e0;
          border-radius: 20px;
          margin-right: 10px;
          outline: none;
        }

        .chat-send {
          background-color: var(--theme-color);
          color: white;
          border: none;
          border-radius: 50%;
          width: 40px;
          height: 40px;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        @media (max-width: 480px) {
          .chat-container {
            width: calc(100vw - 40px);
            height: 70vh;
          }
        }
      </style>

      ${!this.isOpen ? `
        <button id="chat-launcher" class="chat-launcher">
          💬
        </button>
      ` : `
        <div class="chat-container">
          <div class="chat-header">
            <h2>智能客服</h2>
            <button id="chat-close" class="chat-close">×</button>
          </div>
          <div class="chat-body">
            ${this._renderMessages()}
          </div>
          <div class="chat-footer">
            <input type="text" id="chat-input" class="chat-input" placeholder="请输入您的问题...">
            <button id="chat-send" class="chat-send">→</button>
          </div>
        </div>
      `}
    `;

    // 重新附加事件监听器
    this._attachEventListeners();

    // 滚动到底部
    if (this.isOpen) {
      const chatBody = this.shadowRoot.querySelector('.chat-body');
      if (chatBody) {
        chatBody.scrollTop = chatBody.scrollHeight;
      }
    }
  }
}

// 定义自定义元素
customElements.define('chat-widget', ChatWidget);