document.addEventListener('DOMContentLoaded', async () => {
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
            window.location.href = '/'; // Исправлено на /
            // Возвращаем "пустой" Promise, чтобы остановить выполнение цепочки .then()
            return new Promise(() => {});
        }

        return response;
    }

    const token = localStorage.getItem('accessToken');
    if (!token) {
        window.location.href = '/'; // Исправлено на /
        return;
    }

    // --- Элементы DOM ---
    const form = document.getElementById('profile-form');
    const goalSelect = document.getElementById('goal');
    const intensityGroup = document.getElementById('goal-intensity-group');
    const intensitySlider = document.getElementById('goal_intensity');
    const intensityValue = document.getElementById('goal-intensity-value');
    const targetsDisplay = document.getElementById('calculated-targets');
    const logoutButton = document.getElementById('logout-button'); // Добавлено
    const saveProfileButton = form.querySelector('button[type="submit"]'); // Кнопка "Сохранить профиль"
    const originalButtonText = saveProfileButton.textContent;
    const originalButtonClass = saveProfileButton.className;


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
        const currentMonth = new Date().getMonth() + 1; // JavaScript месяцы 0-индексированы
        const currentDay = new Date().getDate(); // Текущий день

        // Годы
        yearSelect.innerHTML = ''; // Очищаем, но не добавляем пустую опцию
        for (let i = currentYear; i >= currentYear - 100; i--) {
            yearSelect.add(new Option(i, i));
        }
        // Устанавливаем текущий год по умолчанию, если не выбран
        if (!yearSelect.value) {
            yearSelect.value = currentYear;
        }

        // Месяцы
        monthSelect.innerHTML = ''; // Очищаем, но не добавляем пустую опцию
        const monthNames = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"];
        monthNames.forEach((name, index) => {
            monthSelect.add(new Option(name, index + 1));
        });
        // Устанавливаем текущий месяц по умолчанию, если не выбран
        if (!monthSelect.value) {
            monthSelect.value = currentMonth;
        }

        // Дни
        updateDaysInMonth(currentDay); // Передаем текущий день для установки по умолчанию
    }

    function updateDaysInMonth(defaultDay = 1) { // Добавляем defaultDay
        const selectedYear = parseInt(yearSelect.value, 10);
        const selectedMonth = parseInt(monthSelect.value, 10);
        const currentSelectedDay = daySelect.value; // Сохраняем текущий выбранный день

        if (!selectedYear || !selectedMonth) {
            daySelect.innerHTML = ''; // Очищаем, если год или месяц не выбраны
            return;
        }

        const daysInMonth = new Date(selectedYear, selectedMonth, 0).getDate();
        daySelect.innerHTML = ''; // Сброс

        for (let i = 1; i <= daysInMonth; i++) {
            daySelect.add(new Option(i, i));
        }

        // Пытаемся установить ранее выбранный день, если он валиден
        if (currentSelectedDay && parseInt(currentSelectedDay, 10) <= daysInMonth) {
            daySelect.value = currentSelectedDay;
        } else {
            // Иначе устанавливаем defaultDay (текущий день при инициализации) или 1
            daySelect.value = defaultDay;
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

    // --- Функция для преобразования значения интенсивности цели ---
    function getDisplayIntensity(sliderValue) {
        const intensityMap = {
            '-3': 'Очень медленно',
            '-2': 'Медленно',
            '-1': 'Чуть медленнее',
            '0': 'Без изменений',
            '1': 'Чуть быстрее',
            '2': 'Быстро',
            '3': 'Очень быстро'
        };
        return intensityMap[sliderValue.toString()] || sliderValue.toString();
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
                const response = await fetchWithAuth('/users/me/calculate-targets', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestBody)
                });
                const targets = await response.json();


                if (!response.ok) {
                    console.error('Server Error:', targets);
                    targetsDisplay.style.display = 'none';
                } else {
                    targetsDisplay.style.display = 'block';
                    const maxValues = { calories: 4000, protein: 300, fat: 200, carbs: 500, fiber: 60 };
                    updateRing('profile-calories-ring', targets.target_calories, maxValues.calories);
                    updateRing('profile-protein-ring', targets.target_protein, maxValues.protein);
                    updateRing('profile-fat-ring', targets.target_fat, maxValues.fat);
                    updateRing('profile-carbs-ring', targets.target_carbohydrates, maxValues.carbs);
                    updateRing('profile-fiber-ring', targets.target_fiber || 25, maxValues.fiber);
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
        const response = await fetchWithAuth('/users/me');
        if (!response.ok) throw new Error('Could not fetch user data.');
        const user = await response.json();

        if (user.date_of_birth) {
            const [year, month, day] = user.date_of_birth.split('-').map(Number);
            yearSelect.value = year;
            monthSelect.value = month;
            updateDaysInMonth(day); // Передаем день из данных пользователя
            daySelect.value = day;
        } else {
            // Если даты рождения нет, устанавливаем текущий день по умолчанию
            const today = new Date();
            daySelect.value = today.getDate();
            monthSelect.value = today.getMonth() + 1;
            yearSelect.value = today.getFullYear();
            updateDaysInMonth(today.getDate());
        }

        if (user.gender) {
            document.getElementById('gender').value = user.gender;
            const activeBtn = document.getElementById(`gender-${user.gender}`);
            if (activeBtn) {
                document.querySelectorAll('.gender-btn').forEach(b => { b.classList.remove('text-white'); b.classList.add('text-gray-400'); });
                activeBtn.classList.remove('text-gray-400');
                activeBtn.classList.add('text-white');
            }
        }
        if (user.height_cm) document.getElementById('height_cm').value = user.height_cm;
        if (user.activity_level) document.getElementById('activity_level').value = user.activity_level;
        if (user.goal) document.getElementById('goal').value = user.goal;
        if (user.goal_intensity !== undefined && user.goal_intensity !== null) { // Проверяем на undefined/null
            intensitySlider.value = user.goal_intensity;
            intensityValue.textContent = getDisplayIntensity(parseFloat(user.goal_intensity)); // Используем новую функцию
        }
        if (user.metrics && user.metrics.length > 0) {
            const latestMetric = user.metrics[user.metrics.length - 1];
            if (latestMetric.weight_kg) document.getElementById('weight_kg').value = latestMetric.weight_kg;
            if (latestMetric.body_fat_percentage) document.getElementById('body_fat_percentage').value = latestMetric.body_fat_percentage;
        }

        updateGoalIntensityUI();
        recalculateTargets();

    } catch (error) {
        // errorMessage.textContent = `Ошибка загрузки данных: ${error.message}`; // УДАЛЕНО
        targetsDisplay.style.display = 'none';
    }

    // --- Слушатели событий ---
    function updateGoalIntensityUI() {
        const isGoalRelevant = (goalSelect.value === 'fat_loss' || goalSelect.value === 'mass_gain');
        intensityGroup.style.display = isGoalRelevant ? 'block' : 'none';
    }

    form.addEventListener('input', (event) => {
        if (event.target.id.startsWith('date_of_birth')) {
            updateDaysInMonth();
        }
        updateGoalIntensityUI();
        recalculateTargets();
    });

    intensitySlider.addEventListener('input', () => {
        intensityValue.textContent = getDisplayIntensity(parseFloat(intensitySlider.value)); // Используем новую функцию
        recalculateTargets();
    });

    // --- Отправка формы ---
    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        // errorMessage.textContent = ''; // УДАЛЕНО
        // successMessage.textContent = ''; // УДАЛЕНО

        const dateOfBirth = getAssembledDate();
        if (!dateOfBirth) {
            // errorMessage.textContent = 'Пожалуйста, выберите полную дату рождения.'; // УДАЛЕНО
            saveProfileButton.textContent = 'Пожалуйста, выберите полную дату рождения.';
            saveProfileButton.className = originalButtonClass.replace('neon-glow-pantone-gray', 'neon-glow-error');
            setTimeout(() => {
                saveProfileButton.textContent = originalButtonText;
                saveProfileButton.className = originalButtonClass;
            }, 2000);
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
            const userUpdateResponse = await fetchWithAuth('/users/me/', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(userUpdateData)
            });
            if (!userUpdateResponse.ok) {
                const errorData = await userUpdateResponse.json();
                throw new Error(`Профиль: ${JSON.stringify(errorData.detail)}`);
            }

            const metricsResponse = await fetchWithAuth('/users/me/metrics', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(metricsData)
            });
            if (!metricsResponse.ok) {
                const errorData = await metricsResponse.json();
                throw new Error(`Метрики: ${JSON.stringify(errorData.detail)}`);
            }

            // successMessage.textContent = 'Профиль успешно сохранен!'; // УДАЛЕНО
            saveProfileButton.textContent = 'Профиль успешно сохранен!';
            saveProfileButton.className = originalButtonClass.replace('neon-glow-pantone-gray', 'neon-glow-success');
            setTimeout(() => {
                saveProfileButton.textContent = originalButtonText;
                saveProfileButton.className = originalButtonClass;
                window.location.href = '/nutrition';
            }, 1500);

        } catch (error) {
            // errorMessage.textContent = error.message; // УДАЛЕНО
            saveProfileButton.textContent = `Ошибка: ${error.message}`;
            saveProfileButton.className = originalButtonClass.replace('neon-glow-pantone-gray', 'neon-glow-error');
            setTimeout(() => {
                saveProfileButton.textContent = originalButtonText;
                saveProfileButton.className = originalButtonClass;
            }, 3000);
        }
    });

// --- Обработчик кнопки "Выйти" ---
    if (logoutButton) {
        logoutButton.addEventListener('click', () => {
            localStorage.removeItem('accessToken');
            window.location.href = '/';
        });
    }

    // --- Переключение пола ---
    document.querySelectorAll('.gender-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.gender-btn').forEach(b => {
                b.classList.remove('text-white');
                b.classList.add('text-gray-400');
            });
            btn.classList.remove('text-gray-400');
            btn.classList.add('text-white');
            document.getElementById('gender').value = btn.dataset.value;
        });
    });
});