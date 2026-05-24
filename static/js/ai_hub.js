document.addEventListener('DOMContentLoaded', () => {
    // --- Глобальный перехватчик для fetch ---
    async function fetchWithAuth(url, options = {}) {
        const token = localStorage.getItem('accessToken');

        // Добавляем заголовок авторизации, если он еще не установлен
        if (token && !options.headers?.Authorization) {
            if (!options.headers) {
                options.headers = {};
            }
            options.headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(url, options);

        // Если токен истек или невалиден, выходим из системы
        if (response.status === 401) {
            localStorage.removeItem('accessToken');
            window.location.href = '/login';
            // Возвращаем "пустой" Promise, чтобы остановить выполнение цепочки .then()
            return new Promise(() => {});
        }

        return response;
    }

    const chatHistory = document.getElementById('chat-history');
    const chatInput = document.getElementById('chat-input');
    const sendButton = document.getElementById('send-button');
    const modelSelectionButton = document.getElementById('model-selection-button');
    const closeModalButton = document.getElementById('close-modal-button');
    const modelSelectionModal = document.getElementById('model-selection-modal');
    const modelListContainer = document.getElementById('model-list');
    const currentModelDisplay = document.getElementById('current-model-display');
    const refreshModelsButton = document.getElementById('refresh-models-button');
    const mainContent = document.querySelector('main'); // Получаем основной контейнер

    const CURRENT_MODEL_KEY = 'aiHubCurrentModel';

    let currentModel = localStorage.getItem(CURRENT_MODEL_KEY) || null;
    let cachedModels = [];

    function updateCurrentModelDisplay() {
        if (currentModel) {
            currentModelDisplay.textContent = `Модель: ${currentModel}`;
        } else {
            currentModelDisplay.textContent = 'Модель не выбрана';
        }
    }

    function createBubble(sender, text) {
        const bubble = document.createElement('div');
        bubble.classList.add('chat-bubble', sender);
        bubble.innerHTML = text.replace(/\n/g, '<br>');
        return bubble;
    }

    // Обновленная функция для отображения моделей
    function displayModels(models) {
        modelListContainer.innerHTML = '';
        if (models.length === 0) {
            modelListContainer.innerHTML = '<p class="text-yellow-500 p-4 text-center">Модели не найдены.</p>';
            return;
        }
        models.forEach(model => {
            const item = document.createElement('div');
            item.classList.add('model-item');
            if (model.id === currentModel) {
                item.classList.add('selected');
            }

            const modelName = document.createElement('span');
            modelName.textContent = model.name || model.id;

            const checkmark = document.createElement('span');
            checkmark.classList.add('checkmark');
            checkmark.innerHTML = '&#10003;'; // Галочка

            item.appendChild(modelName);
            item.appendChild(checkmark);

            item.addEventListener('click', () => {
                currentModel = model.id;
                localStorage.setItem(CURRENT_MODEL_KEY, currentModel);
                updateCurrentModelDisplay();
                // Обновляем выделение в списке
                document.querySelectorAll('.model-item').forEach(el => el.classList.remove('selected'));
                item.classList.add('selected');
                // Закрываем модальное окно после выбора
                setTimeout(() => {
                    modelSelectionModal.classList.add('hidden');
                }, 200);
            });
            modelListContainer.appendChild(item);
        });
    }

    async function fetchAndTestModels() {
        refreshModelsButton.querySelector('svg').classList.add('animate-spin');
        modelListContainer.innerHTML = '<p class="text-white p-4 text-center">Загрузка моделей...</p>';
        try {
            const response = await fetchWithAuth('/ai-hub/get-models');
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            cachedModels = await response.json();

            if (!currentModel && cachedModels.length > 0) {
                currentModel = cachedModels[0].id;
                localStorage.setItem(CURRENT_MODEL_KEY, currentModel);
            }

            updateCurrentModelDisplay();
            displayModels(cachedModels);

        } catch (error) {
            console.error('Failed to fetch models:', error);
            modelListContainer.innerHTML = '<p class="text-red-500 p-4 text-center">Не удалось загрузить модели.</p>';
        } finally {
            refreshModelsButton.querySelector('svg').classList.remove('animate-spin');
        }
    }

    function scrollToBottom() {
        mainContent.scrollTop = mainContent.scrollHeight;
    }

    async function handleSend() {
        const text = chatInput.value.trim();
        if (text && currentModel) {
            const userPrompt = text;
            chatInput.value = '';

            const userBubble = createBubble('user', userPrompt);
            const aiBubble = createBubble('ai', '...');

            // Добавляем сообщения в конец
            chatHistory.appendChild(userBubble);
            chatHistory.appendChild(aiBubble);

            // Прокручиваем к последнему сообщению
            scrollToBottom();

            try {
                const response = await fetchWithAuth('/ai-hub/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        model: currentModel,
                        prompt: userPrompt,
                        history: [] // История пока не передается
                    })
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || 'Ошибка ответа от AI');
                }

                const result = await response.json();
                aiBubble.innerHTML = result.response.replace(/\n/g, '<br>');

            } catch (error) {
                aiBubble.innerHTML = `Ошибка: ${error.message}`.replace(/\n/g, '<br>');
            } finally {
                // Еще раз прокручиваем после получения ответа, если контент изменил высоту
                scrollToBottom();
            }
        } else if (!currentModel) {
            chatInput.placeholder = "Сначала выберите модель";
        }
    }

    // --- Слушатели событий ---
    modelSelectionButton.addEventListener('click', () => {
        modelSelectionModal.classList.remove('hidden');
        fetchAndTestModels();
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
    if (currentModel) {
        updateCurrentModelDisplay();
    }
    fetchAndTestModels();
});