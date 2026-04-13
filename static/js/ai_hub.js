document.addEventListener('DOMContentLoaded', () => {
    const chatHistory = document.getElementById('chat-history');
    const chatInput = document.getElementById('chat-input');
    const sendButton = document.getElementById('send-button');

    const MAX_MESSAGES = 6;
    const STORAGE_KEY = 'aiHubChatHistory';

    let messages = [];

    // Загрузка истории из sessionStorage
    function loadHistory() {
        const storedHistory = sessionStorage.getItem(STORAGE_KEY);
        if (storedHistory) {
            messages = JSON.parse(storedHistory);
            renderMessages();
        }
    }

    // Сохранение истории в sessionStorage
    function saveHistory() {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    }

    // Рендер сообщений
    function renderMessages() {
        chatHistory.innerHTML = '';
        messages.forEach(msg => {
            const bubble = document.createElement('div');
            bubble.classList.add('chat-bubble', msg.sender);
            bubble.textContent = msg.text;
            chatHistory.appendChild(bubble);
        });
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    // Добавление сообщения
    function addMessage(sender, text) {
        if (messages.length >= MAX_MESSAGES) {
            messages.shift(); // Удаляем самое старое сообщение
        }
        messages.push({ sender, text });
        renderMessages();
        saveHistory();
    }

    // Обработка отправки
    function handleSend() {
        const text = chatInput.value.trim();
        if (text) {
            addMessage('user', text);
            chatInput.value = '';
            // Симуляция ответа AI
            setTimeout(() => {
                addMessage('ai', `Это симуляция ответа на: "${text}"`);
            }, 1000);
        }
    }

    sendButton.addEventListener('click', handleSend);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            handleSend();
        }
    });

    loadHistory();
});