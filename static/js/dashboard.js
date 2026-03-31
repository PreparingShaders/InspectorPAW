document.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('accessToken');
    if (!token) {
        window.location.href = '/'; // Если нет токена, редирект на логин
        return;
    }

    // --- Функция для создания одного кольца ---
    function createRingChart(canvasId, consumed, target, color, neonColor) {
        const ctx = document.getElementById(canvasId).getContext('2d');
        const percentage = target > 0 ? (consumed / target) * 100 : 0;
        const data = {
            datasets: [{
                data: [consumed, Math.max(0, target - consumed)], // Потреблено и остаток
                backgroundColor: [color, '#333'], // Цвет для потребленной части и фона
                borderWidth: 0,
                borderRadius: 20,
            }]
        };

        const options = {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '80%', // Толщина кольца
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false }
            },
            animation: {
                animateRotate: true,
                duration: 1500
            },
            // Добавляем эффект свечения через drop-shadow
            onHover: (event, chartElement) => {
                event.native.target.style.cursor = chartElement[0] ? 'pointer' : 'default';
            },
            // Это кастомный плагин для добавления свечения
            plugins: [{
                id: 'neonGlow',
                afterDraw: (chart) => {
                    const { ctx, chartArea } = chart;
                    if (chartArea.width <= 0 || chartArea.height <= 0) return;

                    ctx.save();
                    ctx.shadowColor = neonColor;
                    ctx.shadowBlur = 15;
                    ctx.strokeStyle = color;
                    ctx.lineWidth = 2; // Тонкая линия для свечения
                    ctx.stroke(chart.getDatasetMeta(0).data[0].getProps(['x', 'y'], true).path);
                    ctx.restore();
                }
            }]
        };

        return new Chart(ctx, {
            type: 'doughnut',
            data: data,
            options: options
        });
    }

    // --- Основная функция для загрузки данных и отрисовки ---
    async function initializeDashboard() {
        try {
            const response = await fetch('/users/me/stats/weekly-summary', {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!response.ok) {
                throw new Error('Failed to fetch dashboard data');
            }

            const data = await response.json();
            const todayStats = data.daily_breakdown.find(d => d.date === new Date().toISOString().split('T')[0]);
            const targets = data.period_summary;

            const consumed = {
                calories: todayStats ? todayStats.consumed_calories : 0,
                protein: todayStats ? todayStats.consumed_protein : 0,
                carbs: todayStats ? todayStats.consumed_carbohydrates : 0,
                fat: todayStats ? todayStats.consumed_fat : 0,
            };

            // Обновляем текстовые KPI
            document.getElementById('consumed-calories').textContent = Math.round(consumed.calories);
            document.getElementById('target-calories').textContent = Math.round(targets.target_calories);
            document.getElementById('remaining-calories').textContent = Math.round(Math.max(0, targets.target_calories - consumed.calories));

            // Создаем кольца
            createRingChart('calories-ring', consumed.calories, targets.target_calories, '#FFD700', '#FFD700'); // Оранжево-желтый
            createRingChart('protein-ring', consumed.protein, targets.target_protein, '#9400D3', '#9400D3');     // Фиолетовый
            createRingChart('carbs-ring', consumed.carbs, targets.target_carbohydrates, '#00FF00', '#00FF00'); // Зеленый
            createRingChart('fat-ring', consumed.fat, targets.target_fat, '#00BFFF', '#00BFFF');         // Голубой

        } catch (error) {
            console.error("Error initializing dashboard:", error);
            // Можно добавить отображение ошибки на UI
        }
    }

    initializeDashboard();
});
