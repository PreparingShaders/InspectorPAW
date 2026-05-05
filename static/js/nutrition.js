document.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('accessToken');
    if (!token) { window.location.href = '/'; return; }

    // --- Элементы UI ---
    const mealImageInput = document.getElementById('meal-image');
    const mealDescriptionInput = document.getElementById('meal-description');
    const sendToAiBtn = document.getElementById('send-to-ai-btn');
    const initialView = document.getElementById('initial-view');
    const imageAddedView = document.getElementById('image-added-view');

    const mealLogsContainer = document.getElementById('meal-logs-container');
    const aiCoachTitle = document.getElementById('ai-coach-title');
    const aiCoachAdvice = document.getElementById('ai-coach-advice');
    const errorMessageDiv = document.getElementById('error-message');
    const confirmForm = document.getElementById('confirm-form');
    const cancelAnalysisBtn = document.getElementById('cancel-analysis-btn');

    let currentFoodName = '';
    let tooltipTimeout;
    const scoreTooltip = document.getElementById('score-tooltip');

    const steps = {
        1: document.getElementById('step-1'),
        2: document.getElementById('step-2'),
        3: document.getElementById('step-3')
    };

    // --- Управление состоянием UI ---
    function goToStep(stepNumber) {
        Object.values(steps).forEach(step => {
            if (step) {
                step.classList.remove('active');
                step.classList.add('hidden');
            }
        });
        if (steps[stepNumber]) {
            steps[stepNumber].classList.remove('hidden');
            steps[stepNumber].classList.add('active');
        }
    }

    function showInitialView() {
        initialView.classList.remove('hidden');
        imageAddedView.classList.add('hidden');
    }

    function showImageAddedView() {
        initialView.classList.add('hidden');
        imageAddedView.classList.remove('hidden');
    }

    function resetWizard() {
        mealImageInput.value = '';
        mealDescriptionInput.value = '';
        confirmForm.reset();
        showInitialView();
        goToStep(1);
    }

    // --- Логика анализа ---
    mealImageInput.addEventListener('change', () => {
        if (!mealImageInput.files || mealImageInput.files.length === 0) return;
        showImageAddedView();
    });

    sendToAiBtn.addEventListener('click', async () => {
        if (!mealImageInput.files || mealImageInput.files.length === 0) {
            alert('Сначала выберите фото.');
            return;
        }

        goToStep(2);

        const formData = new FormData();
        formData.append('file', mealImageInput.files[0]);
        if (mealDescriptionInput.value.trim()) {
            formData.append('description', mealDescriptionInput.value.trim());
        }

        const aiModel = localStorage.getItem('aiHubCurrentModel');
        if (aiModel) formData.append('ai_model', aiModel);

        try {
            const res = await fetch('/analyze-meal/', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData
            });

            if (!res.ok) {
                const errorData = await res.json();
                throw new Error(errorData.detail || 'Ошибка анализа');
            }

            const result = await res.json();

            aiCoachTitle.textContent = `Совет от AI (${result.coach_model_used || 'Vision'})`;
            aiCoachAdvice.textContent = result.ai_coach_advice || 'Приятного аппетита!';
            currentFoodName = result.ai_response_text || 'Прием пищи';

            const fields = {
                'calories': result.suggested_totals.total_calories,
                'protein': result.suggested_totals.total_protein,
                'fat': result.suggested_totals.total_fat,
                'carbohydrates': result.suggested_totals.total_carbohydrates
            };

            for (const [id, val] of Object.entries(fields)) {
                document.getElementById(id).value = Math.round(val || 0);
            }

            goToStep(3);

        } catch (err) {
            console.error(err);
            errorMessageDiv.textContent = err.message;
            setTimeout(() => {
                errorMessageDiv.textContent = "";
                resetWizard();
            }, 3000);
        }
    });

    // --- Сохранение результата ---
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
        try {
            await fetch('/meals/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify(mealData)
            });
            resetWizard();
            location.reload();
        } catch (err) {
            alert("Ошибка при сохранении");
        }
    });

    // --- ОБНОВЛЕНИЕ БЛОКА "АНАЛИЗ ДНЯ" ---
    function updateProgressLabSummary(summary, latestDayData) {
        const defaultContent = document.getElementById('summary-content-default');
        const gamifiedContent = document.getElementById('summary-content-gamified');
        const adviceEl = document.getElementById('summary-advice');
        const titleEl = document.getElementById('summary-title');
        const scoreRingContainer = document.getElementById('score-ring-container');
        const paceBarsContainer = document.getElementById('pace-bars-container');

        if (summary && summary.pace_recommendation) {
            // --- GAMIFIED VIEW ---
            const { text_advice, macros_pace, formatted_time } = summary.pace_recommendation;

            // 1. Update titles
            titleEl.textContent = `Статус на ${formatted_time}`;
            document.getElementById('pace-advice-text').textContent = text_advice;

            // 2. Clear previous rings
            scoreRingContainer.innerHTML = '';
            paceBarsContainer.innerHTML = '';

            // 3. Add Score ring
            if (latestDayData) {
                const scoreRingId = 'summary-score-ring';
                const scoreValueId = 'summary-score-value';
                const score = latestDayData.daily_score || 0;
                const scoreColor = latestDayData.status_color || '#F0F0F0';

                scoreRingContainer.innerHTML = `
                    <div class="text-center flex flex-col items-center justify-center h-full">
                        <div class="ring-container w-12 aspect-square relative" style="box-shadow: 0 0 12px ${scoreColor}; border-radius: 50%;">
                            <svg id="${scoreRingId}" class="progress-ring-svg" viewBox="0 0 120 120">
                                <circle class="progress-ring-bg" cx="60" cy="60" r="54" />
                                <circle class="progress-ring-bar" cx="60" cy="60" r="54" style="stroke: ${scoreColor};" />
                            </svg>
                            <div class="absolute inset-0 flex items-center justify-center">
                                <span id="${scoreValueId}" class="font-bold text-base" style="color: ${scoreColor};">${score}</span>
                            </div>
                        </div>
                        <p class="text-xs font-semibold text-gray-400 mt-1">Score</p>
                    </div>
                `;
                updateRing(scoreRingId, score, 100);
                const scoreValueSpan = document.getElementById(scoreValueId);
                if (scoreValueSpan) scoreValueSpan.style.color = scoreColor;
            }

            // 4. Nutrient rings
            const nutrientConfig = {
                calories: { label: 'Ккал', color: 'var(--color-amber)', neon: 'neon-glow-amber' },
                protein: { label: 'Б', color: 'var(--color-protein-white)', neon: 'neon-glow-protein-white' },
                fat: { label: 'Ж', color: 'var(--color-golden-orange)', neon: 'neon-glow-golden-orange' },
                carbohydrates: { label: 'У', color: 'var(--color-muted-teal)', neon: 'neon-glow-muted-teal' }
            };

            for (const key in nutrientConfig) {
                const pace = macros_pace[key];
                if (!pace) continue;

                const config = nutrientConfig[key];
                const ringId = `pace-${key}-ring`;
                const valueId = `pace-${key}-value`;

                const percentage = pace.expected > 0 ? (pace.actual / pace.expected) * 100 : 0;
                let ringColor = config.color;
                let glowClass = config.neon;

                if (percentage > 100) {
                    if (key === 'protein') {
                        ringColor = '#22c55e';
                        glowClass = 'overflow-glow-green';
                    } else {
                        ringColor = '#e11d48';
                        glowClass = 'overflow-glow-red';
                    }
                }

                const ringWrapper = document.createElement('div');
                ringWrapper.className = 'text-center flex flex-col items-center space-y-1';
                ringWrapper.innerHTML = `
                    <div class="ring-container w-12 aspect-square ${glowClass} relative">
                        <svg id="${ringId}" class="progress-ring-svg" viewBox="0 0 120 120">
                            <circle class="progress-ring-bg" cx="60" cy="60" r="54" />
                            <circle class="progress-ring-bar" cx="60" cy="60" r="54" style="stroke: ${ringColor};" />
                        </svg>
                        <div class="absolute inset-0 flex flex-col items-center justify-center">
                            <span id="${valueId}" class="font-bold text-base" style="color: ${ringColor};">0</span>
                        </div>
                    </div>
                    <p class="text-xs font-semibold text-gray-400 mt-1">${config.label}</p>
                `;

                paceBarsContainer.appendChild(ringWrapper);
                updateRing(ringId, pace.actual, pace.expected);
                const ringBar = document.querySelector(`#${ringId} .progress-ring-bar`);
                if(ringBar) ringBar.style.stroke = ringColor;
                const valueSpan = document.getElementById(valueId);
                if(valueSpan) {
                    valueSpan.style.color = ringColor;
                    valueSpan.textContent = Math.round(pace.actual);
                }
            }

            // 5. Show/Hide content blocks
            defaultContent.classList.add('hidden');
            gamifiedContent.classList.remove('hidden');

        } else {
            // --- DEFAULT VIEW ---
            titleEl.textContent = 'Анализ дня';
            adviceEl.textContent = (summary && summary.smart_advice) ? summary.smart_advice : 'Нет данных для анализа.';
            defaultContent.classList.remove('hidden');
            gamifiedContent.classList.add('hidden');
        }
    }

    // --- Функции отрисовки (без изменений) ---
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
        try {
            const res = await fetch('/users/me/average-stats', { headers: { 'Authorization': `Bearer ${token}` } });
            if (res.ok) {
                const s = await res.json();
                updateRing('avg-calories-ring', s.avg_calories, s.target_calories);
                updateRing('avg-protein-ring', s.avg_protein, s.target_protein);
                updateRing('avg-fat-ring', s.avg_fat, s.target_fat);
                updateRing('avg-carbs-ring', s.avg_carbohydrates, s.target_carbohydrates);
                mealLogsContainer.dataset.targets = JSON.stringify(s);
            }
        } catch (e) { console.error("Ошибка статистики:", e); }
    }

    async function fetchAndDisplayMealHistory() {
        try {
            const res = await fetch('/meals/', { headers: { 'Authorization': `Bearer ${token}` } });
            const meals = await res.json();
            const targets = JSON.parse(mealLogsContainer.dataset.targets || '{}');
            mealLogsContainer.innerHTML = '';
            const trans = { breakfast: 'Завтрак', lunch: 'Обед', dinner: 'Ужин', snack: 'Перекус' };
            meals.forEach(m => {
                const card = document.createElement('div');
                card.className = 'glassmorphism rounded-xl p-4 neon-glow-pantone-gray mb-4';
                card.innerHTML = `<div class="text-center mb-2"><h4 class="font-bold">${trans[m.meal_type]}</h4><p class="text-[10px] text-gray-400">${m.food_name}</p></div><div class="flex justify-around">${createMiniRing(m.id, 'calories', m.total_calories, targets.target_calories, 'amber')}${createMiniRing(m.id, 'protein', m.total_protein, targets.target_protein, 'protein-white')}${createMiniRing(m.id, 'fat', m.total_fat, targets.target_fat, 'golden-orange')}${createMiniRing(m.id, 'carbs', m.total_carbohydrates, targets.target_carbohydrates, 'muted-teal')}</div>`;
                mealLogsContainer.appendChild(card);
                ['calories', 'protein', 'fat', 'carbs'].forEach(type => {
                    updateRing(`log-${m.id}-${type}-ring`, m[`total_${type === 'carbs' ? 'carbohydrates' : type}`], targets[`target_${type === 'carbs' ? 'carbohydrates' : type}`]);
                });
            });
        } catch (e) { console.error("Ошибка истории:", e); }
    }

    function createMiniRing(id, type, val, target, color) {
        return `<div class="text-center flex flex-col items-center"><div class="ring-container w-10 h-10 relative"><svg id="log-${id}-${type}-ring" class="progress-ring-svg" viewBox="0 0 120 120"><circle class="progress-ring-bg" cx="60" cy="60" r="54"/><circle class="progress-ring-bar" cx="60" cy="60" r="54" style="stroke: var(--color-${color});"/></svg><div class="absolute inset-0 flex items-center justify-center"><span id="log-${id}-${type}-value" class="text-[9px] font-bold">${Math.round(val)}</span></div></div></div>`;
    }

    function showTooltip(element, dayData) {
        if (!scoreTooltip) return;
        clearTimeout(tooltipTimeout);
        const messageContainer = document.getElementById('tooltip-message');
        const tooltips = dayData.status_message;
        messageContainer.innerHTML = (typeof tooltips === 'object' && tooltips !== null) ? Object.values(tooltips).map(msg => `<p>${msg}</p>`).join('') : tooltips || '';
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
        const rect = element.getBoundingClientRect();
        scoreTooltip.classList.remove('opacity-0', 'pointer-events-none');
        scoreTooltip.classList.add('opacity-100');
        scoreTooltip.style.transform = 'scale(1)';
        let top = rect.top + window.scrollY - scoreTooltip.offsetHeight - 15;
        let left = rect.left + window.scrollX + (rect.width / 2) - (scoreTooltip.offsetWidth / 2);
        if (top < window.scrollY + 10) top = rect.bottom + window.scrollY + 15;
        left = Math.max(10, Math.min(left, window.innerWidth - scoreTooltip.offsetWidth - 10));
        scoreTooltip.style.top = `${top}px`;
        scoreTooltip.style.left = `${left}px`;
        tooltipTimeout = setTimeout(hideTooltip, 6000);
    }

    function hideTooltip() {
        if (!scoreTooltip) return;
        scoreTooltip.classList.replace('opacity-100', 'opacity-0');
        scoreTooltip.classList.add('pointer-events-none');
        scoreTooltip.style.transform = 'scale(0.9)';
    }

    async function fetchScoreGraphData(days) {
        try {
            const res = await fetch(`/users/me/stats/summary-by-period?days=${days}`, { headers: { 'Authorization': `Bearer ${token}` } });
            const data = await res.json();

            // --- Расчет и отображение среднего балла ---
            const scores = data.daily_breakdown.map(d => d.daily_score).filter(s => s !== null && s !== undefined);
            const avgLabel = document.getElementById('average-score-label');
            if (scores.length > 0) {
                const averageScore = Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);
                if (avgLabel) {
                    avgLabel.textContent = averageScore;
                    avgLabel.classList.remove('hidden');
                }
            } else {
                if (avgLabel) {
                    avgLabel.classList.add('hidden');
                }
            }
            // --- Конец расчета ---

            // Sort to find the latest day for the summary score
            const sortedForSummary = data.daily_breakdown.length > 0 ? [...data.daily_breakdown].sort((a, b) => new Date(b.date) - new Date(a.date)) : [];
            const latestDay = sortedForSummary.length > 0 ? sortedForSummary[0] : null;

            // Call updateProgressLabSummary with the latest day's data.
            // This is called regardless of whether progress_lab_summary exists to handle UI reset.
            updateProgressLabSummary(data.progress_lab_summary, latestDay);

            const container = document.getElementById('score-graph-container');
            container.innerHTML = '';
            // Sort ascending for graph display
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
                circle.onclick = (e) => { e.stopPropagation(); showTooltip(circle, day); };
                col.appendChild(circle);
                container.appendChild(col);
            });
        } catch (e) { console.error("Ошибка графика:", e); }
    }

    // --- Инициализация ---
    if (cancelAnalysisBtn) cancelAnalysisBtn.addEventListener('click', resetWizard);
    document.addEventListener('click', (e) => { if (scoreTooltip && !scoreTooltip.contains(e.target) && !e.target.closest('.score-circle')) hideTooltip(); });
    const oneMonthBtn = document.getElementById('one-month-btn');
    const threeMonthsBtn = document.getElementById('three-months-btn');
    if (oneMonthBtn && threeMonthsBtn) {
        const updateBtns = (a, i) => {
            a.classList.add('active'); a.classList.remove('text-gray-400');
            i.classList.remove('active'); i.classList.add('text-gray-400');
        };
        oneMonthBtn.onclick = () => { updateBtns(oneMonthBtn, threeMonthsBtn); fetchScoreGraphData(30); };
        threeMonthsBtn.onclick = () => { updateBtns(threeMonthsBtn, oneMonthBtn); fetchScoreGraphData(90); };
    }

    // --- Первоначальная загрузка данных ---
    await fetchAndDisplayAverageStats();
    await fetchAndDisplayMealHistory();
    await fetchScoreGraphData(30);
    resetWizard();
});