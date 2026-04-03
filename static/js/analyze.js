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

    // --- Индикация добавления фото ---
    mealImageInput.addEventListener('change', () => {
        const file = mealImageInput.files[0];
        if (file) {
            uploadButtonLabel.classList.add('has-image');
            uploadButtonLabel.textContent = 'Фото добавлено!';
        }
    });

    // --- **КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ:** Надежная синхронизация слайдеров и инпутов ---
    function setupSliderSync(sliderId, inputId) {
        const slider = document.getElementById(sliderId);
        const input = document.getElementById(inputId);

        // Обновляет инпут, когда двигается слайдер
        slider.addEventListener('input', (event) => {
            input.value = event.target.value;
        });

        // Обновляет слайдер, когда меняется значение в инпуте
        input.addEventListener('change', (event) => {
            slider.value = event.target.value;
        });
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

            // Обновляем значения и в инпутах, и в слайдерах
            const fields = ['calories', 'protein', 'fat', 'carbohydrates'];
            fields.forEach(field => {
                const value = Math.round(result.suggested_totals[`total_${field}`] || 0);
                document.getElementById(field).value = value;
                document.getElementById(`${field}-slider`).value = value;
            });

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
        // ... (остальной код без изменений)
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
});
