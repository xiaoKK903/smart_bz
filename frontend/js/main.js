// 全局变量
let sessionId = null;
const userId = `user_${Math.random().toString(36).substr(2, 9)}`;
const tenantId = 'default';

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 初始化聊天组件
    initChatWidget();
    
    // 绑定发送按钮事件
    document.getElementById('send-button').addEventListener('click', sendMessage);
    
    // 绑定输入框回车事件
    document.getElementById('message-input').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
});

// 初始化聊天组件
function initChatWidget() {
    console.log('初始化聊天组件');
    // 可以在这里添加初始化逻辑
}

// 发送消息
async function sendMessage() {
    const inputElement = document.getElementById('message-input');
    const message = inputElement.value.trim();
    
    if (!message) return;
    
    // 清空输入框
    inputElement.value = '';
    
    // 添加用户消息到聊天界面
    addMessage('user', message);
    
    // 显示加载状态
    const loadingMessageId = addMessage('bot', '正在思考...', true);
    
    try {
        // 调用API发送消息
        const response = await api.sendChatMessage({
            tenant_id: tenantId,
            session_id: sessionId,
            user_id: userId,
            message: message
        });
        
        // 更新会话ID
        sessionId = response.session_id;
        
        // 移除加载状态
        removeMessage(loadingMessageId);
        
        // 添加机器人回复
        addMessage('bot', response.reply);
        
        // 添加快速回复选项
        if (response.quick_replies && response.quick_replies.length > 0) {
            addQuickReplies(response.quick_replies);
        }
    } catch (error) {
        console.error('发送消息失败:', error);
        // 移除加载状态
        removeMessage(loadingMessageId);
        // 添加错误消息
        addMessage('bot', '抱歉，我暂时无法回答您的问题，请稍后再试。');
    }
}

// 添加消息到聊天界面
function addMessage(role, content, isLoading = false) {
    const chatBody = document.getElementById('chat-body');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role === 'user' ? 'user-message' : 'bot-message'}`;
    
    if (isLoading) {
        messageDiv.id = `loading_${Date.now()}`;
    }
    
    messageDiv.innerHTML = `
        <div class="message-content">
            ${content}
        </div>
    `;
    
    chatBody.appendChild(messageDiv);
    chatBody.scrollTop = chatBody.scrollHeight;
    
    return messageDiv.id;
}

// 移除消息
function removeMessage(messageId) {
    const message = document.getElementById(messageId);
    if (message) {
        message.remove();
    }
}

// 添加快速回复选项
function addQuickReplies(quickReplies) {
    const chatBody = document.getElementById('chat-body');
    const quickRepliesDiv = document.createElement('div');
    quickRepliesDiv.className = 'quick-replies';
    
    quickReplies.forEach(reply => {
        const button = document.createElement('button');
        button.className = 'quick-reply-button';
        button.textContent = reply;
        button.addEventListener('click', function() {
            document.getElementById('message-input').value = reply;
            sendMessage();
        });
        quickRepliesDiv.appendChild(button);
    });
    
    chatBody.appendChild(quickRepliesDiv);
    chatBody.scrollTop = chatBody.scrollHeight;
}

// 模拟数据（用于测试）
const mockResponse = {
    session_id: 'test_session_123',
    reply: '您好！我是智能客服助手，很高兴为您服务。请问有什么可以帮助您的吗？',
    intent: 'greeting',
    confidence: 0.95,
    quick_replies: [
        '我想了解商品信息',
        '我需要退换货',
        '如何查询订单状态'
    ]
};

// 测试发送消息
function testSendMessage() {
    const inputElement = document.getElementById('message-input');
    const message = inputElement.value.trim();
    
    if (!message) return;
    
    inputElement.value = '';
    addMessage('user', message);
    
    setTimeout(() => {
        addMessage('bot', mockResponse.reply);
        addQuickReplies(mockResponse.quick_replies);
    }, 1000);
}