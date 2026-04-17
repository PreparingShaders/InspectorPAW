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

    // --- Tooltip Globals ---
    let tooltipTimeout;
    const scoreTooltip = document.getElementById('score-tooltip');

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

    // --- Tooltip Functions (IMPROVED) ---
    function showTooltip(element, dayData) {
        if (!scoreTooltip) return;
        clearTimeout(tooltipTimeout);

        // --- FIX 1: Handle [object Object] ---
        const messageContainer = document.getElementById('tooltip-message');
        const tooltips = dayData.status_message;
        if (typeof tooltips === 'object' && tooltips !== null) {
            // If it's an object, format it
            messageContainer.innerHTML = Object.values(tooltips).map(msg => `<p>${msg}</p>`).join('');
        } else {
            // Otherwise, just show the string
            messageContainer.textContent = tooltips || '';
        }

        document.getElementById('tooltip-date').textContent = new Date(dayData.date).toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' });
        document.getElementById('tooltip-score').textContent = dayData.daily_score;
        document.getElementById('tooltip-calories').textContent = Math.round(dayData.consumed_calories);
        document.getElementById('tooltip-target-calories').textContent = Math.round(dayData.target_calories);
        document.getElementById('tooltip-protein').textContent = Math.round(dayData.consumed_protein);
        document.getElementById('tooltip-target-protein').textContent = Math.round(dayData.target_protein);
        document.getElementById('tooltip-fat').textContent = Math.round(dayData.consumed_fat);
        document.getElementById('tooltip-target-fat').textContent = Math.round(dayData.target_fat);
        document.getElementById('tooltip-carbs').textContent = Math.round(dayData.consumed_carbohydrates);
        document.getElementById('tooltip-target-carbs').textContent = Math.round(dayData.target_carbohydrates);

        // --- FIX 2: Improved Positioning ---
        const rect = element.getBoundingClientRect();
        const scrollX = window.scrollX || window.pageXOffset;
        const scrollY = window.scrollY || window.pageYOffset;

        // Make it visible first to calculate its dimensions
        scoreTooltip.classList.remove('opacity-0', 'pointer-events-none');
        scoreTooltip.classList.add('opacity-100');
        scoreTooltip.style.transform = 'scale(1)';

        let top = rect.top + scrollY - scoreTooltip.offsetHeight - 15;
        let left = rect.left + scrollX + (rect.width / 2) - (scoreTooltip.offsetWidth / 2);

        // Boundary checks
        if (top < scrollY + 10) { // If too close to the top, flip it below
            top = rect.bottom + scrollY + 15;
        }
        if (left < 10) { // If too close to the left edge
            left = 10;
        }
        if (left + scoreTooltip.offsetWidth > window.innerWidth - 10) { // If too close to the right edge
            left = window.innerWidth - scoreTooltip.offsetWidth - 10;
        }

        scoreTooltip.style.top = `${top}px`;
        scoreTooltip.style.left = `${left}px`;

        tooltipTimeout = setTimeout(hideTooltip, 6000); // Increased timeout
    }

    function hideTooltip() {
        if (!scoreTooltip) return;
        scoreTooltip.style.transform = 'scale(0.9)';
        scoreTooltip.classList.remove('opacity-100');
        scoreTooltip.classList.add('opacity-0', 'pointer-events-none');
        if(tooltipTimeout) clearTimeout(tooltipTimeout);
    }

    document.addEventListener('click', (event) => {
        if (scoreTooltip && !scoreTooltip.contains(event.target) && !event.target.closest('.score-circle')) {
            hideTooltip();
        }
    });


    async function fetchScoreGraphData(days) {
        try {
            const res = await fetch(`/users/me/stats/summary-by-period?days=${days}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();
            const container = document.getElementById('score-graph-container');
            container.innerHTML = '';

            const sortedData = data.daily_breakdown.sort((a, b) => new Date(a.date) - new Date(b.date));

            sortedData.forEach(day => {
                const col = document.createElement('div');
                col.className = 'flex-1 h-full relative flex justify-center';

                const yPos = day.y_axis_pos !== null ? ((120 - day.y_axis_pos) / 120) * 100 : 50;

                const circle = document.createElement('div');
                circle.className = 'absolute w-4 h-4 rounded-full flex items-center justify-center text-[8px] font-bold text-white score-circle cursor-pointer';
                circle.style.top = `${yPos}%`;
                circle.style.backgroundColor = day.status_color || '#F0F0F0';
                circle.style.boxShadow = `0 0 8px ${day.status_color}`;
                circle.textContent = day.daily_score || 0;

                circle.dataset.details = JSON.stringify(day);
                circle.addEventListener('click', (event) => {
                    event.stopPropagation();
                    const dayData = JSON.parse(event.currentTarget.dataset.details);
                    const isVisible = scoreTooltip.classList.contains('opacity-100');
                    const isForThisElement = scoreTooltip.dataset.identifier === dayData.date;

                    if (isVisible && isForThisElement) {
                        hideTooltip();
                    } else {
                        scoreTooltip.dataset.identifier = dayData.date;
                        showTooltip(event.currentTarget, dayData);
                    }
                });

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