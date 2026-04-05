document.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('accessToken');
    if (!token) {
        window.location.href = '/';
        return;
    }

    // --- Элементы DOM ---
    const analyzeForm = document.getElementById('analyze-form');
    const mealImageInput = document.getElementById('meal-image');
    const mealDescriptionInput = document.getElementById('meal-description');
    const analyzeButton = document.getElementById('analyze-button');
    const resultsSection = document.getElementById('results-section');
    const aiResponseTextDiv = document.getElementById('ai-response-text');
    const confirmForm = document.getElementById('confirm-form');
    const errorMessageDiv = document.getElementById('error-message');
    const uploadButtonLabel = document.querySelector('.upload-button-label');
    const mealLogsContainer = document.getElementById('meal-logs-container');

    // --- Конфигурация цветов overflow по типу макронутриента ---
    const OVERFLOW_STYLES = {
        calories:  { glowClass: 'overflow-glow-red'   },
        protein:   { glowClass: 'overflow-glow-green' },
        fat:       { glowClass: 'overflow-glow-red'   },
        carbs:     { glowClass: 'overflow-glow-red'   },
    };

    // Определяем тип макронутриента по ID кольца
    function getMacroType(ringId) {
        if (ringId.includes('protein'))   return 'protein';
        if (ringId.includes('fat'))       return 'fat';
        if (ringId.includes('carbs') || ringId.includes('carbohydrates')) return 'carbs';
        return 'calories'; // default
    }

    // --- Новая функция обновления SVG-колец с переполнением ---
    function updateRingWithOverflow(ringId, value, maxValue) {
        const ring = document.getElementById(ringId);
        if (!ring) return;

        const type = getMacroType(ringId);
        const style = OVERFLOW_STYLES[type];
        const bar = ring.querySelector('.progress-ring-bar');
        const overflowBar = ring.querySelector('.progress-ring-overflow');
        const container = ring.closest('.ring-container');
        const radius = bar.r.baseVal.value;
        const circumference = 2 * Math.PI * radius;

        bar.style.strokeDasharray = `${circumference} ${circumference}`;
        if (overflowBar) overflowBar.style.strokeDasharray = `${circumference} ${circumference}`;

        // Убираем старые glow-классы
        if (container) container.classList.remove('overflow-glow-red', 'overflow-glow-green');
        if (overflowBar) overflowBar.classList.remove('overflow-red', 'overflow-green');

        if (maxValue === 0) {
            bar.style.strokeDashoffset = circumference;
            if (overflowBar) overflowBar.style.strokeDashoffset = circumference;
            return;
        }

        const percentage = value / maxValue;

        // Основной бар (до 100%)
        const mainPercentage = Math.min(percentage, 1);
        const mainOffset = circumference - (mainPercentage * circumference);
        bar.style.strokeDashoffset = mainOffset;

        // Бар переполнения (после 100%)
        if (overflowBar) {
            if (percentage > 1) {
                const overflowColorClass = type === 'protein' ? 'overflow-green' : 'overflow-red';
                overflowBar.classList.add(overflowColorClass);
                if (container) container.classList.add(style.glowClass);

                const overflowPercentage = Math.min(percentage - 1, 1);
                const overflowOffset = circumference - (overflowPercentage * circumference);
                overflowBar.style.strokeDashoffset = overflowOffset;
            } else {
                overflowBar.style.strokeDashoffset = circumference;
            }
        }

        const valueElementId = ringId.replace('-ring', '-value');
        const valueElement = document.getElementById(valueElementId);
        if (valueElement) {
            valueElement.textContent = Math.round(value);
        }
    }

    // --- Загрузка и отображение средних данных ---
    async function fetchAndDisplayAverageStats() {
        try {
            const response = await fetch('/users/me/average-stats', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) throw new Error('Could not fetch average stats.');

            const stats = await response.json();
            updateRingWithOverflow('avg-calories-ring', stats.avg_calories, stats.target_calories);
            updateRingWithOverflow('avg-protein-ring', stats.avg_protein, stats.target_protein);
            updateRingWithOverflow('avg-fat-ring', stats.avg_fat, stats.target_fat);
            updateRingWithOverflow('avg-carbs-ring', stats.avg_carbohydrates, stats.target_carbohydrates);

            mealLogsContainer.dataset.targetCalories = stats.target_calories;
            mealLogsContainer.dataset.targetProtein = stats.target_protein;
            mealLogsContainer.dataset.targetFat = stats.target_fat;
            mealLogsContainer.dataset.targetCarbohydrates = stats.target_carbohydrates;

        } catch (error) {
            console.error("Error fetching average stats:", error);
        }
    }

    // --- Загрузка и отображение всех логов с кольцами ---
    async function fetchAndDisplayMealHistory() {
        try {
            const response = await fetch('/meals/', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) throw new Error(`Could not fetch meal history. Status: ${response.status}`);

            const meals = await response.json();
            mealLogsContainer.innerHTML = '';

            if (meals.length === 0) {
                mealLogsContainer.innerHTML = `<p class="text-center text-gray-500 mt-4">Записей о приемах пищи еще нет.</p>`;
                return;
            }

            const mealsByDate = meals.reduce((acc, meal) => {
                const dateKey = new Date(meal.timestamp).toLocaleDateString('ru-RU');
                if (!acc[dateKey]) acc[dateKey] = [];
                acc[dateKey].push(meal);
                return acc;
            }, {});

            const today = new Date().toLocaleDateString('ru-RU');
            const yesterday = new Date(Date.now() - 86400000).toLocaleDateString('ru-RU');
            const mealTypeTranslations = {
                breakfast: 'Завтрак',
                lunch: 'Обед',
                dinner: 'Ужин',
                snack: 'Перекус'
            };

            for (const dateKey in mealsByDate) {
                let dateLabel = (dateKey === today) ? 'Сегодня' : (dateKey === yesterday) ? 'Вчера' : dateKey;
                const divider = document.createElement('div');
                divider.className = 'date-divider';
                divider.innerHTML = `<span>${dateLabel}</span>`;
                mealLogsContainer.appendChild(divider);

                const mealsOnDate = mealsByDate[dateKey];
                mealsOnDate.forEach(meal => {
                    const mealId = meal.id;
                    const mealType = mealTypeTranslations[meal.meal_type] || 'Прием пищи';
                    const card = document.createElement('div');
                    card.className = 'glassmorphism rounded-xl p-4 neon-glow-pantone-gray';

                    card.innerHTML = `
                        <h4 class="text-lg font-semibold text-center mb-4">${mealType}</h4>
                        <div class="flex justify-around w-full">
                            <div class="text-center flex flex-col items-center space-y-1">
                                <div class="ring-container w-16 aspect-square neon-glow-amber relative">
                                    <svg id="log-${mealId}-calories-ring" class="progress-ring-svg" viewBox="0 0 120 120"><circle class="progress-ring-bg" cx="60" cy="60" r="54"/><circle class="progress-ring-bar" cx="60" cy="60" r="54" style="stroke: var(--color-amber);"/><circle class="progress-ring-overflow" cx="60" cy="60" r="54"/></svg>
                                    <div class="absolute inset-0 flex flex-col items-center justify-center"><span id="log-${mealId}-calories-value" class="font-bold text-lg" style="color: var(--color-amber);">0</span><span class="label-text text-xs -mt-1">ккал</span></div>
                                </div>
                            </div>
                            <div class="text-center flex flex-col items-center space-y-1">
                                <div class="ring-container w-16 aspect-square neon-glow-protein-white relative">
                                    <svg id="log-${mealId}-protein-ring" class="progress-ring-svg" viewBox="0 0 120 120"><circle class="progress-ring-bg" cx="60" cy="60" r="54"/><circle class="progress-ring-bar" cx="60" cy="60" r="54" style="stroke: var(--color-protein-white);"/><circle class="progress-ring-overflow" cx="60" cy="60" r="54"/></svg>
                                    <div class="absolute inset-0 flex flex-col items-center justify-center"><span id="log-${mealId}-protein-value" class="font-bold text-lg" style="color: var(--color-protein-white);">0</span><span class="label-text text-xs -mt-1">г</span></div>
                                </div>
                            </div>
                            <div class="text-center flex flex-col items-center space-y-1">
                                <div class="ring-container w-16 aspect-square neon-glow-golden-orange relative">
                                    <svg id="log-${mealId}-fat-ring" class="progress-ring-svg" viewBox="0 0 120 120"><circle class="progress-ring-bg" cx="60" cy="60" r="54"/><circle class="progress-ring-bar" cx="60" cy="60" r="54" style="stroke: var(--color-golden-orange);"/><circle class="progress-ring-overflow" cx="60" cy="60" r="54"/></svg>
                                    <div class="absolute inset-0 flex flex-col items-center justify-center"><span id="log-${mealId}-fat-value" class="font-bold text-lg" style="color: var(--color-golden-orange);">0</span><span class="label-text text-xs -mt-1">г</span></div>
                                </div>
                            </div>
                            <div class="text-center flex flex-col items-center space-y-1">
                                <div class="ring-container w-16 aspect-square neon-glow-muted-teal relative">
                                    <svg id="log-${mealId}-carbohydrates-ring" class="progress-ring-svg" viewBox="0 0 120 120"><circle class="progress-ring-bg" cx="60" cy="60" r="54"/><circle class="progress-ring-bar" cx="60" cy="60" r="54" style="stroke: var(--color-muted-teal);"/><circle class="progress-ring-overflow" cx="60" cy="60" r="54"/></svg>
                                    <div class="absolute inset-0 flex flex-col items-center justify-center"><span id="log-${mealId}-carbohydrates-value" class="font-bold text-lg" style="color: var(--color-muted-teal);">0</span><span class="label-text text-xs -mt-1">г</span></div>
                                </div>
                            </div>
                        </div>
                    `;
                    mealLogsContainer.appendChild(card);

                    const targetCalories = parseFloat(mealLogsContainer.dataset.targetCalories || 0);
                    const targetProtein = parseFloat(mealLogsContainer.dataset.targetProtein || 0);
                    const targetFat = parseFloat(mealLogsContainer.dataset.targetFat || 0);
                    const targetCarbohydrates = parseFloat(mealLogsContainer.dataset.targetCarbohydrates || 0);

                    updateRingWithOverflow(`log-${mealId}-calories-ring`, meal.total_calories, targetCalories);
                    updateRingWithOverflow(`log-${mealId}-protein-ring`, meal.total_protein, targetProtein);
                    updateRingWithOverflow(`log-${mealId}-fat-ring`, meal.total_fat, targetFat);
                    updateRingWithOverflow(`log-${mealId}-carbohydrates-ring`, meal.total_carbohydrates, targetCarbohydrates);
                });
            }
        } catch (error) {
            console.error("Error in fetchAndDisplayMealHistory:", error);
            mealLogsContainer.innerHTML = `<p class="text-center text-red-500 mt-4">Не удалось загрузить историю приемов пищи.</p>`;
        }
    }

    // --- Индикация добавления фото ---
    mealImageInput.addEventListener('change', () => {
        const file = mealImageInput.files[0];
        if (file) {
            uploadButtonLabel.classList.add('has-image');
            uploadButtonLabel.textContent = 'Фото добавлено!';
        }
    });

    // --- Синхронизация слайдеров и инпутов ---
    function setupSliderSync(sliderId, inputId) {
        const slider = document.getElementById(sliderId);
        const input = document.getElementById(inputId);
        if (slider && input) {
            slider.addEventListener('input', (event) => { input.value = event.target.value; });
            input.addEventListener('change', (event) => { slider.value = event.target.value; });
        }
    }
    setupSliderSync('calories-slider', 'calories');
    setupSliderSync('protein-slider', 'protein');
    setupSliderSync('fat-slider', 'fat');
    setupSliderSync('carbohydrates-slider', 'carbohydrates');

    // --- Утилита сжатия фото через Canvas ---
    async function compressImage(file, maxSize = 1024, quality = 0.85) {
        return new Promise((resolve) => {
            const img = new Image();
            img.onload = () => {
                const canvas = document.createElement('canvas');
                let width = img.width;
                let height = img.height;

                if (width > maxSize || height > maxSize) {
                    if (width > height) {
                        height = Math.round((height * maxSize) / width);
                        width = maxSize;
                    } else {
                        width = Math.round((width * maxSize) / height);
                        height = maxSize;
                    }
                }

                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, width, height);

                canvas.toBlob((blob) => {
                    resolve(blob);
                }, 'image/jpeg', quality);
            };
            img.src = URL.createObjectURL(file);
        });
    }

    // --- Функции статуса анализа ---
    const statusMessages = [
        'Загружаем фото...',
        'Ищем еду на изображении...',
        'Определяем размер порции...',
        'Считаем КБЖУ...',
        'Почти готово...'
    ];

    function showAnalysisStatus(index) {
        analysisStatus.innerHTML = `<span class="spinner"></span>${statusMessages[index]}`;
        analysisStatus.classList.add('visible');
    }

    function hideAnalysisStatus() {
        analysisStatus.classList.remove('visible');
        if (statusInterval) clearInterval(statusInterval);
    }

    // --- Обработка формы анализа ---
    let statusInterval;
    const analysisStatus = document.getElementById('analysis-status');

    analyzeForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        errorMessageDiv.textContent = '';
        analyzeButton.disabled = true;
        analyzeButton.textContent = 'Ждите...';

        const formData = new FormData();

        if (mealImageInput.files.length > 0) {
            const originalFile = mealImageInput.files[0];
            analyzeButton.textContent = 'Подготовка фото...';
            const compressedFile = await compressImage(originalFile);
            formData.append('file', compressedFile, originalFile.name);
        }

        if (mealDescriptionInput.value.trim() !== '') formData.append('description', mealDescriptionInput.value.trim());

        if (!mealImageInput.files.length && mealDescriptionInput.value.trim() === '') {
            errorMessageDiv.textContent = 'Пожалуйста, загрузите фото или введите описание.';
            analyzeButton.disabled = false;
            analyzeButton.textContent = 'Анализировать';
            return;
        }

        // Запускаем последовательное обновление статуса
        let statusIndex = 0;
        showAnalysisStatus(statusIndex);
        statusInterval = setInterval(() => {
            statusIndex = (statusIndex + 1) % statusMessages.length;
            showAnalysisStatus(statusIndex);
        }, 3000);

        try {
            const response = await fetch('/analyze-meal/', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Ошибка анализа блюда.');
            }

            clearInterval(statusInterval);
            const result = await response.json();
            aiResponseTextDiv.innerHTML = `<p>${result.ai_response_text}</p>`;

            const fieldsConfig = {
                calories: { minBuffer: 500, step: 10 },
                protein: { minBuffer: 30, step: 1 },
                fat: { minBuffer: 20, step: 1 },
                carbohydrates: { minBuffer: 40, step: 1 }
            };

            for (const field in fieldsConfig) {
                const config = fieldsConfig[field];
                const value = Math.round(result.suggested_totals[`total_${field}`] || 0);
                const buffer = Math.max(value * 0.5, config.minBuffer);
                const minValue = Math.max(0, Math.floor((value - buffer) / config.step) * config.step);
                const maxValue = Math.ceil((value + buffer) / config.step) * config.step;

                const slider = document.getElementById(`${field}-slider`);
                const input = document.getElementById(field);
                slider.min = minValue;
                slider.max = maxValue;
                slider.value = value;
                input.value = value;
            }

            resultsSection.style.display = 'block';
            analysisStatus.innerHTML = '<span style="color: #50C878;">✓ Анализ завершён!</span>';
            setTimeout(hideAnalysisStatus, 2000);

        } catch (error) {
            clearInterval(statusInterval);
            errorMessageDiv.textContent = error.message;
            hideAnalysisStatus();
        } finally {
            analyzeButton.disabled = false;
            analyzeButton.textContent = 'Анализировать';
        }
    });

    // --- Обработка формы подтверждения ---
    confirmForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        errorMessageDiv.textContent = '';
        const confirmButton = document.getElementById('confirm-button');
        confirmButton.disabled = true;
        confirmButton.textContent = 'Добавляем...';

        const mealData = {
            meal_type: document.getElementById('meal-type').value,
            total_calories: parseFloat(document.getElementById('calories').value),
            total_protein: parseFloat(document.getElementById('protein').value),
            total_fat: parseFloat(document.getElementById('fat').value),
            total_carbohydrates: parseFloat(document.getElementById('carbohydrates').value),
        };

        try {
            const response = await fetch('/meals/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify(mealData)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Ошибка добавления приема пищи.');
            }

            window.location.href = '/dashboard';

        } catch (error) {
            errorMessageDiv.textContent = error.message;
        } finally {
            confirmButton.disabled = false;
            confirmButton.textContent = 'Добавить прием пищи';
        }
    });

    // --- Инициализация страницы ---
    await fetchAndDisplayAverageStats();
    await fetchAndDisplayMealHistory();
});