document.addEventListener('DOMContentLoaded', () => {
    const chatHistory = document.getElementById('chat-history');
    const chatInput = document.getElementById('chat-input');
    const sendButton = document.getElementById('send-button');
    const modelSelectionButton = document.getElementById('model-selection-button');
    const closeModalButton = document.getElementById('close-modal-button');
    const modelSelectionModal = document.getElementById('model-selection-modal');
    const modelListContainer = document.getElementById('model-list');
    const currentModelDisplay = document.getElementById('current-model-display');
    const refreshModelsButton = document.getElementById('refresh-models-button');

    const MAX_MESSAGES = 10;
    const CHAT_HISTORY_KEY = 'aiHubChatHistory';
    const CURRENT_MODEL_KEY = 'aiHubCurrentModel';

    let messages = [];
    let currentModel = localStorage.getItem(CURRENT_MODEL_KEY) || 'google/gemini-flash-1.5';
    let cachedModels = []; // Кэш для моделей

    function updateCurrentModelDisplay() {
        currentModelDisplay.textContent = `Модель: ${currentModel}`;
    }

    function loadHistory() {
        const storedHistory = sessionStorage.getItem(CHAT_HISTORY_KEY);
        if (storedHistory) {
            messages = JSON.parse(storedHistory);
            renderMessages();
        }
    }

    function saveHistory() {
        sessionStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(messages));
    }

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

    function addMessage(sender, text) {
        if (messages.length >= MAX_MESSAGES) {
            messages.shift();
        }
        messages.push({ sender, text });
        renderMessages();
        saveHistory();
    }

    function displayModels(models) {
        modelListContainer.innerHTML = '';
        if (models.length === 0) {
            modelListContainer.innerHTML = '<p class="text-yellow-500">Модели не найдены.</p>';
            return;
        }
        models.forEach(model => {
            const button = document.createElement('button');
            button.textContent = model.name || model.id;
            button.classList.add('w-full', 'text-left', 'p-2', 'rounded-lg', 'hover:bg-gray-700', 'text-white');
            button.dataset.modelId = model.id;
            button.addEventListener('click', () => {
                currentModel = model.id;
                localStorage.setItem(CURRENT_MODEL_KEY, currentModel);
                updateCurrentModelDisplay();
                modelSelectionModal.classList.add('hidden');
            });
            modelListContainer.appendChild(button);
        });
    }

    async function fetchAndTestModels() {
        modelListContainer.innerHTML = '<p class="text-white">Получение и тестирование моделей...</p>';
        try {
            const token = localStorage.getItem('accessToken');
            const response = await fetch('/ai-hub/get-models', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            cachedModels = await response.json();
            displayModels(cachedModels);

        } catch (error) {
            console.error('Failed to fetch models:', error);
            modelListContainer.innerHTML = '<p class="text-red-500">Не удалось загрузить модели.</p>';
        }
    }

    async function handleSend() {
        const text = chatInput.value.trim();
        if (text) {
            addMessage('user', text);
            chatInput.value = '';
            addMessage('ai', '...');

            try {
                const token = localStorage.getItem('accessToken');
                const response = await fetch('/ai-hub/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({
                        model: currentModel,
                        prompt: text,
                        history: messages.slice(0, -2)
                    })
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || 'Ошибка ответа от AI');
                }

                const result = await response.json();
                messages.pop();
                addMessage('ai', result.response);

            } catch (error) {
                messages.pop();
                addMessage('ai', `Ошибка: ${error.message}`);
            }
        }
    }

    modelSelectionButton.addEventListener('click', () => {
        modelSelectionModal.classList.remove('hidden');
        if (cachedModels.length === 0) {
            fetchAndTestModels();
        } else {
            displayModels(cachedModels);
        }
    });

    closeModalButton.addEventListener('click', () => {
        modelSelectionModal.classList.add('hidden');
    });

    refreshModelsButton.addEventListener('click', fetchAndTestModels);

    sendButton.addEventListener('click', handleSend);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            handleSend();
        }
    });

    loadHistory();
    updateCurrentModelDisplay();
});