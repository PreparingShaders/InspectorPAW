document.addEventListener('DOMContentLoaded', async () => {
    // Убираем проверку токена здесь, т.к. fetchWithAuth будет делать это при каждом запросе
    // const token = localStorage.getItem('accessToken');
    // if (!token) { window.location.href = '/'; return; }

    // --- Элементы UI ---
    const mealImageInput = document.getElementById('meal-image');
    const mealDescriptionInput = document.getElementById('meal-description');
    const sendToAiBtn = document.getElementById('send-to-ai-btn');
    const initialView = document.getElementById('initial-view');
    const imageAddedView = document.getElementById('image-added-view');
    const imagePreview = document.getElementById('image-preview'); // Добавляем ссылку на элемент предпросмотра

    const mealLogsContainer = document.getElementById('meal-logs-container');
    const aiCoachTitle = document.getElementById('ai-coach-title');
    const aiCoachAdvice = document.getElementById('ai-coach-advice');
    const errorMessageDiv = document.getElementById('error-message');
    const confirmForm = document.getElementById('confirm-form');
    const cancelAnalysisBtn = document.getElementById('cancel-analysis-btn');

    let currentFoodName = '';
    let compressedFile = null; // Для хранения сжатого файла
    let tooltipTimeout;
    const scoreTooltip = document.getElementById('score-tooltip');

    const steps = {
        1: document.getElementById('step-1'),
        2: document.getElementById('step-2'),
        3: document.getElementById('step-3')
    };

    // --- Функция сжатия изображения ---
    function compressImage(file, maxWidth = 1280, quality = 0.85) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.readAsDataURL(file);
            reader.onload = (event) => {
                const img = new Image();
                img.src = event.target.result;
                img.onload = () => {
                    const canvas = document.createElement('canvas');
                    let { width, height } = img;

                    if (width > height) {
                        if (width > maxWidth) {
                            height = Math.round((height * maxWidth) / width);
                            width = maxWidth;
                        }
                    } else {
                        if (height > maxWidth) {
                            width = Math.round((width * maxWidth) / height);
                            height = maxWidth;
                        }
                    }

                    canvas.width = width;
                    canvas.height = height;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0, width, height);

                    canvas.toBlob(
                        (blob) => {
                            if (blob) {
                                // Создаем новый File объект, чтобы сохранить имя файла
                                const newFile = new File([blob], file.name, {
                                    type: 'image/jpeg',
                                    lastModified: Date.now(),
                                });
                                resolve(newFile);
                            } else {
                                reject(new Error('Canvas to Blob conversion failed'));
                            }
                        },
                        'image/jpeg',
                        quality
                    );
                };
                img.onerror = (error) => reject(error);
            };
            reader.onerror = (error) => reject(error);
        });
    }


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
        compressedFile = null; // Сбрасываем сжатый файл
        if (imagePreview) { // Очищаем предпросмотр изображения
            imagePreview.src = '';
        }
        showInitialView();
        goToStep(1);
    }

    // --- Логика анализа ---
    mealImageInput.addEventListener('change', async () => {
        if (!mealImageInput.files || mealImageInput.files.length === 0) return;

        // Опционально: можно добавить индикатор загрузки/сжатия здесь

        try {
            const originalFile = mealImageInput.files[0];
            compressedFile = await compressImage(originalFile); // Сжимаем изображение
            console.log(`Изображение сжато с ${Math.round(originalFile.size / 1024)}KB до ${Math.round(compressedFile.size / 1024)}KB`);

            // Отображаем сжатое изображение для предпросмотра
            if (imagePreview && compressedFile) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    imagePreview.src = e.target.result;
                };
                reader.readAsDataURL(compressedFile);
            }

            showImageAddedView(); // Показываем следующий шаг после успешного сжатия
        } catch (error) {
            console.error('Ошибка сжатия изображения:', error);
            alert('Не удалось обработать изображение. Попробуйте другое.');
            resetWizard();
        }

        // Опционально: убрать индикатор загрузки
    });

    sendToAiBtn.addEventListener('click', async () => {
        if (!compressedFile) {
            alert('Сначала выберите фото.');
            return;
        }

        goToStep(2);

        const formData = new FormData();
        formData.append('file', compressedFile, compressedFile.name); // Используем сжатый файл
        if (mealDescriptionInput.value.trim()) {
            formData.append('description', mealDescriptionInput.value.trim());
        }

        const aiModel = localStorage.getItem('aiHubCurrentModel');
        if (aiModel) formData.append('ai_model', aiModel);

        try {
            // Используем fetchWithAuth вместо fetch
            const res = await fetchWithAuth('/analyze-meal/', {
                method: 'POST',
                body: formData
                // Заголовки Authorization и Content-Type для FormData устанавливаются автоматически
            });

            if (!res.ok) {
                const errorData = await res.json();
                throw new Error(errorData.detail || 'Ошибка анализа');
            }

            const result = await res.json();

            const foodName = result.ai_response_text || 'Прием пищи';
            const coachAdvice = result.ai_coach_advice || 'Приятного аппетита!';

            aiCoachTitle.textContent = `Совет от AI (${result.coach_model_used || 'Vision'})`;
            aiCoachAdvice.innerHTML = `Блюдо: ${foodName}<br><br>${coachAdvice}`;
            currentFoodName = foodName;

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
            // Используем fetchWithAuth вместо fetch
            await fetchWithAuth('/meals/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
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
                // Передаем найденный SVG-элемент напрямую
                const summaryScoreRingSvg = scoreRingContainer.querySelector(`#${scoreRingId}`);
                if (summaryScoreRingSvg) {
                    updateRing(summaryScoreRingSvg, score, 100);
                }
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

                const ringWrapper = document.createElement('div');
                ringWrapper.className = 'text-center flex flex-col items-center space-y-1';
                ringWrapper.innerHTML = `
                    <div class="ring-container w-12 aspect-square ${config.neon} relative">
                        <svg id="${ringId}" class="progress-ring-svg" viewBox="0 0 120 120">
                            <circle class="progress-ring-bg" cx="60" cy="60" r="54" />
                            <circle class="progress-ring-bar" cx="60" cy="60" r="54" style="stroke: ${config.color};" />
                        </svg>
                        <div class="absolute inset-0 flex flex-col items-center justify-center">
                            <span id="${valueId}" class="font-bold text-base" style="color: ${config.color};">0</span>
                        </div>
                    </div>
                    <p class="text-xs font-semibold text-gray-400 mt-1">${config.label}</p>
                `;

                paceBarsContainer.appendChild(ringWrapper);

                // Находим SVG-элемент внутри только что созданного ringWrapper
                const paceRingSvg = ringWrapper.querySelector(`#${ringId}`);
                if (paceRingSvg) {
                    updateRing(paceRingSvg, pace.actual, pace.expected);
                    // Обновляем цвет обводки после updateRing, если он изменился
                    const ringBar = paceRingSvg.querySelector('.progress-ring-bar');
                    if(ringBar) {
                        let ringColor = config.color;
                        const percentage = pace.expected > 0 ? (pace.actual / pace.expected) * 100 : 0;
                        if (percentage > 100) {
                            if (key === 'protein') {
                                ringColor = '#22c55e';
                            } else {
                                ringColor = '#e11d48';
                            }
                        }
                        ringBar.style.stroke = ringColor;
                    }
                    const valueSpan = ringWrapper.querySelector(`#${valueId}`);
                    if(valueSpan) {
                        let ringColor = config.color;
                        const percentage = pace.expected > 0 ? (pace.actual / pace.expected) * 100 : 0;
                        if (percentage > 100) {
                            if (key === 'protein') {
                                ringColor = '#22c55e';
                            } else {
                                ringColor = '#e11d48';
                            }
                        }
                        valueSpan.style.color = ringColor;
                        valueSpan.textContent = Math.round(pace.actual);
                    }
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
    // Изменена для приема элемента SVG напрямую
    function updateRing(ringSvgElement, value, maxValue) {
        if (!ringSvgElement) return;
        const bar = ringSvgElement.querySelector('.progress-ring-bar');
        if (!bar) return;
        const radius = bar.r.baseVal.value;
        const circum = 2 * Math.PI * radius;
        bar.style.strokeDasharray = `${circum} ${circum}`;
        const pct = maxValue > 0 ? Math.min(value / maxValue, 1) : 0;
        bar.style.strokeDashoffset = circum - (pct * circum);

        // Находим span для значения внутри контейнера SVG
        const ringContainer = ringSvgElement.closest('.ring-container');
        if (ringContainer) {
            const valEl = ringContainer.querySelector(`span`); // Ищем span внутри ring-container
            if (valEl) valEl.textContent = Math.round(value);
        }
    }

    async function fetchAndDisplayAverageStats() {
        try {
            // Используем fetchWithAuth вместо fetch
            const res = await fetchWithAuth('/users/me/average-stats');
            if (res.ok) {
                const s = await res.json();
                // Обновляем вызовы updateRing для средних показателей
                updateRing(document.getElementById('avg-calories-ring'), s.avg_calories, s.target_calories);
                updateRing(document.getElementById('avg-protein-ring'), s.avg_protein, s.target_protein);
                updateRing(document.getElementById('avg-fat-ring'), s.avg_fat, s.target_fat);
                updateRing(document.getElementById('avg-carbs-ring'), s.avg_carbohydrates, s.target_carbohydrates);
                mealLogsContainer.dataset.targets = JSON.stringify(s);
            }
        } catch (e) { console.error("Ошибка статистики:", e); }
    }

    // --- Вспомогательная функция для форматирования даты ---
    function formatDateForLogs(dateString) {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const yesterday = new Date(today);
        yesterday.setDate(today.getDate() - 1);

        const mealDate = new Date(dateString);
        mealDate.setHours(0, 0, 0, 0);

        if (mealDate.getTime() === today.getTime()) {
            return "Сегодня";
        } else if (mealDate.getTime() === yesterday.getTime()) {
            return "Вчера";
        } else {
            return mealDate.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' });
        }
    }

    // --- Метки для макронутриентов ---
    const nutrientLabels = {
        calories: 'Ккал',
        protein: 'Б',
        fat: 'Ж',
        carbs: 'У'
    };

    async function fetchAndDisplayMealHistory() {
        try {
            // Используем fetchWithAuth вместо fetch
            const res = await fetchWithAuth('/meals/');
            let meals = await res.json(); // Используем let, так как будем сортировать
            const targets = JSON.parse(mealLogsContainer.dataset.targets || '{}');
            mealLogsContainer.innerHTML = '';
            const trans = { breakfast: 'Завтрак', lunch: 'Обед', dinner: 'Ужин', snack: 'Перекус' };

            // Сортируем приемы пищи по timestamp в убывающем порядке (самые свежие сверху)
            meals.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

            let lastDate = null;

            meals.forEach(m => {
                const mealTimestamp = new Date(m.timestamp);
                const mealDateString = mealTimestamp.toISOString().split('T')[0]; // YYYY-MM-DD

                if (mealDateString !== lastDate) {
                    // Добавляем заголовок даты
                    const dateHeader = document.createElement('h3');
                    dateHeader.className = 'text-lg font-bold text-center mt-6 mb-3 text-white';
                    dateHeader.textContent = formatDateForLogs(m.timestamp);
                    mealLogsContainer.appendChild(dateHeader);

                    // Добавляем разделитель (кроме самого первого дня)
                    if (lastDate !== null) {
                        const separator = document.createElement('div');
                        separator.className = 'border-t border-white/10 my-4'; // Tailwind классы для тонкого разделителя
                        mealLogsContainer.appendChild(separator);
                    }
                    lastDate = mealDateString;
                }

                const card = document.createElement('div');
                card.className = 'glassmorphism rounded-xl p-4 neon-glow-pantone-gray mb-4';
                card.innerHTML = `
                    <div class="flex justify-between items-center mb-3">
                        <h4 class="font-bold text-lg">${trans[m.meal_type]}</h4>
                        <span class="text-sm text-gray-400">${new Date(m.timestamp).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                    <p class="text-sm text-gray-300 mb-3 text-left">${m.food_name.replace(/\n/g, '<br>')}</p>
                    <div class="border-t border-white/10 my-3"></div>
                    <div class="flex justify-around">
                        ${createMiniRing(m.id, 'calories', m.total_calories, targets.target_calories, 'amber')}
                        ${createMiniRing(m.id, 'protein', m.total_protein, targets.target_protein, 'protein-white')}
                        ${createMiniRing(m.id, 'fat', m.total_fat, targets.target_fat, 'golden-orange')}
                        ${createMiniRing(m.id, 'carbs', m.total_carbohydrates, targets.target_carbohydrates, 'muted-teal')}
                    </div>
                `;
                mealLogsContainer.appendChild(card);

                // Теперь находим SVG-элементы внутри только что добавленной карточки
                ['calories', 'protein', 'fat', 'carbs'].forEach(type => {
                    const ringId = `log-${m.id}-${type}-ring`;
                    const ringSvgElement = card.querySelector(`#${ringId}`); // Ищем внутри card
                    if (ringSvgElement) {
                        updateRing(ringSvgElement, m[`total_${type === 'carbs' ? 'carbohydrates' : type}`], targets[`target_${type === 'carbs' ? 'carbohydrates' : type}`]);
                    } else {
                        console.warn(`SVG ring element with ID ${ringId} not found in card for meal ${m.id}`);
                    }
                });
            });
        } catch (e) { console.error("Ошибка истории:", e); }
    }

    function createMiniRing(id, type, val, target, color) {
        const label = nutrientLabels[type]; // Получаем метку из глобального объекта
        return `<div class="text-center flex flex-col items-center">
                    <div class="ring-container w-10 h-10 relative">
                        <svg id="log-${id}-${type}-ring" class="progress-ring-svg" viewBox="0 0 120 120">
                            <circle class="progress-ring-bg" cx="60" cy="60" r="54"/>
                            <circle class="progress-ring-bar" cx="60" cy="60" r="54" style="stroke: var(--color-${color});"/>
                        </svg>
                        <div class="absolute inset-0 flex items-center justify-center">
                            <span id="log-${id}-${type}-value" class="text-xs font-bold">${Math.round(val)}</span>
                        </div>
                    </div>
                    <p class="text-xs text-gray-400 mt-1">${label}</p>
                </div>`;
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
        document.getElementById('tooltip-target-carbs').textContent = Math.round(dayData.target_carbohydrates); // ИСПРАВЛЕНО: data.target_carbohydrates на dayData.target_carbohydrates
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

    function isLightColor(color) {
        if (!color) return false;
        let r, g, b;
        if (color.startsWith('#')) {
            const hex = color.slice(1);
            r = parseInt(hex.substring(0, 2), 16);
            g = parseInt(hex.substring(2, 4), 16);
            b = parseInt(hex.substring(4, 6), 16);
        } else {
            return false; // Не обрабатываем другие форматы для простоты
        }
        // Формула для определения яркости
        const brightness = (r * 299 + g * 587 + b * 114) / 1000;
        return brightness > 155;
    }

    async function fetchScoreGraphData(days) {
        try {
            const res = await fetchWithAuth(`/users/me/stats/summary-by-period?days=${days}`);
            const data = await res.json();

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

            const sortedForSummary = data.daily_breakdown.length > 0 ? [...data.daily_breakdown].sort((a, b) => new Date(b.date) - new Date(a.date)) : [];
            const latestDay = sortedForSummary.length > 0 ? sortedForSummary[0] : null;

            updateProgressLabSummary(data.progress_lab_summary, latestDay);

            const graphContainer = document.getElementById('score-graph-container');
            const labelsContainer = document.getElementById('x-axis-labels-container');
            graphContainer.innerHTML = '';
            labelsContainer.innerHTML = '';

            const sortedData = data.daily_breakdown.sort((a, b) => new Date(a.date) - new Date(b.date));

            sortedData.forEach((day, index) => {
                const col = document.createElement('div');
                col.className = 'flex-1 h-full relative flex justify-center items-center';

                if (day.daily_score !== null) {
                    const yPos = day.y_axis_pos !== null ? ((120 - day.y_axis_pos) / 120) * 100 : 50;
                    const circle = document.createElement('div');
                    const bgColor = day.status_color || '#F0F0F0';
                    const textColor = isLightColor(bgColor) ? 'text-black' : 'text-white';

                    circle.className = `absolute w-4 h-4 rounded-full flex items-center justify-center text-[8px] font-bold ${textColor} score-circle cursor-pointer`;
                    circle.style.top = `${yPos}%`;
                    circle.style.backgroundColor = bgColor;
                    circle.style.boxShadow = `0 0 8px ${bgColor}`;
                    circle.textContent = day.daily_score;
                    circle.onclick = (e) => { e.stopPropagation(); showTooltip(circle, day); };
                    col.appendChild(circle);
                }
                graphContainer.appendChild(col);

                const label = document.createElement('div');
                label.className = 'text-center w-full';

                if (days === 7) {
                    const dayNames = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];
                    label.textContent = dayNames[new Date(day.date).getDay()];
                } else {
                    const maxLabels = 5;
                    const interval = Math.max(1, Math.floor(sortedData.length / (maxLabels -1)));
                    if (index === 0 || index === sortedData.length - 1 || (index > 0 && index < sortedData.length -1 && index % interval === 0)) {
                        label.textContent = new Date(day.date).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
                    }
                }
                labelsContainer.appendChild(label);
            });
        } catch (e) { console.error("Ошибка графика:", e); }
    }

    // --- Инициализация ---
    if (cancelAnalysisBtn) cancelAnalysisBtn.addEventListener('click', resetWizard);
    document.addEventListener('click', (e) => { if (scoreTooltip && !scoreTooltip.contains(e.target) && !e.target.closest('.score-circle')) hideTooltip(); });

    const sevenDaysBtn = document.getElementById('seven-days-btn');
    const oneMonthBtn = document.getElementById('one-month-btn');
    const threeMonthsBtn = document.getElementById('three-months-btn');

    if (sevenDaysBtn && oneMonthBtn && threeMonthsBtn) {
        const buttons = [sevenDaysBtn, oneMonthBtn, threeMonthsBtn];
        const updateBtns = (activeIndex) => {
            buttons.forEach((btn, index) => {
                if (index === activeIndex) {
                    btn.classList.add('active');
                    btn.classList.remove('text-gray-400');
                } else {
                    btn.classList.remove('active');
                    btn.classList.add('text-gray-400');
                }
            });
        };

        sevenDaysBtn.onclick = () => { updateBtns(0); fetchScoreGraphData(7); };
        oneMonthBtn.onclick = () => { updateBtns(1); fetchScoreGraphData(30); };
        threeMonthsBtn.onclick = () => { updateBtns(2); fetchScoreGraphData(90); };
    }

    // --- Первоначальная загрузка данных ---
    fetchAndDisplayAverageStats();
    fetchAndDisplayMealHistory();
    fetchScoreGraphData(7); // Загружаем 7 дней по умолчанию
    if (sevenDaysBtn) {
        sevenDaysBtn.classList.add('active');
        sevenDaysBtn.classList.remove('text-gray-400');
    }
    resetWizard();
});