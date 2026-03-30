document.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('accessToken');
    if (!token) {
        window.location.href = '/';
        return;
    }

    const form = document.getElementById('profile-form');
    const errorMessage = document.getElementById('error-message');
    const successMessage = document.getElementById('success-message');

    const goalSelect = document.getElementById('goal');
    const intensityGroup = document.getElementById('goal-intensity-group');
    const intensitySlider = document.getElementById('goal_intensity');
    const intensityValue = document.getElementById('goal-intensity-value');
    const targetsDisplay = document.getElementById('calculated-targets');

    let debounceTimer;

    // --- Debounced Calculation Function ---
    const recalculateTargets = async () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {
            const requestBody = {
                date_of_birth: document.getElementById('date_of_birth').value,
                gender: document.getElementById('gender').value,
                height_cm: parseInt(document.getElementById('height_cm').value, 10),
                weight_kg: parseFloat(document.getElementById('weight_kg').value),
                goal: goalSelect.value,
                goal_intensity: parseFloat(intensitySlider.value)
            };

            if (!requestBody.date_of_birth || !requestBody.gender || !requestBody.height_cm || !requestBody.weight_kg || !requestBody.goal) {
                targetsDisplay.innerHTML = '<p>Заполните все поля для расчета</p>';
                return;
            }

            try {
                const response = await fetch('/users/me/calculate-targets', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify(requestBody)
                });
                if (!response.ok) throw new Error('Calculation failed.');
                const targets = await response.json();
                displayTargets(targets);
            } catch (error) {
                targetsDisplay.innerHTML = `<p class="error-message">Ошибка расчета</p>`;
            }
        }, 250);
    };

    function displayTargets(targets) {
        if (!targets) {
            targetsDisplay.innerHTML = '';
            return;
        }
        targetsDisplay.innerHTML = `
            <p><strong>Ваша норма:</strong></p>
            <span>🔥 ${targets.target_calories} ккал</span>
            <span>🥩 ${targets.target_protein} г</span>
            <span>🥑 ${targets.target_fat} г</span>
            <span>🍞 ${targets.target_carbohydrates} г</span>
        `;
    }

    try {
        const response = await fetch('/users/me', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!response.ok) throw new Error('Could not fetch user data.');

        const user = await response.json();

        if (user.date_of_birth) document.getElementById('date_of_birth').value = user.date_of_birth;
        if (user.gender) document.getElementById('gender').value = user.gender;
        if (user.height_cm) document.getElementById('height_cm').value = user.height_cm;
        if (user.goal) document.getElementById('goal').value = user.goal;
        if (user.goal_intensity) {
            intensitySlider.value = user.goal_intensity;
            intensityValue.textContent = parseFloat(user.goal_intensity).toFixed(1);
        }

        if (user.metrics && user.metrics.length > 0) {
            const latestWeight = user.metrics[user.metrics.length - 1].weight_kg;
            if (latestWeight) document.getElementById('weight_kg').value = latestWeight;
        }

        displayTargets(user.calculated_targets);
        handleGoalChange();

    } catch (error) {
        errorMessage.textContent = `Ошибка загрузки данных: ${error.message}`;
    }

    function handleGoalChange() {
        if (goalSelect.value === 'fat_loss' || goalSelect.value === 'mass_gain') {
            intensityGroup.style.display = 'block';
        } else {
            intensityGroup.style.display = 'none';
        }
        recalculateTargets();
    }

    form.addEventListener('input', (e) => {
        if (e.target.type !== 'range') {
            handleGoalChange();
        }
    });

    intensitySlider.addEventListener('input', () => {
        intensityValue.textContent = parseFloat(intensitySlider.value).toFixed(1);
        recalculateTargets();
    });

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        errorMessage.textContent = '';
        successMessage.textContent = '';

        const userUpdateData = {
            date_of_birth: document.getElementById('date_of_birth').value,
            gender: document.getElementById('gender').value,
            height_cm: parseInt(document.getElementById('height_cm').value, 10),
            goal: document.getElementById('goal').value,
            goal_intensity: goalSelect.value !== 'maintenance' ? parseFloat(intensitySlider.value) : 0,
        };

        const weightData = {
            weight_kg: parseFloat(document.getElementById('weight_kg').value)
        };

        try {
            const userUpdateResponse = await fetch('/users/me/', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(userUpdateData)
            });

            if (!userUpdateResponse.ok) {
                const errorData = await userUpdateResponse.json();
                throw new Error(`Ошибка обновления профиля: ${errorData.detail}`);
            }

            const weightResponse = await fetch('/users/me/metrics', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(weightData)
            });

            if (!weightResponse.ok) {
                const errorData = await weightResponse.json();
                throw new Error(`Ошибка сохранения веса: ${errorData.detail}`);
            }

            successMessage.textContent = 'Профиль успешно сохранен!';
            setTimeout(() => {
                window.location.href = '/dashboard';
            }, 1500);

        } catch (error) {
            errorMessage.textContent = error.message;
        }
    });
});
