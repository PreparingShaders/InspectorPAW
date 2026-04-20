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
                step.classList.add('hidden'); // Убедимся, что все неактивные шаги скрыты
            }
        });
        if (steps[stepNumber]) {
            steps[stepNumber].classList.remove('hidden'); // Показываем активный шаг
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

    // --- НОВАЯ ЛОГИКА: ДВУХЭТАПНЫЙ АНАЛИЗ ---

    // 1. При выборе фото, меняем UI
    mealImageInput.addEventListener('change', () => {
        if (!mealImageInput.files || mealImageInput.files.length === 0) {
            return;
        }
        showImageAddedView();
    });

    // 2. При клике на "Отправить в AI", запускаем анализ
    sendToAiBtn.addEventListener('click', async () => {
        if (!mealImageInput.files || mealImageInput.files.length === 0) {
            alert('Сначала выберите фото.');
            return;
        }

        goToStep(2); // Показываем лоадер

        const formData = new FormData();
        formData.append('file', mealImageInput.files[0]);
        if (mealDescriptionInput.value.trim()) {
            formData.append('description', mealDescriptionInput.value.trim());
        }

        const aiModel = localStorage.getItem('aiHubCurrentModel');
        if (aiModel) {
            formData.append('ai_model', aiModel);
        }

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

            // Заполняем данными Шаг 3
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
                const el = document.getElementById(id);
                if (el) el.value = Math.round(val || 0);
            }

            goToStep(3); // Переходим на шаг подтверждения

        } catch (err) {
            console.error(err);
            errorMessageDiv.textContent = err.message;
            setTimeout(() => {
                errorMessageDiv.textContent = "";
                resetWizard();
            }, 3000);
        }
    });

    // --- Сохранение результата (без изменений) ---
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

    // --- Функции отрисовки (без изменений) ---
    function updateProgressLabSummary(summary) {
        if (!summary) return;
        const titleEl = document.getElementById('summary-title');
        const adviceEl = document.getElementById('summary-advice');
        if (titleEl) titleEl.textContent = summary.status_title || 'Анализ дня';
        if (adviceEl) adviceEl.textContent = summary.smart_advice || 'Нет данных для анализа.';
    }

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
            if (data.progress_lab_summary) {
                updateProgressLabSummary(data.progress_lab_summary);
            }
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
    resetWizard(); // Убедимся, что при загрузке страницы всегда начальный вид
});