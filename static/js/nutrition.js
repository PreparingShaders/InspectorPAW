document.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('accessToken');
    if (!token) { window.location.href = '/'; return; }

    const mealImageInput = document.getElementById('meal-image');
    const mealDescriptionInput = document.getElementById('meal-description');
    const analyzeButton = document.getElementById('analyze-button');
    const uploadButtonLabel = document.querySelector('.upload-button-label');
    const mealLogsContainer = document.getElementById('meal-logs-container');
    const aiCoachTitle = document.getElementById('ai-coach-title');
    const aiCoachAdvice = document.getElementById('ai-coach-advice');
    const errorMessageDiv = document.getElementById('error-message');
    const confirmForm = document.getElementById('confirm-form');
    const analyzeForm = document.getElementById('analyze-form');
    const cancelAnalysisBtn = document.getElementById('cancel-analysis-btn');

    let currentFoodName = '';

    const steps = { 1: document.getElementById('step-1'), 2: document.getElementById('step-2'), 3: document.getElementById('step-3') };

    function goToStep(stepNumber) {
        Object.values(steps).forEach(step => { if (step) step.classList.remove('active'); });
        if (steps[stepNumber]) steps[stepNumber].classList.add('active');
    }

    function resetWizard() {
        analyzeForm.reset(); confirmForm.reset();
        uploadButtonLabel.classList.remove('has-image');
        uploadButtonLabel.textContent = 'Добавить фото';
        analyzeButton.disabled = true;
        goToStep(1);
    }

    // --- Анализ и сохранение ---
    analyzeForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        goToStep(2);
        const formData = new FormData();
        if (mealImageInput.files[0]) formData.append('file', mealImageInput.files[0]);
        if (mealDescriptionInput.value.trim()) formData.append('description', mealDescriptionInput.value.trim());

        try {
            const res = await fetch('/analyze-meal/', { method: 'POST', headers: { 'Authorization': `Bearer ${token}` }, body: formData });
            const result = await res.json();
            aiCoachTitle.textContent = `Совет от AI (${result.coach_model_used || 'Vision'})`;
            aiCoachAdvice.textContent = result.ai_coach_advice || 'Приятного аппетита!';
            currentFoodName = result.ai_response_text || 'Прием пищи';

            const fields = { 'calories': result.suggested_totals.total_calories, 'protein': result.suggested_totals.total_protein, 'fat': result.suggested_totals.total_fat, 'carbohydrates': result.suggested_totals.total_carbohydrates };
            for (const [id, val] of Object.entries(fields)) {
                const el = document.getElementById(id);
                if (el) el.value = Math.round(val || 0);
            }
            goToStep(3);
        } catch (err) { errorMessageDiv.textContent = "Ошибка анализа"; setTimeout(() => goToStep(1), 2000); }
    });

    confirmForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const mealData = {
            meal_type: document.getElementById('meal-type').value,
            food_name: currentFoodName,
            total_calories: parseFloat(document.getElementById('calories').value),
            total_protein: parseFloat(document.getElementById('protein').value),
            total_fat: parseFloat(document.getElementById('fat').value),
            total_carbohydrates: parseFloat(document.getElementById('carbohydrates').value),
            ai_coach_advice: aiCoachAdvice.textContent,
        };
        await fetch('/meals/', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` }, body: JSON.stringify(mealData) });
        resetWizard();
        location.reload();
    });

    // --- Функции отрисовки ---
    function updateRing(ringId, value, maxValue) {
        const ring = document.getElementById(ringId);
        if (!ring) return;
        const bar = ring.querySelector('.progress-ring-bar');
        const radius = bar.r.baseVal.value;
        const circum = 2 * Math.PI * radius;
        bar.style.strokeDasharray = `${circum} ${circum}`;
        const pct = maxValue > 0 ? Math.min(value / maxValue, 1) : 0;
        bar.style.strokeDashoffset = circum - (pct * circum);
        const valEl = document.getElementById(ringId.replace('-ring', '-value'));
        if (valEl) valEl.textContent = Math.round(value);
    }

    async function fetchAndDisplayAverageStats() {
        const res = await fetch('/users/me/average-stats', { headers: { 'Authorization': `Bearer ${token}` } });
        if (res.ok) {
            const s = await res.json();
            updateRing('avg-calories-ring', s.avg_calories, s.target_calories);
            updateRing('avg-protein-ring', s.avg_protein, s.target_protein);
            updateRing('avg-fat-ring', s.avg_fat, s.target_fat);
            updateRing('avg-carbs-ring', s.avg_carbohydrates, s.target_carbohydrates);
            mealLogsContainer.dataset.targets = JSON.stringify(s);
        }
    }

    async function fetchAndDisplayMealHistory() {
        const res = await fetch('/meals/', { headers: { 'Authorization': `Bearer ${token}` } });
        const meals = await res.json();
        const targets = JSON.parse(mealLogsContainer.dataset.targets || '{}');
        mealLogsContainer.innerHTML = '';

        const trans = { breakfast: 'Завтрак', lunch: 'Обед', dinner: 'Ужин', snack: 'Перекус' };
        meals.forEach(m => {
            const card = document.createElement('div');
            card.className = 'glassmorphism rounded-xl p-4 neon-glow-pantone-gray mb-4';
            card.innerHTML = `
                <div class="text-center mb-2"><h4 class="font-bold">${trans[m.meal_type]}</h4><p class="text-[10px] text-gray-400">${m.food_name}</p></div>
                <div class="flex justify-around">
                    ${createMiniRing(m.id, 'calories', m.total_calories, targets.target_calories, 'amber')}
                    ${createMiniRing(m.id, 'protein', m.total_protein, targets.target_protein, 'protein-white')}
                    ${createMiniRing(m.id, 'fat', m.total_fat, targets.target_fat, 'golden-orange')}
                    ${createMiniRing(m.id, 'carbs', m.total_carbohydrates, targets.target_carbohydrates, 'muted-teal')}
                </div>`;
            mealLogsContainer.appendChild(card);
            ['calories', 'protein', 'fat', 'carbs'].forEach(type => {
                updateRing(`log-${m.id}-${type}-ring`, m[`total_${type}`] || m.total_carbohydrates, targets[`target_${type}`] || targets.target_carbohydrates);
            });
        });
    }

    function createMiniRing(id, type, val, target, color) {
        return `<div class="text-center flex flex-col items-center"><div class="ring-container w-10 h-10 relative">
            <svg id="log-${id}-${type}-ring" class="progress-ring-svg" viewBox="0 0 120 120">
                <circle class="progress-ring-bg" cx="60" cy="60" r="54"/><circle class="progress-ring-bar" cx="60" cy="60" r="54" style="stroke: var(--color-${color});"/>
            </svg>
            <div class="absolute inset-0 flex items-center justify-center"><span id="log-${id}-${type}-value" class="text-[9px] font-bold">${Math.round(val)}</span></div>
        </div></div>`;
    }

    async function fetchScoreGraphData(days) {
        try {
            const res = await fetch(`/users/me/stats/summary-by-period?days=${days}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();
            const container = document.getElementById('score-graph-container');
            container.innerHTML = '';

            // --- ВОТ ТУТ МАГИЯ ---
            // Если сейчас график идет не туда, добавим .reverse()
            // или уберем его, если он там был.
            // Большинство API отдают данные от старых к новым.
            const sortedData = data.daily_breakdown.sort((a, b) => new Date(a.date) - new Date(b.date));
            // Если нужно, чтобы сегодня было СПРАВА, оставляем так.
            // Если нужно, чтобы сегодня было СЛЕВА, добавь в конец .reverse()

            sortedData.forEach(day => {
                const col = document.createElement('div');
                col.className = 'flex-1 h-full relative flex justify-center';

                // Расчет высоты (y_axis_pos): 0 - внизу, 120 - вверху
                const yPos = day.y_axis_pos !== null ? ((120 - day.y_axis_pos) / 120) * 100 : 50;

                const circle = document.createElement('div');
                circle.className = 'absolute w-4 h-4 rounded-full flex items-center justify-center text-[8px] font-bold text-white score-circle';
                circle.style.top = `${yPos}%`;
                circle.style.backgroundColor = day.status_color || '#F0F0F0';
                circle.style.boxShadow = `0 0 8px ${day.status_color}`;
                circle.textContent = day.daily_score || 0;

                col.appendChild(circle);
                container.appendChild(col);
            });
        } catch (e) {
            console.error("Ошибка графика:", e);
        }
    }

    // --- Инициализация ---
    cancelAnalysisBtn.addEventListener('click', resetWizard);
    mealImageInput.addEventListener('change', () => { if(mealImageInput.files[0]) { uploadButtonLabel.textContent = 'Фото добавлено!'; analyzeButton.disabled = false; } });

    await fetchAndDisplayAverageStats();
    await fetchAndDisplayMealHistory();
    await fetchScoreGraphData(30);
    goToStep(1);
});