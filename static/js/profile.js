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

    // Элементы для выбора даты
    const daySelect = document.getElementById('date_of_birth_day');
    const monthSelect = document.getElementById('date_of_birth_month');
    const yearSelect = document.getElementById('date_of_birth_year');

    let debounceTimer;

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

    // --- Функции для выбора даты ---
    function populateDatePickers() {
        const currentYear = new Date().getFullYear();
        const startYear = currentYear - 100;

        // Годы
        for (let i = currentYear; i >= startYear; i--) {
            yearSelect.add(new Option(i, i));
        }

        // Месяцы
        const monthNames = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"];
        monthNames.forEach((name, index) => {
            monthSelect.add(new Option(name, index + 1));
        });

        // Дни (изначально)
        updateDaysInMonth();
    }

    function updateDaysInMonth() {
        const selectedYear = parseInt(yearSelect.value, 10);
        const selectedMonth = parseInt(monthSelect.value, 10);
        const currentDay = daySelect.value;

        if (!selectedYear || !selectedMonth) {
            daySelect.innerHTML = '<option value="">День</option>';
            return;
        }

        const daysInMonth = new Date(selectedYear, selectedMonth, 0).getDate();
        daySelect.innerHTML = '<option value="">День</option>'; // Сброс

        for (let i = 1; i <= daysInMonth; i++) {
            daySelect.add(new Option(i, i));
        }

        if (currentDay && currentDay <= daysInMonth) {
            daySelect.value = currentDay;
        }
    }

    function getAssembledDate() {
        const day = daySelect.value;
        const month = monthSelect.value;
        const year = yearSelect.value;
        if (day && month && year) {
            return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        }
        return null;
    }


    // --- Функция пересчета и обновления UI ---
    const recalculateTargets = () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {
            const bodyFatValue = parseFloat(document.getElementById('body_fat_percentage').value);
            const dateOfBirth = getAssembledDate();

            const requestBody = {
                date_of_birth: dateOfBirth,
                gender: document.getElementById('gender').value,
                height_cm: parseInt(document.getElementById('height_cm').value, 10),
                weight_kg: parseFloat(document.getElementById('weight_kg').value),
                body_fat_percentage: !isNaN(bodyFatValue) && bodyFatValue > 0 ? bodyFatValue : null,
                activity_level: document.getElementById('activity_level').value,
                goal: goalSelect.value,
                goal_intensity: parseFloat(intensitySlider.value)
            };

            if (!requestBody.date_of_birth || !requestBody.gender || !requestBody.height_cm || !requestBody.weight_kg || !requestBody.activity_level || !requestBody.goal) {
                targetsDisplay.style.display = 'none';
                return;
            }

            try {
                const response = await fetch('/users/me/calculate-targets', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                    body: JSON.stringify(requestBody)
                });
                const targets = await response.json();
                if (!response.ok) {
                    console.error('Server Error:', targets);
                    targetsDisplay.style.display = 'none';
                } else {
                    targetsDisplay.style.display = 'block';
                    const maxValues = { calories: 4000, protein: 300, fat: 200, carbs: 500 };
                    updateRing('profile-calories-ring', targets.target_calories, maxValues.calories);
                    updateRing('profile-protein-ring', targets.target_protein, maxValues.protein);
                    updateRing('profile-fat-ring', targets.target_fat, maxValues.fat);
                    updateRing('profile-carbs-ring', targets.target_carbohydrates, maxValues.carbs);
                }
            } catch (error) {
                console.error('Fetch Error:', error);
                targetsDisplay.style.display = 'none';
            }
        }, 250);
    };

    // --- Инициализация страницы ---
    populateDatePickers();

    try {
        const response = await fetch('/users/me', { headers: { 'Authorization': `Bearer ${token}` } });
        if (!response.ok) throw new Error('Could not fetch user data.');
        const user = await response.json();

        if (user.date_of_birth) {
            const [year, month, day] = user.date_of_birth.split('-').map(Number);
            yearSelect.value = year;
            monthSelect.value = month;
            updateDaysInMonth(); // Важно обновить дни до установки значения
            daySelect.value = day;
        }

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

        updateGoalIntensityUI();
        recalculateTargets();

    } catch (error) {
        errorMessage.textContent = `Ошибка загрузки данных: ${error.message}`;
        targetsDisplay.style.display = 'none';
    }

    // --- Слушатели событий ---
    function updateGoalIntensityUI() {
        intensityGroup.style.display = (goalSelect.value === 'fat_loss' || goalSelect.value === 'mass_gain') ? 'block' : 'none';
    }

    form.addEventListener('input', (event) => {
        if (event.target.id.startsWith('date_of_birth')) {
            updateDaysInMonth();
        }
        updateGoalIntensityUI();
        recalculateTargets();
    });

    intensitySlider.addEventListener('input', () => {
        intensityValue.textContent = parseFloat(intensitySlider.value).toFixed(1);
    });

    // --- Отправка формы ---
    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        errorMessage.textContent = '';
        successMessage.textContent = '';

        const dateOfBirth = getAssembledDate();
        if (!dateOfBirth) {
            errorMessage.textContent = 'Пожалуйста, выберите полную дату рождения.';
            return;
        }

        const userUpdateData = {
            date_of_birth: dateOfBirth,
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