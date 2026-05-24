document.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('accessToken');
    if (!token) {
        window.location.href = '/';
        return;
    }

    // Глобальный объект для хранения экземпляров графиков
    window.ringCharts = {};

    // --- Функция для создания или обновления одного кольца ---
    function createOrUpdateRingChart(canvasId, consumed, target, color) {
        const ctx = document.getElementById(canvasId).getContext('2d');

        const data = {
            datasets: [{
                data: [consumed, Math.max(0, target - consumed)],
                backgroundColor: [color, '#333'], // Используем переданный цвет
                borderWidth: 0,
                borderRadius: 20,
            }]
        };

        const options = {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '80%',
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false }
            },
            animation: {
                duration: 0 // Отключаем анимацию при обновлении для плавности
            }
        };

        // Если график уже существует, обновляем его данные. Иначе, создаем новый.
        if (window.ringCharts[canvasId]) {
            window.ringCharts[canvasId].data = data;
            window.ringCharts[canvasId].update();
        } else {
            window.ringCharts[canvasId] = new Chart(ctx, {
                type: 'doughnut',
                data: data,
                options: options
            });
        }
    }

    // --- Основная функция для загрузки данных и отрисовки ---
    async function initializeDashboard() {
        try {
            const response = await fetch('/users/me/stats/weekly-summary', {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!response.ok) throw new Error('Failed to fetch dashboard data');

            const data = await response.json();
            console.log('Fetched data:', data); // Логирование

            const todayStats = data.daily_breakdown[0];
            const targets = data.period_summary;

            console.log('Today Stats:', todayStats); // Логирование
            console.log('Targets:', targets); // Логирование

            const consumed = {
                calories: todayStats ? todayStats.consumed_calories : 0,
                protein: todayStats ? todayStats.consumed_protein : 0,
                carbs: todayStats ? todayStats.consumed_carbohydrates : 0,
                fat: todayStats ? todayStats.consumed_fat : 0,
            };

            console.log('Consumed values:', consumed); // Логирование

            // Обновляем текстовые KPI в шапке
            document.getElementById('consumed-calories').textContent = Math.round(consumed.calories);
            document.getElementById('target-calories').textContent = Math.round(targets.target_calories);
            document.getElementById('remaining-calories').textContent = Math.round(Math.max(0, targets.target_calories - consumed.calories));

            // Обновляем значения в центре колец
            document.getElementById('calories-value').textContent = Math.round(consumed.calories);
            document.getElementById('protein-value').textContent = Math.round(consumed.protein);
            document.getElementById('carbs-value').textContent = Math.round(consumed.carbs);
            document.getElementById('fat-value').textContent = Math.round(consumed.fat);

            // **КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ЦВЕТА:**
            // Считываем реальные значения цветов из CSS переменных
            const style = getComputedStyle(document.body);
            const caloriesColor = style.getPropertyValue('--calories-color').trim();
            const proteinColor = style.getPropertyValue('--protein-color').trim();
            const carbsColor = style.getPropertyValue('--carbs-color').trim();
            const fatColor = style.getPropertyValue('--fat-color').trim();

            // Создаем или обновляем кольца с реальными цветами
            createOrUpdateRingChart('calories-ring', consumed.calories, targets.target_calories, caloriesColor);
            createOrUpdateRingChart('protein-ring', consumed.protein, targets.target_protein, proteinColor);
            createOrUpdateRingChart('carbs-ring', consumed.carbs, targets.target_carbohydrates, carbsColor);
            createOrUpdateRingChart('fat-ring', consumed.fat, targets.target_fat, fatColor);

        } catch (error) {
            console.error("Error initializing dashboard:", error);
        }
    }

    initializeDashboard();
});
