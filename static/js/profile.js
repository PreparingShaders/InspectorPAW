document.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('accessToken');
    if (!token) {
        window.location.href = '/';
        return;
    }

    // --- Элементы DOM ---
    const form = document.getElementById('profile-form');
    const errorMessage = document.getElementById('error-message');
    const successMessage = document.getElementById('success-message');
    const goalSelect = document.getElementById('goal');
    const intensityGroup = document.getElementById('goal-intensity-group');
    const intensitySlider = document.getElementById('goal_intensity');
    const intensityValue = document.getElementById('goal-intensity-value');
    const targetsDisplay = document.getElementById('calculated-targets');

    let debounceTimer;

    // --- Функция отображения ---
    function displayTargets(targets) {
        // Если данных нет или они нулевые, показываем инструкцию.
        if (!targets || !targets.target_calories) {
            targetsDisplay.innerHTML = '<p>Заполните все обязательные поля для расчета.</p>';
            return;
        }
        // Иначе, показываем рассчитанные значения.
        targetsDisplay.innerHTML = `
            <p><strong>Ваша норма:</strong></p>
            <span>🔥 ${targets.target_calories} ккал</span>
            <span>🥩 ${targets.target_protein} г</span>
            <span>🥑 ${targets.target_fat} г</span>
            <span>🍞 ${targets.target_carbohydrates} г</span>
        `;
    }

    // --- Функция пересчета ---
    const recalculateTargets = () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {
            const bodyFatValue = parseFloat(document.getElementById('body_fat_percentage').value);
            const requestBody = {
                date_of_birth: document.getElementById('date_of_birth').value,
                gender: document.getElementById('gender').value,
                height_cm: parseInt(document.getElementById('height_cm').value, 10),
                weight_kg: parseFloat(document.getElementById('weight_kg').value),
                body_fat_percentage: !isNaN(bodyFatValue) && bodyFatValue > 0 ? bodyFatValue : null,
                activity_level: document.getElementById('activity_level').value,
                goal: goalSelect.value,
                goal_intensity: parseFloat(intensitySlider.value)
            };

            try {
                const response = await fetch('/users/me/calculate-targets', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify(requestBody)
                });
                const targets = await response.json();
                if (!response.ok) {
                    // Если сервер вернул ошибку, все равно отображаем ее, но в консоль пишем детали
                    console.error('Server Error:', targets);
                    displayTargets(null);
                } else {
                    displayTargets(targets);
                }
            } catch (error) {
                console.error('Fetch Error:', error);
                displayTargets(null);
            }
        }, 250);
    };

    // --- Инициализация страницы ---
    try {
        const response = await fetch('/users/me', { headers: { 'Authorization': `Bearer ${token}` } });
        if (!response.ok) throw new Error('Could not fetch user data.');
        const user = await response.json();

        // 1. Заполняем все поля формы данными с сервера
        if (user.date_of_birth) document.getElementById('date_of_birth').value = user.date_of_birth;
        if (user.gender) document.getElementById('gender').value = user.gender;
        if (user.height_cm) document.getElementById('height_cm').value = user.height_cm;
        if (user.activity_level) document.getElementById('activity_level').value = user.activity_level;
        if (user.goal) document.getElementById('goal').value = user.goal;
        if (user.goal_intensity) {
            intensitySlider.value = user.goal_intensity;
            intensityValue.textContent = parseFloat(user.goal_intensity).toFixed(1);
        }
        if (user.metrics && user.metrics.length > 0) {
            const latestMetric = user.metrics[user.metrics.length - 1];
            if (latestMetric.weight_kg) document.getElementById('weight_kg').value = latestMetric.weight_kg;
            if (latestMetric.body_fat_percentage) document.getElementById('body_fat_percentage').value = latestMetric.body_fat_percentage;
        }

        // 2. **ГЛАВНОЕ ИЗМЕНЕНИЕ:** После заполнения формы, запускаем единый механизм пересчета.
        // Это гарантирует, что начальное отображение и последующие пересчеты работают одинаково.
        recalculateTargets();

    } catch (error) {
        errorMessage.textContent = `Ошибка загрузки данных: ${error.message}`;
        displayTargets(null);
    }

    // --- Слушатели событий ---
    function updateGoalIntensityUI() {
        intensityGroup.style.display = (goalSelect.value === 'fat_loss' || goalSelect.value === 'mass_gain') ? 'block' : 'none';
    }

    form.addEventListener('input', () => {
        updateGoalIntensityUI();
        recalculateTargets();
    });

    intensitySlider.addEventListener('input', () => {
        intensityValue.textContent = parseFloat(intensitySlider.value).toFixed(1);
    });

    // --- Отправка формы ---
    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        // ... (код отправки формы остается без изменений)
        errorMessage.textContent = '';
        successMessage.textContent = '';
        const userUpdateData = {
            date_of_birth: document.getElementById('date_of_birth').value,
            gender: document.getElementById('gender').value,
            height_cm: parseInt(document.getElementById('height_cm').value, 10),
            activity_level: document.getElementById('activity_level').value,
            goal: document.getElementById('goal').value,
            goal_intensity: goalSelect.value !== 'maintenance' ? parseFloat(intensitySlider.value) : 0,
        };
        const bodyFatValue = parseFloat(document.getElementById('body_fat_percentage').value);
        const metricsData = {
            weight_kg: parseFloat(document.getElementById('weight_kg').value),
            body_fat_percentage: !isNaN(bodyFatValue) && bodyFatValue > 0 ? bodyFatValue : null
        };
        try {
            const userUpdateResponse = await fetch('/users/me/', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify(userUpdateData)
            });
            if (!userUpdateResponse.ok) throw new Error('Ошибка обновления профиля');

            const metricsResponse = await fetch('/users/me/metrics', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify(metricsData)
            });
            if (!metricsResponse.ok) throw new Error('Ошибка сохранения метрик');

            successMessage.textContent = 'Профиль успешно сохранен!';
            setTimeout(() => { window.location.href = '/dashboard'; }, 1500);
        } catch (error) {
            errorMessage.textContent = error.message;
        }
    });
});
