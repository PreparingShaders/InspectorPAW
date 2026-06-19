document.addEventListener('DOMContentLoaded', async () => {
    // --- Элементы UI ---
    const mealImageInput = document.getElementById('meal-image');
    const mealDescriptionInput = document.getElementById('meal-description');
    const sendToAiBtn = document.getElementById('send-to-ai-btn');
    const initialView = document.getElementById('initial-view');
    const imageAddedView = document.getElementById('image-added-view');
    const imagePreview = document.getElementById('image-preview');

    const mealLogsContainer = document.getElementById('meal-logs-container');
    const aiCoachTitle = document.getElementById('ai-coach-title');
    const aiCoachAdvice = document.getElementById('ai-coach-advice');
    const errorMessageDiv = document.getElementById('error-message');
    const confirmForm = document.getElementById('confirm-form');
    const cancelAnalysisBtn = document.getElementById('cancel-analysis-btn');
    const interactiveRingsContainer = document.getElementById('interactive-rings-container');
    const mealTypeSelect = document.getElementById('meal-type');

    // --- Элементы модального окна ---
    const modalOverlay = document.getElementById('edit-modal-overlay');
    const modalTitle = document.getElementById('modal-title');
    const modalInput = document.getElementById('modal-input');
    const modalError = document.getElementById('modal-error');
    const modalConfirmBtn = document.getElementById('modal-confirm-btn');
    const modalCancelBtn = document.getElementById('modal-cancel-btn');

    // --- Элементы Tooltip ---
    const scoreTooltip = document.getElementById('score-tooltip');
    const ringTooltip = document.getElementById('ring-tooltip');
    let tooltipTimeout;
    let ringTooltipTimeout;

    let currentFoodName = '';
    let compressedFile = null;
    let nutrientValues = {}; // Хранилище для текущих значений КБЖУ
    let initialNutrientValues = {}; // Хранилище для исходных значений от AI
    let currentFoodQuality = null; // Хранилище для данных о качестве еды

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
                                const newFile = new File([blob], file.name, { type: 'image/jpeg', lastModified: Date.now() });
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
        mealTypeSelect.value = '';
        confirmForm.reset();
        compressedFile = null;
        currentFoodQuality = null;
        if (imagePreview) imagePreview.src = '';
        interactiveRingsContainer.innerHTML = ''; // Очищаем кольца
        showInitialView();
        goToStep(1);
    }

    // --- Логика анализа ---
    mealImageInput.addEventListener('change', async () => {
        if (!mealImageInput.files || mealImageInput.files.length === 0) return;
        try {
            const originalFile = mealImageInput.files[0];
            compressedFile = await compressImage(originalFile);
            console.log(`Изображение сжато с ${Math.round(originalFile.size / 1024)}KB до ${Math.round(compressedFile.size / 1024)}KB`);
            if (imagePreview && compressedFile) {
                const reader = new FileReader();
                reader.onload = (e) => { imagePreview.src = e.target.result; };
                reader.readAsDataURL(compressedFile);
            }
            showImageAddedView();
        } catch (error) {
            console.error('Ошибка сжатия изображения:', error);
            alert('Не удалось обработать изображение. Попробуйте другое.');
            resetWizard();
        }
    });

    sendToAiBtn.addEventListener('click', async () => {
        if (!compressedFile) {
            alert('Сначала выберите фото.');
            return;
        }
        const mealType = mealTypeSelect.value;
        if (!mealType) {
            mealTypeSelect.classList.add('border-red-500', 'ring-2', 'ring-red-500', 'shake');
            setTimeout(() => mealTypeSelect.classList.remove('shake'), 820);
            return;
        }

        goToStep(2);
        const formData = new FormData();
        formData.append('file', compressedFile, compressedFile.name);
        formData.append('meal_type', mealType);
        if (mealDescriptionInput.value.trim()) formData.append('description', mealDescriptionInput.value.trim());
        const aiModel = localStorage.getItem('aiHubCurrentModel');
        if (aiModel) formData.append('ai_model', aiModel);

        try {
            const res = await fetchWithAuth('/analyze-meal/', { method: 'POST', body: formData });
            if (!res.ok) {
                const errorData = await res.json();
                throw new Error(errorData.detail || 'Ошибка анализа');
            }
            const result = await res.json();

            const foodName = result.ai_response_text || 'Прием пищи';
            const coachAdvice = result.ai_coach_advice || 'Приятного аппетита!';

            currentFoodQuality = result.food_quality; // Сохраняем данные о качестве
            const toxicComment = currentFoodQuality ? currentFoodQuality.toxic_coach_comment : '';

            aiCoachTitle.textContent = `Совет от AI (${result.coach_model_used || 'Vision'})`;
            aiCoachAdvice.innerHTML = `Блюдо: ${foodName}<br><br>${toxicComment}`;
            currentFoodName = foodName;

            initialNutrientValues = {
                calories: Math.round(result.suggested_totals.total_calories || 0),
                protein: Math.round(result.suggested_totals.total_protein || 0),
                fat: Math.round(result.suggested_totals.total_fat || 0),
                carbohydrates: Math.round(result.suggested_totals.total_carbohydrates || 0)
            };
            // Копируем начальные значения в редактируемые
            nutrientValues = { ...initialNutrientValues };

            renderInteractiveRings();
            goToStep(3);

        } catch (err) {
            console.error(err);
            errorMessageDiv.textContent = err.message;
            goToStep(1); // Возвращаем на первый шаг в случае ошибки
            setTimeout(() => {
                errorMessageDiv.textContent = "";
                resetWizard();
            }, 3000);
        }
    });

    // --- Логика кастомного модального окна ---
    function showEditModal(nutrientKey, config) {
        const initialValue = initialNutrientValues[nutrientKey];
        let lowerBound, upperBound;

        if (initialValue === 0) {
            lowerBound = 0;
            upperBound = 20;
        } else {
            lowerBound = Math.round(initialValue * 0.5);
            upperBound = Math.round(initialValue * 1.5);
        }

        modalTitle.textContent = `Изменить ${config.label}`;
        modalInput.value = nutrientValues[nutrientKey];
        modalError.textContent = '';
        modalOverlay.classList.add('visible');
        modalInput.focus();

        const handleConfirm = () => {
            const newValueStr = modalInput.value;
            const newValue = parseInt(newValueStr, 10);

            if (isNaN(newValue) || newValue < lowerBound || newValue > upperBound) {
                modalError.textContent = `Введите число от ${lowerBound} до ${upperBound}.`;
                modalInput.classList.add('shake');
                setTimeout(() => modalInput.classList.remove('shake'), 820);
                return;
            }

            nutrientValues[nutrientKey] = newValue;
            if (nutrientKey !== 'calories') {
                recalculateCalories();
            }
            renderInteractiveRings(); // Перерисовываем кольца с новыми значениями
            hideEditModal();
        };

        const handleCancel = () => {
            hideEditModal();
        };

        const hideEditModal = () => {
            modalOverlay.classList.remove('visible');
            modalConfirmBtn.removeEventListener('click', handleConfirm);
            modalCancelBtn.removeEventListener('click', handleCancel);
            modalInput.removeEventListener('keydown', handleEnter);
        };

        const handleEnter = (e) => {
            if (e.key === 'Enter') {
                handleConfirm();
            }
        };

        modalConfirmBtn.addEventListener('click', handleConfirm);
        modalCancelBtn.addEventListener('click', handleCancel);
        modalInput.addEventListener('keydown', handleEnter);
    }

    // --- Рендеринг и интерактивность составного кольца КБЖУ ---
    function renderInteractiveRings() {
        interactiveRingsContainer.innerHTML = '';

        const svgNS = "http://www.w3.org/2000/svg";
        const svg = document.createElementNS(svgNS, "svg");
        const viewBoxSize = 280; // Оставляем увеличенный размер для лейблов
        svg.setAttribute("viewBox", `0 0 ${viewBoxSize} ${viewBoxSize}`);
        svg.style.overflow = 'visible';

        const defs = document.createElementNS(svgNS, "defs");
        const filter = document.createElementNS(svgNS, "filter");
        filter.setAttribute("id", "drop-shadow");
        filter.innerHTML = `<feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="#000000" flood-opacity="0.3"/>`;
        defs.appendChild(filter);
        svg.appendChild(defs);

        const center = viewBoxSize / 2;
        const radius = 85; // Уменьшаем радиус
        const strokeWidth = 22; // Уменьшаем толщину
        const circumference = 2 * Math.PI * radius;
        const gapDegrees = 4;

        const nutrientConfig = {
            protein: { label: 'Белки', color: 'var(--color-protein-white)' },
            fat: { label: 'Жиры', color: 'var(--color-golden-orange)' },
            carbohydrates: { label: 'Углеводы', color: 'var(--color-muted-teal)' }
        };

        const { protein, fat, carbohydrates, calories } = nutrientValues;
        const totalGrams = protein + fat + carbohydrates;

        if (totalGrams === 0) {
            // Отрисовка плейсхолдера
            return;
        }

        let currentAngle = 0;
        const segmentsData = [];
        const drawOrder = ['protein', 'fat', 'carbohydrates'];

        drawOrder.forEach(key => {
            const value = nutrientValues[key];
            if (value > 0) {
                const percentage = value / totalGrams;
                const angle = percentage * 360;
                segmentsData.push({ key, angle, ...nutrientConfig[key] });
            }
        });

        const totalGaps = segmentsData.length * gapDegrees;
        const scaleFactor = (360 - totalGaps) / 360;

        const segmentElements = segmentsData.map(item => {
            const angle = item.angle * scaleFactor;
            const arcLength = (circumference / 360) * angle;

            const segment = document.createElementNS(svgNS, "circle");
            segment.setAttribute("cx", center);
            segment.setAttribute("cy", center);
            segment.setAttribute("r", radius);
            segment.setAttribute("stroke", item.color);
            segment.setAttribute("stroke-width", strokeWidth);
            segment.setAttribute("stroke-dasharray", `${arcLength} ${circumference}`);
            segment.setAttribute("stroke-linecap", "round"); // Закругленные концы
            segment.setAttribute("fill", "none");
            segment.setAttribute("filter", "url(#drop-shadow)");
            segment.style.transformOrigin = 'center';
            segment.style.transform = `rotate(${currentAngle - 90 + gapDegrees / 2}deg)`; // Добавляем половину гэпа для центрирования

            item.startAngle = currentAngle;
            item.endAngle = currentAngle + angle;

            currentAngle += angle + gapDegrees;
            return segment;
        });

        const labelsGroup = document.createElementNS(svgNS, "g");
        segmentsData.forEach(item => {
            const midAngleRad = (item.startAngle + (item.endAngle - item.startAngle) / 2 - 90) * Math.PI / 180;
            const labelRadius = radius + strokeWidth + 10; // Увеличиваем радиус для лейблов
            const x = center + labelRadius * Math.cos(midAngleRad);
            const y = center + labelRadius * Math.sin(midAngleRad);

            const label = document.createElementNS(svgNS, "text");
            label.setAttribute("x", x);
            label.setAttribute("y", y);
            label.setAttribute("text-anchor", "middle");
            label.setAttribute("dominant-baseline", "middle");
            label.setAttribute("fill", item.color);
            label.style.fontSize = '14px';
            label.style.fontWeight = 'bold';
            label.innerHTML = `<tspan x="${x}" dy="-0.6em">${item.label}</tspan><tspan x="${x}" dy="1.2em" style="font-size: 12px; fill: var(--text-secondary);">${nutrientValues[item.key]}г</tspan>`;
            labelsGroup.appendChild(label);
        });

        segmentElements.forEach(el => svg.appendChild(el));
        svg.appendChild(labelsGroup);

        const centerText = document.createElementNS(svgNS, "text");
        centerText.setAttribute("x", "50%");
        centerText.setAttribute("y", "50%");
        centerText.setAttribute("text-anchor", "middle");
        centerText.setAttribute("dominant-baseline", "central");
        centerText.setAttribute("fill", "var(--color-amber)");
        centerText.style.fontSize = '32px';
        centerText.style.fontWeight = 'bold';
        centerText.innerHTML = `<tspan x="50%" dy="-0.1em">${calories}</tspan><tspan x="50%" dy="1.2em" style="font-size: 14px; fill: var(--text-secondary);">Ккал</tspan>`;
        svg.appendChild(centerText);

        svg.addEventListener('click', (event) => {
            const rect = svg.getBoundingClientRect();
            const clickX = (event.clientX - rect.left) * (viewBoxSize / rect.width);
            const clickY = (event.clientY - rect.top) * (viewBoxSize / rect.height);

            const dx = clickX - center;
            const dy = clickY - center;

            let clickAngle = (Math.atan2(dy, dx) * 180 / Math.PI + 90 + 360) % 360;

            const clickedSegment = segmentsData.find(item => {
                const start = item.startAngle;
                const end = item.endAngle + gapDegrees; // Учитываем гэп
                return clickAngle >= start && clickAngle < end;
            });

            if (clickedSegment) {
                showEditModal(clickedSegment.key, clickedSegment);
            } else if (Math.sqrt(dx*dx + dy*dy) < (radius - strokeWidth / 2)) {
                showEditModal('calories', { label: 'Ккал' });
            }
        });

        interactiveRingsContainer.appendChild(svg);
    }


    function recalculateCalories() {
        const { protein, fat, carbohydrates } = nutrientValues;
        nutrientValues.calories = Math.round((protein * 4) + (fat * 9) + (carbohydrates * 4));
    }

    // --- Сохранение результата ---
    confirmForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const mealType = mealTypeSelect.value;
        if (!mealType) {
            alert("Пожалуйста, выберите тип приема пищи.");
            return;
        }

        const mealData = {
            meal_type: mealType,
            food_name: currentFoodName,
            total_calories: nutrientValues.calories,
            total_protein: nutrientValues.protein,
            total_fat: nutrientValues.fat,
            total_carbohydrates: nutrientValues.carbohydrates,
            ai_comment: currentFoodQuality ? currentFoodQuality.toxic_coach_comment : null,
            ai_score: currentFoodQuality ? currentFoodQuality.ai_score : null,
            processing_level: currentFoodQuality ? currentFoodQuality.processing_level : null,
            satiety_index: currentFoodQuality ? currentFoodQuality.satiety_index : null,
            micronutrient_density: currentFoodQuality ? currentFoodQuality.micronutrient_density : null,
        };

        try {
            await fetchWithAuth('/meals/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(mealData)
            });
            resetWizard();
            location.reload();
        } catch (err) {
            alert("Ошибка при сохранении: " + err.message);
        }
    });

    mealTypeSelect.addEventListener('change', () => {
        if (mealTypeSelect.value) {
            mealTypeSelect.classList.remove('border-red-500', 'ring-2', 'ring-red-500');
        }
    });

    // --- Логика Tooltip'ов ---
    function showRingTooltip(element, title, content, color) {
        if (!ringTooltip) return;
        clearTimeout(ringTooltipTimeout);

        const titleEl = document.getElementById('ring-tooltip-title');
        const contentEl = document.getElementById('ring-tooltip-content');

        titleEl.textContent = title;
        titleEl.style.color = color;
        contentEl.innerHTML = content;
        ringTooltip.style.boxShadow = `0 0 15px ${color}`;
        ringTooltip.style.border = `1px solid ${color}`;

        const rect = element.getBoundingClientRect();
        ringTooltip.classList.remove('opacity-0', 'pointer-events-none');
        ringTooltip.classList.add('opacity-100');
        ringTooltip.style.transform = 'scale(1)';

        let top = rect.top + window.scrollY - ringTooltip.offsetHeight - 15;
        let left = rect.left + window.scrollX + (rect.width / 2) - (ringTooltip.offsetWidth / 2);

        if (top < window.scrollY + 10) {
            top = rect.bottom + window.scrollY + 15;
        }
        left = Math.max(10, Math.min(left, window.innerWidth - ringTooltip.offsetWidth - 10));

        ringTooltip.style.top = `${top}px`;
        ringTooltip.style.left = `${left}px`;

        ringTooltipTimeout = setTimeout(hideRingTooltip, 4000);
    }

    function hideRingTooltip() {
        if (!ringTooltip) return;
        ringTooltip.classList.replace('opacity-100', 'opacity-0');
        ringTooltip.classList.add('pointer-events-none');
        ringTooltip.style.transform = 'scale(0.9)';
    }

    // --- ОБНОВЛЕНИЕ БЛОКА СОВЕТОВ ---
    function updateCoachRecommendations(summary) {
        const nutrientStatuses = summary?.nutrient_statuses;
        const tooltips = summary?.pace_recommendation?.tooltips;

        // Обновляем общий совет
        const generalAdviceEl = document.getElementById('coach-general-advice');
        if (tooltips?.daily_score) {
            generalAdviceEl.innerHTML = tooltips.daily_score;
        } else {
            generalAdviceEl.textContent = 'Нет данных для анализа.';
        }

        if (!nutrientStatuses || !tooltips) {
            // Скрываем или очищаем карточки нутриентов, если нет данных
            return;
        }

        const statusOrder = { 'CRITICAL_LIMIT': 1, 'WARNING': 2, 'OK': 3 };
        const nutrientGrid = document.getElementById('coach-nutrient-grid');
        const cards = Array.from(nutrientGrid.children);

        cards.forEach(card => {
            const nutrient = card.dataset.nutrient;
            const status = nutrientStatuses[nutrient] || 'OK';
            const adviceEl = card.querySelector('p');

            // Обновляем текст
            adviceEl.innerHTML = tooltips[nutrient] || 'Нет данных.';

            // Обновляем подсветку
            card.classList.remove('status-danger', 'status-warning');
            if (status === 'CRITICAL_LIMIT') {
                card.classList.add('status-danger');
            } else if (status === 'WARNING') {
                card.classList.add('status-warning');
            }

            // Сохраняем порядок для сортировки
            card.dataset.order = statusOrder[status] || 3;
        });

        // Сортируем и вставляем обратно
        cards.sort((a, b) => a.dataset.order - b.dataset.order);
        cards.forEach(card => nutrientGrid.appendChild(card));
    }


    // --- Новая функция для обновления колец со статусами ---
    function updateRingWithStatus(ringSvgElement, value, maxValue, nutrient = null) {
        if (!ringSvgElement) return;
        const bar = ringSvgElement.querySelector('.progress-ring-bar');
        if (!bar) return;

        // 1. Обновление длины полосы
        const radius = bar.r.baseVal.value;
        const circum = 2 * Math.PI * radius;
        bar.style.strokeDasharray = `${circum} ${circum}`;
        const pct = maxValue > 0 ? value / maxValue : 0;
        const displayPct = Math.min(pct, 1);
        bar.style.strokeDashoffset = circum - (displayPct * circum);

        // 2. Логика статусов и цветов
        bar.classList.remove('status-warning', 'status-danger', 'status-success');

        if (pct > 1.05) {
            if (nutrient === 'protein') {
                bar.classList.add('status-success');
            } else {
                bar.classList.add('status-danger');
            }
        } else if (pct > 0.95) {
            if (nutrient !== 'protein') {
                bar.classList.add('status-warning');
            }
        }
    }


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

    const nutrientLabels = {
        calories: 'Ккал',
        protein: 'Б',
        fat: 'Ж',
        carbs: 'У'
    };

    async function fetchAndDisplayMealHistory(targets) {
        try {
            const res = await fetchWithAuth('/meals/');
            let meals = await res.json();
            mealLogsContainer.innerHTML = '';
            const trans = { breakfast: 'Завтрак', lunch: 'Обед', dinner: 'Ужин', snack: 'Перекус' };

            meals.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

            let lastDate = null;

            meals.forEach(m => {
                const mealTimestamp = new Date(m.timestamp);
                const mealDateString = mealTimestamp.toISOString().split('T')[0];

                if (mealDateString !== lastDate) {
                    const dateHeader = document.createElement('h3');
                    dateHeader.className = 'text-lg font-bold text-center mt-6 mb-3 text-white';
                    dateHeader.textContent = formatDateForLogs(m.timestamp);
                    mealLogsContainer.appendChild(dateHeader);

                    if (lastDate !== null) {
                        const separator = document.createElement('div');
                        separator.className = 'border-t border-white/10 my-4';
                        mealLogsContainer.appendChild(separator);
                    }
                    lastDate = mealDateString;
                }

                const card = document.createElement('div');
                card.className = 'glassmorphism rounded-xl p-4 mb-4';
                card.innerHTML = `
                    <div class="flex justify-between items-center mb-3">
                        <h4 class="font-bold text-lg">${trans[m.meal_type]}</h4>
                        <span class="text-sm text-gray-400">${m.formatted_time}</span>
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

                ['calories', 'protein', 'fat', 'carbs'].forEach(type => {
                    const nutrientKey = type === 'carbs' ? 'carbohydrates' : type;
                    const ringSvgElement = card.querySelector(`#log-${m.id}-${type}-ring`);
                    if (ringSvgElement) {
                        updateRingWithStatus(ringSvgElement, m[`total_${nutrientKey}`], targets[`target_${nutrientKey}`], nutrientKey);
                    }
                });
            });
        } catch (e) { console.error("Ошибка истории:", e); }
    }

    function createMiniRing(id, type, val, target, color) {
        const label = nutrientLabels[type];
        const nutrientKey = type === 'carbs' ? 'carbohydrates' : type;
        return `<div class="text-center flex flex-col items-center">
                    <div class="ring-container w-10 h-10 relative">
                        <svg id="log-${id}-${type}-ring" class="progress-ring-svg" viewBox="0 0 120 120">
                            <circle class="progress-ring-bg" cx="60" cy="60" r="54"/>
                            <circle data-nutrient="${nutrientKey}" class="progress-ring-bar" cx="60" cy="60" r="54" style="stroke: var(--color-${color});"/>
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

    function isLightColor(color) {
        if (!color) return false;
        let r, g, b;
        if (color.startsWith('#')) {
            const hex = color.slice(1);
            r = parseInt(hex.substring(0, 2), 16);
            g = parseInt(hex.substring(2, 4), 16);
            b = parseInt(hex.substring(4, 6), 16);
        } else {
            return false;
        }
        const brightness = (r * 299 + g * 587 + b * 114) / 1000;
        return brightness > 155;
    }

    async function fetchScoreGraphData(days) {
        try {
            const res = await fetchWithAuth(`/users/me/stats/summary-by-period?days=${days}`);
            const data = await res.json();

            // Обновляем средние показатели
            const s = data.period_summary;
            updateRingWithStatus(document.querySelector('[data-nutrient="calories"]'), s.avg_calories, s.target_calories, 'calories');
            updateRingWithStatus(document.querySelector('[data-nutrient="protein"]'), s.avg_protein, s.target_protein, 'protein');
            updateRingWithStatus(document.querySelector('[data-nutrient="fat"]'), s.avg_fat, s.target_fat, 'fat');
            updateRingWithStatus(document.querySelector('[data-nutrient="carbohydrates"]'), s.avg_carbohydrates, s.target_carbohydrates, 'carbohydrates');

            document.getElementById('avg-calories-value').textContent = Math.round(s.avg_calories);
            document.getElementById('avg-protein-value').textContent = Math.round(s.avg_protein);
            document.getElementById('avg-fat-value').textContent = Math.round(s.avg_fat);
            document.getElementById('avg-carbs-value').textContent = Math.round(s.avg_carbohydrates);

            // Передаем цели в историю приемов пищи
            fetchAndDisplayMealHistory(s);

            const scores = data.daily_breakdown.map(d => d.daily_score).filter(s => s !== null && s !== undefined);
            const avgScoreValue = document.getElementById('avg-score-value');
            const avgScoreBar = document.getElementById('avg-score-bar');
            const avgScoreRingContainer = document.getElementById('avg-score-ring-container');

            if (scores.length > 0) {
                const averageScore = Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);
                avgScoreValue.textContent = averageScore;
                updateRingWithStatus(document.getElementById('avg-score-ring'), averageScore, 120);

                let scoreColor = '#e11d48'; // red
                if (averageScore > 105) scoreColor = '#FFD700'; // gold
                else if (averageScore >= 95) scoreColor = '#F0F0F0'; // white
                else if (averageScore >= 80) scoreColor = '#f59e0b'; // amber

                avgScoreValue.style.color = scoreColor;
                avgScoreBar.style.stroke = scoreColor;
                avgScoreRingContainer.style.boxShadow = `0 0 8px 1px ${scoreColor}`;

            } else {
                avgScoreValue.textContent = '0';
                updateRingWithStatus(document.getElementById('avg-score-ring'), 0, 120);
                avgScoreValue.style.color = '#A0A0A0';
                avgScoreBar.style.stroke = '#A0A0A0';
                avgScoreRingContainer.style.boxShadow = 'none';
            }

            // Обновляем новый блок советов
            updateCoachRecommendations(data.progress_lab_summary);

            const averageStatsContainer = document.getElementById('average-stats');
            const graphWrapper = document.getElementById('graph-wrapper');
            const labelsContainer = document.getElementById('x-axis-labels-container');
            const graphContainer = document.getElementById('score-graph-container');
            graphContainer.innerHTML = '';
            labelsContainer.innerHTML = '';

            // Обновление меток КБЖУ
            const caloriesLabel = document.getElementById('avg-calories-label');
            const proteinLabel = document.getElementById('avg-protein-label');
            const fatLabel = document.getElementById('avg-fat-label');
            const carbsLabel = document.getElementById('avg-carbs-label');

            if (days === 1) {
                graphWrapper.classList.add('opacity-0', 'h-0');
                labelsContainer.classList.add('opacity-0', 'h-0');
                averageStatsContainer.classList.add('flex-grow', 'flex', 'items-center', 'justify-center', 'day-view-active');

                caloriesLabel.textContent = 'Калории';
                proteinLabel.textContent = 'Белки';
                fatLabel.textContent = 'Жиры';
                carbsLabel.textContent = 'Углеводы';

            } else {
                graphWrapper.classList.remove('opacity-0', 'h-0');
                labelsContainer.classList.remove('opacity-0', 'h-0');
                averageStatsContainer.classList.remove('flex-grow', 'flex', 'items-center', 'justify-center', 'day-view-active');

                caloriesLabel.textContent = 'Ккал';
                proteinLabel.textContent = 'Б';
                fatLabel.textContent = 'Ж';
                carbsLabel.textContent = 'У';
            }

            const sortedData = data.daily_breakdown.sort((a, b) => new Date(a.date) - new Date(b.date));

            sortedData.forEach((day, index) => {
                const colWrapper = document.createElement('div');
                colWrapper.className = 'flex-1 h-full flex flex-col justify-end items-center';

                if (day.daily_score !== null) {
                    const barHeight = (day.daily_score / 120) * 100;
                    const bar = document.createElement('div');
                    const bgColor = day.status_color || '#F0F0F0';

                    bar.className = 'w-1/2 rounded-t-md cursor-pointer';
                    bar.style.height = `${barHeight}%`;
                    bar.style.backgroundColor = bgColor;
                    bar.style.boxShadow = `0 0 8px ${bgColor}`;
                    bar.onclick = (e) => { e.stopPropagation(); showTooltip(bar, day); };
                    colWrapper.appendChild(bar);
                }
                graphContainer.appendChild(colWrapper);

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
    document.addEventListener('click', (e) => {
        if (scoreTooltip && !scoreTooltip.contains(e.target) && !e.target.closest('.score-circle')) {
            hideTooltip();
        }
        if (ringTooltip && !ringTooltip.contains(e.target) && !e.target.closest('.ring-container')) {
            hideRingTooltip();
        }
    });

    const oneDayBtn = document.getElementById('one-day-btn');
    const sevenDaysBtn = document.getElementById('seven-days-btn');
    const oneMonthBtn = document.getElementById('one-month-btn');
    const threeMonthsBtn = document.getElementById('three-months-btn');

    if (oneDayBtn && sevenDaysBtn && oneMonthBtn && threeMonthsBtn) {
        const buttons = [oneDayBtn, sevenDaysBtn, oneMonthBtn, threeMonthsBtn];
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

        oneDayBtn.onclick = () => { updateBtns(0); fetchScoreGraphData(1); };
        sevenDaysBtn.onclick = () => { updateBtns(1); fetchScoreGraphData(7); };
        oneMonthBtn.onclick = () => { updateBtns(2); fetchScoreGraphData(30); };
        threeMonthsBtn.onclick = () => { updateBtns(3); fetchScoreGraphData(90); };
    }

    const avgScoreWrapper = document.getElementById('avg-score-wrapper');
    if (avgScoreWrapper) {
        avgScoreWrapper.addEventListener('click', () => {
            const scoreTooltipText = "Оценка показывает, насколько равномерно вы идете к цели в течение дня. Переборы по калориям, жирам и углеводам срезают баллы, а вот выполнение нормы по белку — наоборот, поощряется бонусами. Чтобы набрать максимум, старайтесь избегать резких скачков и питайтесь равномерно в течении дня. Максимум 120 баллов.";
            const scoreColor = document.getElementById('avg-score-value').style.color || '#F0F0F0';
            showRingTooltip(avgScoreWrapper, 'Daily Score', scoreTooltipText, scoreColor);
        });
    }

    // --- Первоначальная загрузка данных ---
    fetchScoreGraphData(1); // Загружаем 1 день по умолчанию
    if (oneDayBtn) {
        oneDayBtn.classList.add('active');
        oneDayBtn.classList.remove('text-gray-400');
    }
    resetWizard();
});