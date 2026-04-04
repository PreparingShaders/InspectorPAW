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

    // --- Функция обновления SVG-колец ---
    function updateRing(ringId, value, maxValue) {
        const ring = document.getElementById(ringId);
        if (!ring) return;

        const bar = ring.querySelector('.progress-ring-bar');
        const radius = bar.r.baseVal.value;
        const circumference = 2 * Math.PI * radius;
        bar.style.strokeDasharray = `${circumference} ${circumference}`;

        const normalizedValue = maxValue > 0 ? Math.min(value / maxValue, 1) : 0;
        const offset = circumference - (normalizedValue * circumference);
        bar.style.strokeDashoffset = offset;

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

            updateRing('avg-calories-ring', stats.avg_calories, stats.target_calories);
            updateRing('avg-protein-ring', stats.avg_protein, stats.target_protein);
            updateRing('avg-fat-ring', stats.avg_fat, stats.target_fat);
            updateRing('avg-carbs-ring', stats.avg_carbohydrates, stats.target_carbohydrates);

        } catch (error) {
            console.error("Error fetching average stats:", error);
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
        slider.addEventListener('input', (event) => { input.value = event.target.value; });
        input.addEventListener('change', (event) => { slider.value = event.target.value; });
    }
    setupSliderSync('calories-slider', 'calories');
    setupSliderSync('protein-slider', 'protein');
    setupSliderSync('fat-slider', 'fat');
    setupSliderSync('carbohydrates-slider', 'carbohydrates');

    // --- Обработка формы анализа ---
    analyzeForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        errorMessageDiv.textContent = '';
        analyzeButton.disabled = true;
        analyzeButton.textContent = 'Анализируем...';

        const formData = new FormData();
        if (mealImageInput.files.length > 0) formData.append('file', mealImageInput.files[0]);
        if (mealDescriptionInput.value.trim() !== '') formData.append('description', mealDescriptionInput.value.trim());

        if (!mealImageInput.files.length && mealDescriptionInput.value.trim() === '') {
            errorMessageDiv.textContent = 'Пожалуйста, загрузите фото или введите описание.';
            analyzeButton.disabled = false;
            analyzeButton.textContent = 'Анализировать';
            return;
        }

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

        } catch (error) {
            errorMessageDiv.textContent = error.message;
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
    fetchAndDisplayAverageStats();
});
