document.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('accessToken');
    if (!token) {
        window.location.href = '/';
        return;
    }

    const analyzeForm = document.getElementById('analyze-form');
    const mealImageInput = document.getElementById('meal-image');
    const mealDescriptionInput = document.getElementById('meal-description');
    const analyzeButton = document.getElementById('analyze-button');
    const resultsSection = document.getElementById('results-section');
    const aiResponseTextDiv = document.getElementById('ai-response-text');
    const confirmForm = document.getElementById('confirm-form');
    const mealTypeSelect = document.getElementById('meal-type');
    const caloriesInput = document.getElementById('calories');
    const proteinInput = document.getElementById('protein');
    const fatInput = document.getElementById('fat');
    const carbohydratesInput = document.getElementById('carbohydrates');
    const errorMessageDiv = document.getElementById('error-message');

    // --- Обработка формы анализа (фото/описание) ---
    analyzeForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        errorMessageDiv.textContent = '';
        analyzeButton.disabled = true;
        analyzeButton.textContent = 'Анализируем...';

        const formData = new FormData();
        if (mealImageInput.files.length > 0) {
            formData.append('file', mealImageInput.files[0]);
        }
        if (mealDescriptionInput.value.trim() !== '') {
            formData.append('description', mealDescriptionInput.value.trim());
        }

        if (!mealImageInput.files.length && mealDescriptionInput.value.trim() === '') {
            errorMessageDiv.textContent = 'Пожалуйста, загрузите фото или введите описание.';
            analyzeButton.disabled = false;
            analyzeButton.textContent = 'Анализировать';
            return;
        }

        try {
            const response = await fetch('/analyze-meal/', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                },
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Ошибка анализа блюда.');
            }

            const result = await response.json();
            aiResponseTextDiv.innerHTML = `<p>${result.ai_response_text}</p>`;

            // Заполняем поля формы подтверждения результатами AI
            caloriesInput.value = Math.round(result.suggested_totals.total_calories);
            proteinInput.value = Math.round(result.suggested_totals.total_protein);
            fatInput.value = Math.round(result.suggested_totals.total_fat);
            carbohydratesInput.value = Math.round(result.suggested_totals.total_carbohydrates);

            resultsSection.style.display = 'block'; // Показываем секцию с результатами

        } catch (error) {
            errorMessageDiv.textContent = error.message;
            resultsSection.style.display = 'none';
        } finally {
            analyzeButton.disabled = false;
            analyzeButton.textContent = 'Анализировать';
        }
    });

    // --- Обработка формы подтверждения и добавления приема пищи ---
    confirmForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        errorMessageDiv.textContent = '';
        const confirmButton = document.getElementById('confirm-button');
        confirmButton.disabled = true;
        confirmButton.textContent = 'Добавляем...';

        const mealData = {
            meal_type: mealTypeSelect.value,
            total_calories: parseFloat(caloriesInput.value),
            total_protein: parseFloat(proteinInput.value),
            total_fat: parseFloat(fatInput.value),
            total_carbohydrates: parseFloat(carbohydratesInput.value),
        };

        try {
            const response = await fetch('/meals/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(mealData)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Ошибка добавления приема пищи.');
            }

            // Успешно добавлено, перенаправляем на дашборд
            window.location.href = '/dashboard';

        } catch (error) {
            errorMessageDiv.textContent = error.message;
        } finally {
            confirmButton.disabled = false;
            confirmButton.textContent = 'Добавить прием пищи';
        }
    });
});
