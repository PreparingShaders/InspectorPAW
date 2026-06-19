document.addEventListener('DOMContentLoaded', async () => {
    // --- Глобальный перехватчик для fetch ---
    async function fetchWithAuth(url, options = {}) {
        const token = localStorage.getItem('accessToken');
        if (token && !options.headers?.Authorization) {
            if (!options.headers) {
                options.headers = {};
            }
            options.headers['Authorization'] = `Bearer ${token}`;
        }
        const response = await fetch(url, options);
        if (response.status === 401) {
            localStorage.removeItem('accessToken');
            window.location.href = '/login';
            return new Promise(() => {});
        }
        return response;
    }

    const token = localStorage.getItem('accessToken');
    if (!token) {
        window.location.href = '/login';
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
        aiResponseTextDiv.innerHTML = '';
        const fields = ['calories', 'protein', 'fat', 'carbohydrates'];
        fields.forEach(field => {
            const slider = document.getElementById(`${field}-slider`);
            const input = document.getElementById(field);
            slider.value = 0;
            input.value = 0;
        });
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

    // --- Новый, исправленный код для интерактивного кольца ---
    function createInteractiveRing(container, data, totalCalories) {
        container.innerHTML = '';

        const svgNS = "http://www.w3.org/2000/svg";
        const svg = document.createElementNS(svgNS, "svg");
        const viewBoxSize = 280; // Увеличим, чтобы было место для лейблов и тени
        svg.setAttribute("viewBox", `0 0 ${viewBoxSize} ${viewBoxSize}`);

        const defs = document.createElementNS(svgNS, "defs");
        const filter = document.createElementNS(svgNS, "filter");
        filter.setAttribute("id", "drop-shadow");
        filter.innerHTML = `<feDropShadow dx="0" dy="4" stdDeviation="3" flood-color="#000000" flood-opacity="0.4"/>`;
        defs.appendChild(filter);
        svg.appendChild(defs);

        const center = viewBoxSize / 2;
        const radius = 100;
        const strokeWidth = 25;
        const circumference = 2 * Math.PI * radius;
        const gapDegrees = 2.5; // Увеличим отступ

        const totalGrams = data.reduce((sum, item) => sum + item.value, 0);

        if (totalGrams === 0) {
            // Отрисовка плейсхолдера, если нет данных
            const placeholder = document.createElementNS(svgNS, "circle");
            placeholder.setAttribute("cx", center);
            placeholder.setAttribute("cy", center);
            placeholder.setAttribute("r", radius);
            placeholder.setAttribute("stroke", "var(--border-color)");
            placeholder.setAttribute("stroke-width", strokeWidth);
            placeholder.setAttribute("fill", "none");
            svg.appendChild(placeholder);
            const centerText = document.createElementNS(svgNS, "text");
            centerText.setAttribute("x", "50%");
            centerText.setAttribute("y", "50%");
            centerText.setAttribute("text-anchor", "middle");
            centerText.setAttribute("dominant-baseline", "middle");
            centerText.setAttribute("font-size", "20");
            centerText.setAttribute("fill", "var(--text-secondary)");
            centerText.textContent = "Нет данных";
            svg.appendChild(centerText);
            container.appendChild(svg);
            return;
        }

        let currentAngle = 0;
        const segments = [];
        const labels = [];

        data.forEach(item => {
            const percentage = item.value / totalGrams;
            const angle = 360 * percentage;
            const arcLength = (circumference / 360) * (angle > gapDegrees ? angle - gapDegrees : angle);

            const segment = document.createElementNS(svgNS, "circle");
            segment.setAttribute("cx", center);
            segment.setAttribute("cy", center);
            segment.setAttribute("r", radius);
            segment.setAttribute("stroke", item.color);
            segment.setAttribute("stroke-width", strokeWidth);
            segment.setAttribute("stroke-dasharray", `${arcLength} ${circumference}`);
            segment.setAttribute("stroke-linecap", "butt"); // Важно для четких отступов
            segment.setAttribute("transform", `rotate(${currentAngle - 90 + gapDegrees / 2}, ${center}, ${center})`);
            segment.setAttribute("fill", "none");
            segment.setAttribute("filter", "url(#drop-shadow)"); // Применяем тень
            segments.push(segment);

            // Сохраняем углы для обработчика кликов
            item.startAngle = currentAngle;
            item.endAngle = currentAngle + angle;

            // Создаем лейблы, но пока не добавляем в SVG
            const labelRadius = radius + strokeWidth;
            const midAngleRad = (currentAngle + angle / 2 - 90) * Math.PI / 180;
            const x = center + labelRadius * Math.cos(midAngleRad);
            const y = center + labelRadius * Math.sin(midAngleRad);

            const label = document.createElementNS(svgNS, "text");
            label.setAttribute("class", "nutrient-ring-label");
            label.setAttribute("x", x);
            label.setAttribute("y", y);
            label.textContent = item.label;
            labels.push(label);

            currentAngle += angle;
        });

        // Сначала добавляем все сегменты, потом все лейблы
        segments.forEach(s => svg.appendChild(s));
        labels.forEach(l => svg.appendChild(l));

        // Центральный текст (калории)
        const centerText = document.createElementNS(svgNS, "text");
        centerText.setAttribute("x", "50%");
        centerText.setAttribute("y", "50%");
        centerText.setAttribute("text-anchor", "middle");
        centerText.setAttribute("dominant-baseline", "middle");
        centerText.setAttribute("font-size", "40");
        centerText.setAttribute("font-weight", "bold");
        centerText.setAttribute("fill", "var(--color-amber)");
        centerText.innerHTML = `
            <tspan x="50%" dy="-0.1em">${Math.round(totalCalories)}</tspan>
            <tspan x="50%" dy="1.2em" font-size="16" fill="var(--text-secondary)">ккал</tspan>
        `;
        svg.appendChild(centerText);

        // Единый обработчик кликов
        svg.addEventListener('click', (event) => {
            const rect = svg.getBoundingClientRect();
            const x = event.clientX - rect.left - center;
            const y = event.clientY - rect.top - center;

            let clickAngle = Math.atan2(y, x) * 180 / Math.PI + 90;
            if (clickAngle < 0) {
                clickAngle += 360;
            }

            const clickedSegment = data.find(item => clickAngle >= item.startAngle && clickAngle < item.endAngle);

            if (clickedSegment) {
                console.log(`Clicked on ${clickedSegment.label}`);
                const input = document.getElementById(clickedSegment.id);
                if (input) {
                    const sliderGroup = input.closest('.slider-group');
                    if (sliderGroup) {
                        sliderGroup.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        input.focus();
                    }
                }
            }
        });

        container.appendChild(svg);
    }

    async function fetchAndDrawRing() {
        try {
            const response = await fetchWithAuth('/users/me/average-stats');
            if (!response.ok) throw new Error('Could not fetch average stats.');
            const stats = await response.json();

            const container = document.getElementById('interactive-rings-container');
            if (!container) return;

            const nutrientData = [
                { id: 'protein', label: 'Белки', value: stats.avg_protein || 0, color: 'var(--color-protein-white)' },
                { id: 'fat', label: 'Жиры', value: stats.avg_fat || 0, color: 'var(--color-golden-orange)' },
                { id: 'carbohydrates', label: 'Углеводы', value: stats.avg_carbohydrates || 0, color: 'var(--color-muted-teal)' }
            ];

            createInteractiveRing(container, nutrientData, stats.avg_calories);

            mealLogsContainer.dataset.targetCalories = stats.target_calories;
            mealLogsContainer.dataset.targetProtein = stats.target_protein;
            mealLogsContainer.dataset.targetFat = stats.target_fat;
            mealLogsContainer.dataset.targetCarbohydrates = stats.target_carbohydrates;

        } catch (error) {
            console.error("Error fetching average stats for ring:", error);
            // В случае ошибки, рисуем пустой круг
            const container = document.getElementById('interactive-rings-container');
            if (container) createInteractiveRing(container, [], 0);
        }
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

    async function fetchAndDisplayMealHistory() {
        try {
            const response = await fetchWithAuth('/meals/');
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
            const response = await fetchWithAuth('/analyze-meal/', { method: 'POST', body: formData });
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
            const response = await fetchWithAuth('/meals/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
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
            await fetchAndDrawRing(); // Обновляем кольцо после добавления еды
        } catch (error) {
            errorMessageDiv.textContent = error.message;
        } finally {
            confirmButton.disabled = false;
            confirmButton.textContent = 'Добавить прием пищи';
        }
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

    await fetchAndDrawRing();
    await fetchAndDisplayMealHistory();
});