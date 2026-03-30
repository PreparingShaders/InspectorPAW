document.addEventListener('DOMContentLoaded', async function() {
    const token = localStorage.getItem('accessToken');
    const loadingIndicator = document.getElementById('loading-indicator');
    const statsContainer = document.getElementById('stats-container');

    if (!token) {
        window.location.href = '/';
        return;
    }

    try {
        loadingIndicator.style.display = 'block';
        statsContainer.style.display = 'none';

        const response = await fetch('/users/me/stats/weekly-summary', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (response.status === 401) {
            // Токен недействителен или истек
            localStorage.removeItem('accessToken');
            window.location.href = '/';
            return;
        }

        if (!response.ok) {
            throw new Error('Не удалось загрузить статистику.');
        }

        const data = await response.json();
        renderStatistics(data);

    } catch (error) {
        console.error('Ошибка:', error);
        document.getElementById('stats-container').innerHTML = `<p class="error-message">${error.message}</p>`;
    } finally {
        loadingIndicator.style.display = 'none';
        statsContainer.style.display = 'block';
    }
});

function renderStatistics(data) {
    renderDailyBreakdown(data.daily_breakdown);
    renderPeriodSummary(data.period_summary);
}

function renderDailyBreakdown(dailyData) {
    const container = document.getElementById('daily-cards-container');
    container.innerHTML = ''; // Очищаем контейнер

    dailyData.forEach(day => {
        const dayNames = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];
        const date = new Date(day.date);
        const dayName = dayNames[date.getUTCDay()];
        const formattedDate = `${dayName} ${date.getUTCDate().toString().padStart(2, '0')}.${(date.getUTCMonth() + 1).toString().padStart(2, '0')}`;

        const card = document.createElement('div');
        card.className = `daily-card status-${day.status}`;

        let content = `<strong>${formattedDate}:</strong> `;
        if (day.status !== 'no_data') {
            content += `${Math.round(day.consumed_calories)} / ${Math.round(day.target_calories)} ккал`;
        } else {
            content += 'Нет данных';
        }

        card.innerHTML = content;
        container.appendChild(card);
    });
}

function renderPeriodSummary(summary) {
    const container = document.getElementById('summary-grid');
    container.innerHTML = '';

    const items = [
        { label: 'Калории', consumed: summary.avg_calories, target: summary.target_calories, unit: '' },
        { label: 'Белки', consumed: summary.avg_protein, target: summary.target_protein, unit: 'г' },
        { label: 'Жиры', consumed: summary.avg_fat, target: summary.target_fat, unit: 'г' },
        { label: 'Углеводы', consumed: summary.avg_carbohydrates, target: summary.target_carbohydrates, unit: 'г' }
    ];

    items.forEach(item => {
        const gridItem = document.createElement('div');
        gridItem.className = 'summary-item';
        gridItem.innerHTML = `
            <span class="summary-label">${item.label}</span>
            <span class="summary-value">${Math.round(item.consumed)} / ${Math.round(item.target)} ${item.unit}</span>
        `;
        container.appendChild(gridItem);
    });
}

document.getElementById('logout-button').addEventListener('click', () => {
    localStorage.removeItem('accessToken');
    window.location.href = '/';
});
