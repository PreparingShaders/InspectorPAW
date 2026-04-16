document.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('accessToken');
    if (!token) {
        window.location.href = '/';
        return;
    }

    // --- Элементы DOM ---
    const analyzeForm = document.getElementById('analyze-form');
    const mealImageInput = document.getElementById('meal-image');
    const mealDescriptionInput = document.getElementById('meal-description');
    const analyzeButton = document.getElementById('analyze-button');
    const resultsSection = document.getElementById('results-section');
    const aiResponseTextDiv = document.getElementById('ai-response-text');
    const confirmForm = document.getElementById('confirm-form');
    const errorMessageDiv = document.getElementById('error-message');
    const uploadButtonLabel = document.querySelector('.upload-button-label');
    const mealLogsContainer = document.getElementById('meal-logs-container');
    const aiCoachSection = document.getElementById('ai-coach-section');
    const aiCoachTitle = document.getElementById('ai-coach-title');
    const aiCoachAdvice = document.getElementById('ai-coach-advice');
    const nutritionModelInfo = document.getElementById('nutrition-model-info');

    let currentFoodName = '';

    // Mapping for neon glow classes (copied from index.html)
    const NEON_GLOW_CLASSES = {
        '#FFD700': 'neon-glow-emerald', // Золотой
        '#F0F0F0': 'neon-glow-white',   // Белый
        '#f59e0b': 'neon-glow-amber-score',
        '#e11d48': 'neon-glow-rose'
    };

    function getNeonGlowClass(hexColor) {
        return NEON_GLOW_CLASSES[hexColor] || ''; // Return empty string if no match
    }

    let tooltipTimeout;
    const scoreTooltip = document.getElementById('score-tooltip'); // Assuming tooltip HTML is added to nutrition.html

    function showTooltip(element, dayData) {
        clearTimeout(tooltipTimeout);

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

        const messageContainer = document.getElementById('tooltip-message');
        const tooltips = dayData.status_message;

        if (typeof tooltips === 'object' && tooltips !== null) {
            messageContainer.innerHTML = `
                <p>${tooltips.calories}</p>
                <p>${tooltips.protein}</p>
                <p>${tooltips.fat}</p>
                <p>${tooltips.carbohydrates}</p>
            `;
        } else {
            messageContainer.textContent = tooltips || '';
        }

        const rect = element.getBoundingClientRect();
        const scrollX = window.scrollX || window.pageXOffset;
        const scrollY = window.scrollY || window.pageYOffset;

        scoreTooltip.classList.remove('opacity-0', 'pointer-events-none');
        scoreTooltip.classList.add('opacity-100');

        let top = rect.top + scrollY - scoreTooltip.offsetHeight - 15;
        let left = rect.left + scrollX + (rect.width / 2) - (scoreTooltip.offsetWidth / 2);

        if (top < scrollY + 10) {
            top = rect.bottom + scrollY + 15;
        }
        if (left < 10) left = 10;
        if (left + scoreTooltip.offsetWidth > window.innerWidth - 10) {
            left = window.innerWidth - scoreTooltip.offsetWidth - 10;
        }

        scoreTooltip.style.top = `${top}px`;
        scoreTooltip.style.left = `${left}px`;
        scoreTooltip.style.transform = 'scale(0.9)';

        tooltipTimeout = setTimeout(hideTooltip, 6000);
    }

    function hideTooltip() {
        if (scoreTooltip) { // Check if scoreTooltip exists
            scoreTooltip.style.transform = 'scale(0.7)';
            scoreTooltip.classList.remove('opacity-100');
            scoreTooltip.classList.add('opacity-0', 'pointer-events-none');
            if(tooltipTimeout) clearTimeout(tooltipTimeout);
            scoreTooltip.dataset.identifier = '';
        }
    }

    document.addEventListener('click', (event) => {
        if (scoreTooltip && !scoreTooltip.contains(event.target) && !event.target.closest('.score-circle')) {
            hideTooltip();
        }
    });

    function renderScoreGraph(dailyBreakdown) {
        const graphContainer = document.getElementById('score-graph-container');
        if (!graphContainer) return;
        graphContainer.innerHTML = ''; // Clear previous content

        dailyBreakdown.sort((a, b) => new Date(a.date) - new Date(b.date));

        // --- Расчет и отображение среднего балла ---
        const scores = dailyBreakdown.map(d => d.daily_score).filter(s => s !== null);
        const avgLabel = document.getElementById('average-score-label');
        if (scores.length > 0) {
            const averageScore = Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);
            if (avgLabel) {
                avgLabel.textContent = averageScore;
                avgLabel.classList.remove('hidden');
            }
        } else {
            if (avgLabel) avgLabel.classList.add('hidden');
        }
        // --- Конец расчета ---

        dailyBreakdown.forEach((dayData) => {
            const score = dayData.daily_score !== null ? dayData.daily_score : 0;
            const color = dayData.status_color || '#F0F0F0';
            const yPos = dayData.y_axis_pos !== null ? dayData.y_axis_pos : 0;

            const topPosition = ((120 - yPos) / 120) * 100; // Scale Y position to 0-100%

            const circleClasses = [
                'absolute', 'w-4', 'h-4', 'rounded-full', 'flex', 'items-center', 'justify-center', 'text-[8px]', 'font-bold', // Smaller circles
                'transition-all', 'duration-300', 'ease-out', getNeonGlowClass(color), 'score-circle'
            ];
            let circleStyle = `top: ${topPosition}%; transform: translateY(-50%);`;

            // Add glow effect based on color
            circleStyle += `box-shadow: 0 0 5px ${color}, inset 0 0 3px ${color};`;


            // Text color logic
            if (color === '#F0F0F0') {
                circleClasses.push('text-black'); // Black text on white background
            } else {
                circleClasses.push('text-white'); // White text on other backgrounds
            }
            circleStyle += `background-color: ${color};`;


            const dayColumn = document.createElement('div');
            dayColumn.className = 'flex flex-col items-center justify-end h-full flex-1 relative';

            const circleElement = document.createElement('div');
            circleElement.className = circleClasses.join(' ');
            circleElement.style = circleStyle;
            circleElement.textContent = score;
            circleElement.dataset.details = JSON.stringify(dayData);

            circleElement.addEventListener('click', (event) => {
                event.stopPropagation();
                const isVisible = scoreTooltip.classList.contains('opacity-100');
                const isForThisElement = scoreTooltip.dataset.identifier === dayData.date;

                if (isVisible && isForThisElement) {
                    hideTooltip();
                } else {
                    scoreTooltip.dataset.identifier = dayData.date;
                    showTooltip(circleElement, dayData);
                }
            });

            dayColumn.appendChild(circleElement);
            graphContainer.appendChild(dayColumn);
        });
    }

    async function fetchScoreGraphData(periodDays) {
        try {
            // Assuming a new endpoint or modification to an existing one to fetch data for a given number of days
            const response = await fetch(`/users/me/stats/summary-by-period?days=${periodDays}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!response.ok) {
                if (response.status === 401) window.location.href = '/';
                throw new Error('Failed to fetch score graph data');
            }

            const data = await response.json();
            renderScoreGraph(data.daily_breakdown);

        } catch (error) {
            console.error('Error fetching score graph data:', error);
            const graphContainer = document.getElementById('score-graph-container');
            if (graphContainer) graphContainer.innerHTML = '<p class="text-center text-red-500 mt-4">Не удалось загрузить данные индекса.</p>';
        }
    }

    // --- Управление состоянием формы анализа ---
    const analysisStateKey = 'analysisInProgress';

    function saveAnalysisState(state) {
        localStorage.setItem(analysisStateKey, JSON.stringify(state));
    }

    function loadAnalysisState() {
        const state = localStorage.getItem(analysisStateKey);
        return state ? JSON.parse(state) : null;
    }

    function clearAnalysisState() {
        localStorage.removeItem(analysisStateKey);
    }

    function resetAnalysisUI() {
        // Не скрываем resultsSection, а сбрасываем его содержимое
        aiResponseTextDiv.innerHTML = '';

        const fields = ['calories', 'protein', 'fat', 'carbohydrates'];
        fields.forEach(field => {
            const slider = document.getElementById(`${field}-slider`);
            const input = document.getElementById(field);
            slider.value = 0;
            input.value = 0;
        });

        // Скрываем только AI коуча, так как он относится к конкретному анализу
        aiCoachSection.style.display = 'none';
        localStorage.removeItem('lastAiAdvice');
        localStorage.removeItem('lastCoachModel');

        clearAnalysisState();
    }

    function populateResultsFromState(state) {
        if (!state) return;

        currentFoodName = state.foodName;
        aiResponseTextDiv.innerHTML = `<p>${currentFoodName}</p>`;

        document.getElementById('meal-type').value = state.mealType;

        const fields = ['calories', 'protein', 'fat', 'carbohydrates'];
        fields.forEach(field => {
            const slider = document.getElementById(`${field}-slider`);
            const input = document.getElementById(field);
            const value = state.values[field] || 0;

            slider.value = value;
            input.value = value;

            const config = { minBuffer: field === 'calories' ? 500 : 30, step: field === 'calories' ? 10 : 1 };
            const buffer = Math.max(value * 0.5, config.minBuffer);
            const minValue = Math.max(0, Math.floor((value - buffer) / config.step) * config.step);
            const maxValue = Math.ceil((value + buffer) / config.step) * config.step;
            slider.min = minValue;
            slider.max = maxValue;
        });

        resultsSection.style.display = 'block';
    }

    function updateRingWithOverflow(ringId, value, maxValue) {
        const ring = document.getElementById(ringId);
        if (!ring) return;
        const bar = ring.querySelector('.progress-ring-bar');
        const radius = bar.r.baseVal.value;
        const circumference = 2 * Math.PI * radius;
        bar.style.strokeDasharray = `${circumference} ${circumference}`;
        if (maxValue === 0) {
            bar.style.strokeDashoffset = circumference;
            return;
        }
        const percentage = Math.min(value / maxValue, 1);
        const offset = circumference - (percentage * circumference);
        bar.style.strokeDashoffset = offset;
        const valueElementId = ringId.replace('-ring', '-value');
        const valueElement = document.getElementById(valueElementId);
        if (valueElement) {
            valueElement.textContent = Math.round(value);
        }
    }

    async function fetchAndDisplayAverageStats() {
        try {
            const response = await fetch('/users/me/average-stats', { headers: { 'Authorization': `Bearer ${token}` } });
            if (!response.ok) throw new Error('Could not fetch average stats.');
            const stats = await response.json();
            updateRingWithOverflow('avg-calories-ring', stats.avg_calories, stats.target_calories);
            updateRingWithOverflow('avg-protein-ring', stats.avg_protein, stats.target_protein);
            updateRingWithOverflow('avg-fat-ring', stats.avg_fat, stats.target_fat);
            updateRingWithOverflow('avg-carbs-ring', stats.avg_carbohydrates, stats.target_carbohydrates);
            mealLogsContainer.dataset.targetCalories = stats.target_calories;
            mealLogsContainer.dataset.targetProtein = stats.target_protein;
            mealLogsContainer.dataset.targetFat = stats.target_fat;
            mealLogsContainer.dataset.targetCarbohydrates = stats.target_carbohydrates;
        } catch (error) {
            console.error("Error fetching average stats:", error);
        }
    }

    async function fetchAndDisplayMealHistory() {
        try {
            const response = await fetch('/meals/', { headers: { 'Authorization': `Bearer ${token}` } });
            if (!response.ok) throw new Error(`Could not fetch meal history. Status: ${response.status}`);
            const meals = await response.json();
            mealLogsContainer.innerHTML = '';
            if (meals.length === 0) {
                mealLogsContainer.innerHTML = `<p class="text-center text-gray-500 mt-4">Записей о приемах пищи еще нет.</p>`;
                return;
            }
            const mealsByDate = meals.reduce((acc, meal) => {
                const dateKey = new Date(meal.timestamp).toLocaleDateString('ru-RU');
                if (!acc[dateKey]) acc[dateKey] = [];
                acc[dateKey].push(meal);
                return acc;
            }, {});
            const today = new Date().toLocaleDateString('ru-RU');
            const yesterday = new Date(Date.now() - 86400000).toLocaleDateString('ru-RU');
            const mealTypeTranslations = { breakfast: 'Завтрак', lunch: 'Обед', dinner: 'Ужин', snack: 'Перекус' };
            for (const dateKey in mealsByDate) {
                let dateLabel = (dateKey === today) ? 'Сегодня' : (dateKey === yesterday) ? 'Вчера' : dateKey;
                const divider = document.createElement('div');
                divider.className = 'date-divider';
                divider.innerHTML = `<span>${dateLabel}</span>`;
                mealLogsContainer.appendChild(divider);
                const mealsOnDate = mealsByDate[dateKey];
                mealsOnDate.forEach(meal => {
                    const mealId = meal.id;
                    const mealType = mealTypeTranslations[meal.meal_type] || 'Прием пищи';
                    const card = document.createElement('div');
                    card.className = 'glassmorphism rounded-xl p-4 neon-glow-pantone-gray';
                    card.innerHTML = `
                        <div class="text-center">
                            <h4 class="text-lg font-semibold">${mealType}</h4>
                            <p class="text-sm text-gray-400 -mt-1 mb-3">${meal.food_name || 'Блюдо'}</p>
                        </div>
                        <div class="flex justify-center w-full space-x-2">
                            <div class="text-center flex flex-col items-center space-y-1"><div class="ring-container w-12 aspect-square neon-glow-amber relative"><svg id="log-${mealId}-calories-ring" class="progress-ring-svg" viewBox="0 0 120 120"><circle class="progress-ring-bg" cx="60" cy="60" r="54"/><circle class="progress-ring-bar" cx="60" cy="60" r="54" style="stroke: var(--color-amber);"/></svg><div class="absolute inset-0 flex flex-col items-center justify-center"><span id="log-${mealId}-calories-value" class="font-bold text-sm" style="color: var(--color-amber);">0</span><span class="label-text text-xs -mt-1">ккал</span></div></div></div>
                            <div class="text-center flex flex-col items-center space-y-1"><div class="ring-container w-12 aspect-square neon-glow-protein-white relative"><svg id="log-${mealId}-protein-ring" class="progress-ring-svg" viewBox="0 0 120 120"><circle class="progress-ring-bg" cx="60" cy="60" r="54"/><circle class="progress-ring-bar" cx="60" cy="60" r="54" style="stroke: var(--color-protein-white);"/></svg><div class="absolute inset-0 flex flex-col items-center justify-center"><span id="log-${mealId}-protein-value" class="font-bold text-sm" style="color: var(--color-protein-white);">0</span><span class="label-text text-xs -mt-1">г</span></div></div></div>
                            <div class="text-center flex flex-col items-center space-y-1"><div class="ring-container w-12 aspect-square neon-glow-golden-orange relative"><svg id="log-${mealId}-fat-ring" class="progress-ring-svg" viewBox="0 0 120 120"><circle class="progress-ring-bg" cx="60" cy="60" r="54"/><circle class="progress-ring-bar" cx="60" cy="60" r="54" style="stroke: var(--color-golden-orange);"/></svg><div class="absolute inset-0 flex flex-col items-center justify-center"><span id="log-${mealId}-fat-value" class="font-bold text-sm" style="color: var(--color-golden-orange);">0</span><span class="label-text text-xs -mt-1">г</span></div></div></div>
                            <div class="text-center flex flex-col items-center space-y-1"><div class="ring-container w-12 aspect-square neon-glow-muted-teal relative"><svg id="log-${mealId}-carbohydrates-ring" class="progress-ring-svg" viewBox="0 0 120 120"><circle class="progress-ring-bg" cx="60" cy="60" r="54"/><circle class="progress-ring-bar" cx="60" cy="60" r="54" style="stroke: var(--color-muted-teal);"/></svg><div class="absolute inset-0 flex flex-col items-center justify-center"><span id="log-${mealId}-carbohydrates-value" class="font-bold text-sm" style="color: var(--color-muted-teal);">0</span><span class="label-text text-xs -mt-1">г</span></div></div></div>
                        </div>
                    `;
                    mealLogsContainer.appendChild(card);
                    const targetCalories = parseFloat(mealLogsContainer.dataset.targetCalories || 0);
                    const targetProtein = parseFloat(mealLogsContainer.dataset.targetProtein || 0);
                    const targetFat = parseFloat(mealLogsContainer.dataset.targetFat || 0);
                    const targetCarbohydrates = parseFloat(mealLogsContainer.dataset.targetCarbohydrates || 0);
                    updateRingWithOverflow(`log-${mealId}-calories-ring`, meal.total_calories, targetCalories);
                    updateRingWithOverflow(`log-${mealId}-protein-ring`, meal.total_protein, targetProtein);
                    updateRingWithOverflow(`log-${mealId}-fat-ring`, meal.total_fat, targetFat);
                    updateRingWithOverflow(`log-${mealId}-carbohydrates-ring`, meal.total_carbohydrates, targetCarbohydrates);
                });
            }
        } catch (error) {
            console.error("Error in fetchAndDisplayMealHistory:", error);
            mealLogsContainer.innerHTML = `<p class="text-center text-red-500 mt-4">Не удалось загрузить историю приемов пищи.</p>`;
        }
    }

    mealImageInput.addEventListener('change', () => {
        if (mealImageInput.files[0]) {
            uploadButtonLabel.classList.add('has-image');
            uploadButtonLabel.textContent = 'Фото добавлено!';
        }
    });

    function calculateCalories(protein, fat, carbs) {
        return Math.round((protein * 4) + (fat * 9) + (carbs * 4));
    }

    function updateCaloriesFromMacros() {
        const protein = parseFloat(document.getElementById('protein').value) || 0;
        const fat = parseFloat(document.getElementById('fat').value) || 0;
        const carbs = parseFloat(document.getElementById('carbohydrates').value) || 0;
        const calculatedCalories = calculateCalories(protein, fat, carbs);
        const caloriesInput = document.getElementById('calories');
        const caloriesSlider = document.getElementById('calories-slider');
        caloriesInput.value = calculatedCalories;
        const currentMax = parseFloat(caloriesSlider.max);
        const currentMin = parseFloat(caloriesSlider.min);
        if (calculatedCalories > currentMax || calculatedCalories < currentMin) {
            const config = { minBuffer: 500, step: 10 };
            const buffer = Math.max(calculatedCalories * 0.5, config.minBuffer);
            const minValue = Math.max(0, Math.floor((calculatedCalories - buffer) / config.step) * config.step);
            const maxValue = Math.ceil((calculatedCalories + buffer) / config.step) * config.step;
            caloriesSlider.min = minValue;
            caloriesSlider.max = maxValue;
        }
        caloriesSlider.value = calculatedCalories;
        saveCurrentAnalysis();
    }

    function setupSliderSync(sliderId, inputId, isMacro = false) {
        const slider = document.getElementById(sliderId);
        const input = document.getElementById(inputId);
        if (slider && input) {
            const updateAndSave = () => {
                if (isMacro) updateCaloriesFromMacros();
                saveCurrentAnalysis();
            };
            slider.addEventListener('input', (event) => { input.value = event.target.value; updateAndSave(); });
            input.addEventListener('change', (event) => { slider.value = event.target.value; updateAndSave(); });
        }
    }
    setupSliderSync('calories-slider', 'calories');
    setupSliderSync('protein-slider', 'protein', true);
    setupSliderSync('fat-slider', 'fat', true);
    setupSliderSync('carbohydrates-slider', 'carbohydrates', true);
    document.getElementById('meal-type').addEventListener('change', saveCurrentAnalysis);

    function saveCurrentAnalysis() {
        const state = {
            foodName: currentFoodName,
            mealType: document.getElementById('meal-type').value,
            values: {
                calories: document.getElementById('calories').value,
                protein: document.getElementById('protein').value,
                fat: document.getElementById('fat').value,
                carbohydrates: document.getElementById('carbohydrates').value,
            }
        };
        saveAnalysisState(state);
    }

    async function compressImage(file, maxSize = 1024, quality = 0.85) {
        return new Promise((resolve) => {
            const img = new Image();
            img.onload = () => {
                const canvas = document.createElement('canvas');
                let width = img.width; let height = img.height;
                if (width > maxSize || height > maxSize) {
                    if (width > height) { height = Math.round((height * maxSize) / width); width = maxSize; }
                    else { width = Math.round((width * maxSize) / height); height = maxSize; }
                }
                canvas.width = width; canvas.height = height;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, width, height);
                canvas.toBlob((blob) => { resolve(blob); }, 'image/jpeg', quality);
            };
            img.src = URL.createObjectURL(file);
        });
    }

    const statusMessages = ['Загружаем фото...', 'Ищем еду на изображении...', 'Определяем размер порции...', 'Считаем КБЖУ...', 'Готовим совет от AI-коуча...'];
    function showAnalysisStatus(index) {
        analysisStatus.innerHTML = `<span class="spinner"></span>${statusMessages[index]}`;
        analysisStatus.classList.add('visible');
    }
    function hideAnalysisStatus() {
        analysisStatus.classList.remove('visible');
        if (statusInterval) clearInterval(statusInterval);
    }

    let statusInterval;
    const analysisStatus = document.getElementById('analysis-status');

    analyzeForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        errorMessageDiv.textContent = '';
        analyzeButton.disabled = true;
        analyzeButton.textContent = 'Ждите...';
        aiCoachSection.style.display = 'none';
        nutritionModelInfo.textContent = '';

        const formData = new FormData();
        if (mealImageInput.files.length > 0) {
            const originalFile = mealImageInput.files[0];
            analyzeButton.textContent = 'Подготовка фото...';
            const compressedFile = await compressImage(originalFile);
            formData.append('file', compressedFile, originalFile.name);
        }
        if (mealDescriptionInput.value.trim() !== '') formData.append('description', mealDescriptionInput.value.trim());
        if (!mealImageInput.files.length && mealDescriptionInput.value.trim() === '') {
            errorMessageDiv.textContent = 'Пожалуйста, загрузите фото или введите описание.';
            analyzeButton.disabled = false;
            analyzeButton.textContent = 'Анализировать';
            return;
        }

        let statusIndex = 0;
        showAnalysisStatus(statusIndex);
        statusInterval = setInterval(() => {
            statusIndex = (statusIndex + 1) % statusMessages.length;
            showAnalysisStatus(statusIndex);
        }, 3000);

        aiCoachSection.style.display = 'block';
        aiCoachSection.classList.add('loading');
        aiCoachTitle.textContent = 'AI-коуч анализирует ваш выбор...';
        aiCoachAdvice.textContent = '';

        try {
            const response = await fetch('/analyze-meal/', { method: 'POST', headers: { 'Authorization': `Bearer ${token}` }, body: formData });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Ошибка анализа блюда.');
            }
            clearInterval(statusInterval);
            const result = await response.json();

            const advice = result.ai_coach_advice || 'Не удалось получить совет.';
            aiCoachSection.classList.remove('loading');
            aiCoachTitle.textContent = `Совет от AI (${result.coach_model_used || 'модель не указана'})`;
            aiCoachAdvice.textContent = advice;
            localStorage.setItem('lastAiAdvice', advice);
            localStorage.setItem('lastCoachModel', result.coach_model_used);

            nutritionModelInfo.textContent = `Проанализировано с помощью: ${result.nutrition_model_used || 'модель не указана'}`;

            currentFoodName = result.ai_response_text;
            const initialState = {
                foodName: currentFoodName,
                mealType: document.getElementById('meal-type').value,
                values: {
                    calories: Math.round(result.suggested_totals.total_calories || 0),
                    protein: Math.round(result.suggested_totals.total_protein || 0),
                    fat: Math.round(result.suggested_totals.total_fat || 0),
                    carbohydrates: Math.round(result.suggested_totals.total_carbohydrates || 0),
                }
            };
            saveAnalysisState(initialState);
            populateResultsFromState(initialState);

            resultsSection.style.display = 'block';
            analysisStatus.innerHTML = '<span style="color: #50C878;">✓ Анализ завершён!</span>';
            setTimeout(hideAnalysisStatus, 2000);
        } catch (error) {
            clearInterval(statusInterval);
            errorMessageDiv.textContent = error.message;
            hideAnalysisStatus();
            aiCoachSection.style.display = 'none';
        } finally {
            analyzeButton.disabled = false;
            analyzeButton.textContent = 'Анализировать';
        }
    });

    confirmForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        errorMessageDiv.textContent = '';
        const confirmButton = document.getElementById('confirm-button');
        confirmButton.disabled = true;
        confirmButton.textContent = 'Добавляем...';

        const mealData = {
            meal_type: document.getElementById('meal-type').value,
            food_name: currentFoodName,
            total_calories: parseFloat(document.getElementById('calories').value),
            total_protein: parseFloat(document.getElementById('protein').value),
            total_fat: parseFloat(document.getElementById('fat').value),
            total_carbohydrates: parseFloat(document.getElementById('carbohydrates').value),
        };

        try {
            const response = await fetch('/meals/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify(mealData)
            });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Ошибка добавления приема пищи.');
            }

            resetAnalysisUI();
            analyzeForm.reset();
            uploadButtonLabel.classList.remove('has-image');
            uploadButtonLabel.textContent = 'Добавить фото';

            errorMessageDiv.style.color = '#50C878';
            errorMessageDiv.textContent = 'Прием пищи успешно добавлен!';
            setTimeout(() => { errorMessageDiv.textContent = ''; errorMessageDiv.style.color = ''; }, 3000);

            await fetchAndDisplayMealHistory();
            await fetchAndDisplayAverageStats();
            // Re-fetch score graph data after meal is added
            const currentPeriodBtn = document.querySelector('.period-button.bg-gray-700');
            if (currentPeriodBtn) {
                const periodDays = currentPeriodBtn.id === 'one-month-btn' ? 30 : 90;
                await fetchScoreGraphData(periodDays);
            }
        } catch (error) {
            errorMessageDiv.textContent = error.message;
        } finally {
            confirmButton.disabled = false;
            confirmButton.textContent = 'Добавить прием пищи';
        }
    });

    // --- Кнопки выбора периода ---
    const oneMonthBtn = document.getElementById('one-month-btn');
    const threeMonthsBtn = document.getElementById('three-months-btn');

    function setActivePeriodButton(activeBtn) {
        [oneMonthBtn, threeMonthsBtn].forEach(btn => {
            btn.classList.remove('active');
            btn.classList.add('text-gray-400');
        });
        activeBtn.classList.add('active');
        activeBtn.classList.remove('text-gray-400');
    }

    oneMonthBtn.addEventListener('click', () => {
        setActivePeriodButton(oneMonthBtn);
        fetchScoreGraphData(30); // 1 month
    });

    threeMonthsBtn.addEventListener('click', () => {
        setActivePeriodButton(threeMonthsBtn);
        fetchScoreGraphData(90); // 3 months
    });

    // --- Инициализация страницы ---
    const lastAdvice = localStorage.getItem('lastAiAdvice');
    const lastCoachModel = localStorage.getItem('lastCoachModel');
    if (lastAdvice) {
        aiCoachSection.style.display = 'block';
        aiCoachTitle.textContent = `Совет от AI (${lastCoachModel || 'модель не указана'})`;
        aiCoachAdvice.textContent = lastAdvice;
    }

    const savedState = loadAnalysisState();
    if (savedState) {
        populateResultsFromState(savedState);
    }

    await fetchAndDisplayAverageStats();
    await fetchAndDisplayMealHistory();
    // Initial load for score graph (default to 1 month)
    setActivePeriodButton(oneMonthBtn);
    await fetchScoreGraphData(30);
});