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

    const CURRENT_MODEL_KEY = 'aiHubCurrentModel';

    let currentModel = localStorage.getItem(CURRENT_MODEL_KEY) || 'google/gemini-flash-1.5';
    let cachedModels = [];

    function updateCurrentModelDisplay() {
        currentModelDisplay.textContent = `Модель: ${currentModel}`;
    }

    // Функция просто создает и возвращает DOM-элемент сообщения
    function createBubble(sender, text) {
        const bubble = document.createElement('div');
        bubble.classList.add('chat-bubble', sender);
        bubble.innerHTML = text.replace(/\n/g, '<br>');
        return bubble;
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
                // При смене модели просто очищаем видимый чат
                chatHistory.innerHTML = '';
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
            const userPrompt = text;
            chatInput.value = '';

            // 1. ПОЛНОСТЬЮ ОЧИЩАЕМ видимый чат
            chatHistory.innerHTML = '';

            // 2. Отображаем ТОЛЬКО текущий вопрос и плейсхолдер ответа
            const userBubble = createBubble('user', userPrompt);
            const aiBubble = createBubble('ai', '...');
            chatHistory.appendChild(userBubble);
            chatHistory.appendChild(aiBubble);

            try {
                const token = localStorage.getItem('accessToken');

                const response = await fetch('/ai-hub/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                    body: JSON.stringify({
                        model: currentModel,
                        prompt: userPrompt,
                        history: [] // ИСТОРИЯ ВСЕГДА ПУСТАЯ
                    })
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || 'Ошибка ответа от AI');
                }

                const result = await response.json();

                // 3. Обновляем текст плейсхолдера реальным ответом
                aiBubble.innerHTML = result.response.replace(/\n/g, '<br>');

            } catch (error) {
                aiBubble.innerHTML = `Ошибка: ${error.message}`.replace(/\n/g, '<br>');
            }
        }
    }

    // --- Слушатели событий ---
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

    // --- Инициализация ---
    updateCurrentModelDisplay();
});