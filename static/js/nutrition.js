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
    let nutrientValues = {};
    let initialNutrientValues = {};
    let currentFoodQuality = null;
    let currentMealAnalysis = null;
    let currentAiScore = null;
    let ringDisplayMode = 'progress';

    // --- Слайдер приёмов пищи ---
    let dailyMeals = [];
    let dailyTotal = null;
    let currentMealIndex = -1;
    let isTotalView = false;

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
                            if (blob && blob.size > 500) {
                                const newFile = new File(
                                    [blob],
                                    `meal_${Date.now()}.jpg`,
                                    { type: 'image/jpeg', lastModified: Date.now() }
                                );
                                resolve(newFile);
                            } else {
                                reject(new Error('Canvas to Blob conversion failed or image is empty'));
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
        console.log('goToStep called with:', stepNumber);
        Object.values(steps).forEach(step => {
            if (step) {
                step.classList.remove('active');
                step.classList.add('hidden');
            }
        });
        if (steps[stepNumber]) {
            steps[stepNumber].classList.remove('hidden');
            steps[stepNumber].classList.add('active');
            console.log('Step', stepNumber, 'is now active');
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
        currentMealAnalysis = null;
        currentAiScore = null;
        nutrientValues = {};
        initialNutrientValues = {};
        if (imagePreview) imagePreview.src = '';
        interactiveRingsContainer.innerHTML = '';
        const qualityDetails = document.getElementById('quality-details');
        if (qualityDetails) qualityDetails.style.display = 'none';
        showInitialView();
        goToStep(1);
    }

    // --- Логика анализа ---
    const uploadLabel = document.querySelector('label[for="meal-image"]');
    if (uploadLabel) {
        uploadLabel.addEventListener('click', () => {
            mealImageInput.value = '';
        });
    }

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
        currentFoodQuality = null;
        currentMealAnalysis = null;
        nutrientValues = {};
        initialNutrientValues = {};

        const formData = new FormData();
        formData.append('file', compressedFile, compressedFile.name);
        formData.append('meal_type', mealType);
        if (mealDescriptionInput.value.trim()) formData.append('description', mealDescriptionInput.value.trim());
        const aiModel = localStorage.getItem('aiHubCurrentModel');
        if (aiModel) formData.append('ai_model', aiModel);

        try {
            const res = await fetchWithAuth('/analyze-meal/', { method: 'POST', body: formData, cache: 'no-store' });
            console.log('Response status:', res.status);
            if (!res.ok) {
                const errorData = await res.json();
                console.error('Error response:', errorData);
                throw new Error(errorData.detail || 'Ошибка анализа');
            }
            const result = await res.json();
            console.log('Analysis result:', result);

            const foodName = result.ai_response_text || 'Прием пищи';
            const coachAdvice = result.ai_coach_advice || 'Приятного аппетита!';

            currentFoodQuality = result.food_quality;
            currentMealAnalysis = {
                total_fiber: result.suggested_totals?.total_fiber || 0,
                ai_analysis_details: result.ai_analysis_details || null,
            };
            currentAiScore = result.food_quality?.ai_score ?? null;
            const toxicComment = currentFoodQuality ? currentFoodQuality.toxic_coach_comment : '';

            aiCoachTitle.textContent = `Совет от AI (${result.coach_model_used || 'Vision'})`;
            const step3Label = document.getElementById('step-3-daily-quality-label');
            if (step3Label) step3Label.textContent = `Блюдо: ${foodName}`;
            aiCoachAdvice.innerHTML = toxicComment;
            currentFoodName = foodName;

            initialNutrientValues = {
                calories: Math.round(result.suggested_totals.total_calories || 0),
                protein: Math.round(result.suggested_totals.total_protein || 0),
                fat: Math.round(result.suggested_totals.total_fat || 0),
                carbohydrates: Math.round(result.suggested_totals.total_carbohydrates || 0),
                fiber: Math.round(result.suggested_totals.total_fiber || 0)
            };
            nutrientValues = { ...initialNutrientValues };

            console.log('Rendering rings with values:', nutrientValues);
            console.log('Food quality:', currentFoodQuality);
            console.log('Meal analysis:', currentMealAnalysis);
            
            renderInteractiveRings();
            console.log('Rings rendered, going to step 3');
            goToStep(3);
            console.log('Now at step 3');

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
            if (nutrientKey !== 'calories' && nutrientKey !== 'fiber') {
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
    function createRingGradient(defs, id, light, dark) {
        const grad = document.createElementNS("http://www.w3.org/2000/svg", "linearGradient");
        grad.setAttribute("id", id);
        grad.setAttribute("x1", "20%");
        grad.setAttribute("y1", "0%");
        grad.setAttribute("x2", "80%");
        grad.setAttribute("y2", "100%");
        [{ offset: "0%", color: light }, { offset: "100%", color: dark }].forEach(({ offset, color }) => {
            const stop = document.createElementNS("http://www.w3.org/2000/svg", "stop");
            stop.setAttribute("offset", offset);
            stop.setAttribute("stop-color", color);
            grad.appendChild(stop);
        });
        defs.appendChild(grad);
    }

    function createRingGlowFilter(defs, id, glowColor) {
        const filter = document.createElementNS("http://www.w3.org/2000/svg", "filter");
        filter.setAttribute("id", id);
        filter.setAttribute("x", "-40%");
        filter.setAttribute("y", "-40%");
        filter.setAttribute("width", "180%");
        filter.setAttribute("height", "180%");
        filter.innerHTML = `
            <feDropShadow dx="0" dy="4" stdDeviation="3" flood-color="#000000" flood-opacity="0.5" result="depth"/>
            <feDropShadow dx="0" dy="0" stdDeviation="5" flood-color="${glowColor}" flood-opacity="0.55" result="glow"/>
            <feMerge>
                <feMergeNode in="depth"/>
                <feMergeNode in="glow"/>
                <feMergeNode in="SourceGraphic"/>
            </feMerge>
        `;
        defs.appendChild(filter);
    }

    function renderInteractiveRings() {
        const oldContainer = document.getElementById('interactive-rings-container');
        if (!oldContainer) return;
        const parent = oldContainer.parentNode;
        const container = document.createElement('div');
        container.id = 'interactive-rings-container';
        container.style.cssText = 'width: 260px; height: 260px; margin: 0.5rem auto; position: relative; flex-shrink: 0;';
        parent.replaceChild(container, oldContainer);

        const { protein, fat, carbohydrates, fiber } = nutrientValues;
        const score = currentAiScore || 0;
        const calories = nutrientValues.calories || 0;

        renderDailyQualityRing({
            protein: protein || 0,
            fat: fat || 0,
            carbohydrates: carbohydrates || 0,
            fiber: fiber || 0,
            _score: score,
            _calories: calories
        }, 1, 'interactive-rings-container');
    }

    function getScoreColor(score) {
        if (score === null || score === undefined) return 'rgba(255,255,255,0.3)';
        if (score <= 40) return '#EF4444';
        if (score <= 70) return '#F59E0B';
        return '#10B981';
    }

    function getScoreLabel(score) {
        if (score === null || score === undefined) return '—';
        if (score <= 40) return 'Плохо';
        if (score <= 70) return 'Средне';
        return 'Отлично';
    }

    function renderQualityCards(meal) {
        const container = document.getElementById('quality-cards');
        if (!container) return;
        container.innerHTML = '';

        const cards = [];

        const aas = meal.amino_acid_score;
        const apr = meal.animal_protein_ratio;
        if (aas !== null || apr !== null) {
            let hint = '';
            if (aas !== null) {
                if (aas >= 90) hint = 'Полный аминокислотный профиль';
                else if (aas >= 60) hint = 'Хороший профиль';
                else hint = 'Нехватает незаменимых аминокислот';
            }
            if (apr !== null) {
                hint += hint ? '. ' : '';
                if (apr >= 0.6) hint += 'Преобладает животный белок';
                else if (apr >= 0.4) hint += 'Сбалансированный белок';
                else hint += 'Преобладает растительный белок';
            }
            const badge = aas >= 80 ? 'good' : aas >= 50 ? 'warn' : 'bad';
            cards.push({
                icon: '🥩', iconClass: 'icon-protein',
                title: 'Белки',
                value: aas !== null ? `${Math.round(aas)}/100` : '—',
                hint,
                badge,
                badgeText: aas >= 80 ? 'Хорошо' : aas >= 50 ? 'Средне' : 'Плохо'
            });
        }

        const o63 = meal.omega6_omega3_ratio;
        const tfr = meal.trans_fat_ratio;
        if (o63 !== null || tfr !== null) {
            let hint = '';
            if (o63 !== null) {
                if (o63 <= 4) hint = 'Идеальный баланс Омега-6/3';
                else if (o63 <= 10) hint = 'Приемлемый баланс';
                else hint = 'Слишком много Омега-6 — воспаление';
            }
            if (tfr !== null) {
                hint += hint ? '. ' : '';
                if (tfr <= 0.01) hint = 'Безопасный уровень трансжиров';
                else if (tfr <= 0.03) hint = 'Немного трансжиров';
                else hint = 'Много трансжиров!';
            }
            const badge = (o63 !== null && o63 <= 4) ? 'good' : (o63 !== null && o63 <= 10) ? 'warn' : 'bad';
            cards.push({
                icon: '🫒', iconClass: 'icon-fat',
                title: 'Жиры',
                value: o63 !== null ? `Ω6/3: ${o63.toFixed(1)}` : '—',
                hint,
                badge,
                badgeText: o63 <= 4 ? 'Хорошо' : o63 <= 10 ? 'Средне' : 'Плохо'
            });
        }

        const gl = meal.glycemic_load;
        const fcr = meal.fiber_to_carb_ratio;
        if (gl !== null || fcr !== null) {
            let hint = '';
            if (gl !== null) {
                if (gl <= 10) hint = 'Низкая гликемическая нагрузка';
                else if (gl <= 20) hint = 'Средняя нагрузка';
                else hint = 'Высокая нагрузка — скачок сахара';
            }
            if (fcr !== null) {
                hint += hint ? '. ' : '';
                if (fcr >= 0.15) hint = 'Много клетчатки — хорошо';
                else if (fcr >= 0.08) hint = 'Среднее количество клетчатки';
                else hint = 'Мало клетчатки';
            }
            const badge = (gl !== null && gl <= 10) ? 'good' : (gl !== null && gl <= 20) ? 'warn' : 'bad';
            cards.push({
                icon: '🌾', iconClass: 'icon-carb',
                title: 'Углеводы',
                value: gl !== null ? `GL: ${Math.round(gl)}` : '—',
                hint,
                badge,
                badgeText: gl <= 10 ? 'Хорошо' : gl <= 20 ? 'Средне' : 'Плохо'
            });
        }

        const nova = meal.nova_processing_level;
        if (nova !== null) {
            const novaLabels = ['', 'Цельный', 'Минимальная', 'Обработанный', 'Ультра-обработанный'];
            const badge = nova <= 2 ? 'good' : nova === 3 ? 'warn' : 'bad';
            cards.push({
                icon: '⚙️', iconClass: 'icon-nova',
                title: 'Обработка',
                value: novaLabels[nova] || `NOVA ${nova}`,
                hint: nova <= 2 ? 'Натуральная еда' : nova === 3 ? 'Обработанный продукт' : 'Фастфуд / УПП',
                badge,
                badgeText: nova <= 2 ? 'Хорошо' : nova === 3 ? 'Средне' : 'Плохо'
            });
        }

        const cardCount = cards.length;
        cards.forEach((card, idx) => {
            const el = document.createElement('div');
            el.className = 'quality-card';
            el.innerHTML = `
                <div class="quality-card-main">
                    <div class="quality-card-icon ${card.iconClass}">${card.icon}</div>
                    <div class="quality-card-body">
                        <div class="quality-card-title">${card.title}</div>
                        <div class="quality-card-value">${card.value}</div>
                    </div>
                    <span class="quality-badge badge-${card.badge}">${card.badgeText}</span>
                </div>
                <div class="quality-card-hint">${card.hint}</div>
            `;
            el.addEventListener('click', () => {
                const isActive = el.classList.contains('active');
                container.querySelectorAll('.quality-card').forEach(c => c.classList.remove('active'));
                if (!isActive) el.classList.add('active');
            });
            container.appendChild(el);
        });

        if (cards.length === 0) {
            container.innerHTML = '<p class="text-xs text-center opacity-40 mt-2">Нет данных о качестве. Добавьте приём пищи.</p>';
        }
    }

    function renderMealSliderDots() {
        const container = document.getElementById('meal-slider-dots');
        if (!container) return;
        container.innerHTML = '';

        if (dailyTotal) {
            const totalDot = document.createElement('div');
            totalDot.className = `meal-dot total-dot ${isTotalView ? 'active' : ''}`;
            totalDot.title = 'Итого за день';
            totalDot.addEventListener('click', () => {
                isTotalView = true;
                renderMealView();
            });
            container.appendChild(totalDot);
        }

        // Приёмы в обратном порядке: новый приём ближе к Total, первый — в конце
        for (let idx = dailyMeals.length - 1; idx >= 0; idx--) {
            const meal = dailyMeals[idx];
            const dot = document.createElement('div');
            const isActive = idx === currentMealIndex && !isTotalView;
            dot.className = `meal-dot ${isActive ? 'active' : ''}`;
            dot.title = meal.food_name || `Приём ${idx + 1}`;
            dot.addEventListener('click', () => {
                currentMealIndex = idx;
                isTotalView = false;
                renderMealView();
            });
            container.appendChild(dot);
        }
    }

    function renderMealView() {
        renderMealSliderDots();
        const meal = isTotalView ? dailyTotal : dailyMeals[currentMealIndex];
        if (!meal) {
            renderDailyQualityRing(null, 0);
            renderQualityCards({});
            return;
        }

        const label = document.getElementById('daily-quality-label');
        if (label) {
            const mealDate = meal.timestamp ? new Date(meal.timestamp) : new Date();
            const dateStr = mealDate.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' });
            if (isTotalView) {
                label.textContent = `${dateStr} · Итоги дня`;
                label.className = 'text-center daily-quality-label-total';
            } else {
                const mealTypeNames = {
                    breakfast: 'Завтрак',
                    lunch: 'Обед',
                    dinner: 'Ужин',
                    snack: 'Перекус'
                };
                const typeLabel = mealTypeNames[meal.meal_type] || '';
                const time = meal.formatted_time || '';
                const name = meal.food_name || 'Приём пищи';
                const desc = meal.description || '';

                const parts = [typeLabel, dateStr, name, desc].filter(Boolean);
                if (desc) {
                    const descSpan = document.createElement('span');
                    descSpan.style.color = 'rgba(192, 132, 252, 0.85)';
                    descSpan.style.fontStyle = 'italic';
                    descSpan.style.fontSize = '0.65rem';
                    descSpan.textContent = desc;
                    const mainText = parts.filter(p => p !== desc).join('  ');
                    label.textContent = mainText + '  ';
                    label.appendChild(descSpan);
                } else {
                    label.textContent = parts.join('  ');
                }
                label.className = 'text-center daily-quality-label-meal';
            }
        }

        renderDailyQualityRing({
            protein: meal.total_protein || 0,
            fat: meal.total_fat || 0,
            carbohydrates: meal.total_carbohydrates || 0,
            fiber: meal.total_fiber || 0,
            _score: meal.ai_score || 0,
            _calories: meal.total_calories || 0,
            _quality: {
                protein: meal.amino_acid_score !== null && meal.amino_acid_score !== undefined
                    ? { text: meal.amino_acid_score >= 80 ? 'Хорошо' : meal.amino_acid_score >= 50 ? 'Средне' : 'Плохо', color: meal.amino_acid_score >= 80 ? '#4ADE80' : meal.amino_acid_score >= 50 ? '#FBBF24' : '#F87171' }
                    : null,
                fat: meal.omega6_omega3_ratio !== null && meal.omega6_omega3_ratio !== undefined
                    ? { text: meal.omega6_omega3_ratio <= 4 ? 'Хорошо' : meal.omega6_omega3_ratio <= 10 ? 'Средне' : 'Плохо', color: meal.omega6_omega3_ratio <= 4 ? '#4ADE80' : meal.omega6_omega3_ratio <= 10 ? '#FBBF24' : '#F87171' }
                    : null,
                carbohydrates: meal.glycemic_load !== null && meal.glycemic_load !== undefined
                    ? { text: meal.glycemic_load <= 10 ? 'Хорошо' : meal.glycemic_load <= 20 ? 'Средне' : 'Плохо', color: meal.glycemic_load <= 10 ? '#4ADE80' : meal.glycemic_load <= 20 ? '#FBBF24' : '#F87171' }
                    : null,
                fiber: meal.total_fiber > 0
                    ? { text: 'Есть', color: '#4ADE80' }
                    : null
            }
        }, isTotalView ? (meal.meal_count || 1) : 1);

        renderQualityCards(meal);
    }

    function renderDailyQualityRing(nutrientValues, mealCount, containerId) {
         const targetContainerId = containerId || 'daily-quality-ring';
         const container = document.getElementById(targetContainerId);
         if (!container) return;
         container.innerHTML = '';

        const svgNS = "http://www.w3.org/2000/svg";
        const viewBoxSize = 260;
        const center = viewBoxSize / 2;
        const radius = 78;
        const strokeWidth = 14;
        const circumference = 2 * Math.PI * radius;
        const gapDegrees = 3;

        const svg = document.createElementNS(svgNS, "svg");
        svg.setAttribute("viewBox", `0 0 ${viewBoxSize} ${viewBoxSize}`);
        svg.setAttribute("class", "composite-ring-svg");

        const defs = document.createElementNS(svgNS, "defs");
        createRingGradient(defs, 'dq-grad-protein', '#FFFFFF', '#9CA3AF');
        createRingGradient(defs, 'dq-grad-fat', '#F0D878', '#DAA520');
        createRingGradient(defs, 'dq-grad-carbs', '#86EFAC', '#16A34A');
        createRingGradient(defs, 'dq-grad-fiber', '#D2B48C', '#8B4513');
        createRingGlowFilter(defs, 'dq-glow-protein', '#FFFFFF');
        createRingGlowFilter(defs, 'dq-glow-fat', '#DAA520');
        createRingGlowFilter(defs, 'dq-glow-carbs', '#4ADE80');
        createRingGlowFilter(defs, 'dq-glow-fiber', '#8B4513');
        defs.innerHTML += `<filter id="dq-glow-text" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="1" stdDeviation="1.5" flood-color="#DEB887" flood-opacity="0.45"/></filter>`;
        svg.appendChild(defs);

        const trackRing = document.createElementNS(svgNS, "circle");
        trackRing.setAttribute("cx", center);
        trackRing.setAttribute("cy", center);
        trackRing.setAttribute("r", radius);
        trackRing.setAttribute("stroke", "rgba(255,255,255,0.07)");
        trackRing.setAttribute("stroke-width", strokeWidth + 2);
        trackRing.setAttribute("fill", "none");
        svg.appendChild(trackRing);

        const nutrientConfig = {
            protein: { label: 'Белки', color: '#FFFFFF', gradient: 'url(#dq-grad-protein)', filter: 'url(#dq-glow-protein)' },
            fat: { label: 'Жиры', color: 'var(--color-golden-orange)', gradient: 'url(#dq-grad-fat)', filter: 'url(#dq-glow-fat)' },
            carbohydrates: { label: 'Углеводы', color: '#4ADE80', gradient: 'url(#dq-grad-carbs)', filter: 'url(#dq-glow-carbs)' },
            fiber: { label: 'Клетчатка', color: '#8B4513', gradient: 'url(#dq-grad-fiber)', filter: 'url(#dq-glow-fiber)' }
        };

        const { protein = 0, fat = 0, carbohydrates = 0, fiber = 0 } = nutrientValues || {};
        const totalGrams = protein + fat + carbohydrates + fiber;

        if (totalGrams > 0 && mealCount > 0) {
            let currentAngle = 0;
            const segmentsData = [];
            const drawOrder = ['protein', 'fat', 'carbohydrates', 'fiber'];

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
                const rotation = `${currentAngle - 90 + gapDegrees / 2}deg`;

                const shadow = document.createElementNS(svgNS, "circle");
                shadow.setAttribute("cx", center);
                shadow.setAttribute("cy", center);
                shadow.setAttribute("r", radius);
                shadow.setAttribute("stroke", "rgba(0,0,0,0.35)");
                shadow.setAttribute("stroke-width", strokeWidth + 2);
                shadow.setAttribute("stroke-dasharray", `${arcLength} ${circumference}`);
                shadow.setAttribute("stroke-linecap", "round");
                shadow.setAttribute("fill", "none");
                shadow.style.transformOrigin = 'center';
                shadow.style.transform = `rotate(${rotation}) translateY(2px)`;

                const segment = document.createElementNS(svgNS, "circle");
                segment.setAttribute("cx", center);
                segment.setAttribute("cy", center);
                segment.setAttribute("r", radius);
                segment.setAttribute("stroke", item.gradient);
                segment.setAttribute("stroke-width", strokeWidth);
                segment.setAttribute("stroke-dasharray", `${arcLength} ${circumference}`);
                segment.setAttribute("stroke-linecap", "round");
                segment.setAttribute("fill", "none");
                segment.setAttribute("filter", item.filter);
                segment.style.transformOrigin = 'center';
                segment.style.transform = `rotate(${rotation})`;

                item.startAngle = currentAngle;
                item.endAngle = currentAngle + angle;
                currentAngle += angle + gapDegrees;

                return { shadow, segment };
            });

            const labelOffsets = { protein: 28, fat: 28, carbohydrates: 28, fiber: 28 };
            const labelsGroup = document.createElementNS(svgNS, "g");

            segmentsData.forEach(item => {
                const midAngleRad = (item.startAngle + (item.endAngle - item.startAngle) / 2 - 90) * Math.PI / 180;
                const labelRadius = radius + strokeWidth / 2 + labelOffsets[item.key];
                const x = center + labelRadius * Math.cos(midAngleRad);
                const y = center + labelRadius * Math.sin(midAngleRad);

                const label = document.createElementNS(svgNS, "text");
                label.setAttribute("x", x);
                label.setAttribute("y", y);
                label.setAttribute("text-anchor", "middle");
                label.setAttribute("dominant-baseline", "central");
                label.setAttribute("fill", item.color);
                label.style.fontSize = '12px';
                label.style.fontWeight = 'bold';
                label.textContent = item.label;
                labelsGroup.appendChild(label);

                const valueLabel = document.createElementNS(svgNS, "text");
                valueLabel.setAttribute("x", x);
                valueLabel.setAttribute("y", y + 14);
                valueLabel.setAttribute("text-anchor", "middle");
                valueLabel.setAttribute("dominant-baseline", "central");
                valueLabel.setAttribute("fill", "rgba(255,255,255,0.5)");
                valueLabel.style.fontSize = '12px';
                valueLabel.style.fontWeight = '500';
                valueLabel.textContent = `${Math.round(nutrientValues[item.key])}г`;
                labelsGroup.appendChild(valueLabel);
            });

            segmentElements.forEach(({ shadow, segment }) => {
                svg.appendChild(shadow);
                svg.appendChild(segment);
            });
            svg.appendChild(labelsGroup);
        }

        const score = nutrientValues?._score || 0;
        const scoreColor = getScoreColor(score);
        const scoreLabel = getScoreLabel(score);
        const calories = nutrientValues?._calories || 0;

        const scoreText = document.createElementNS(svgNS, "text");
        scoreText.setAttribute("x", center);
        scoreText.setAttribute("y", center - 28);
        scoreText.setAttribute("text-anchor", "middle");
        scoreText.setAttribute("dominant-baseline", "central");
        scoreText.setAttribute("fill", scoreColor);
        scoreText.style.fontSize = '44px';
        scoreText.style.fontWeight = '900';
        scoreText.textContent = mealCount === 0 ? '—' : Math.round(score);
        svg.appendChild(scoreText);

        const scoreLabelEl = document.createElementNS(svgNS, "text");
        scoreLabelEl.setAttribute("x", center);
        scoreLabelEl.setAttribute("y", center + 10);
        scoreLabelEl.setAttribute("text-anchor", "middle");
        scoreLabelEl.setAttribute("dominant-baseline", "central");
        scoreLabelEl.setAttribute("fill", scoreColor);
        scoreLabelEl.style.fontSize = '13px';
        scoreLabelEl.style.fontWeight = '700';
        scoreLabelEl.textContent = mealCount === 0 ? 'Нет данных' : scoreLabel;
        svg.appendChild(scoreLabelEl);

        const calText = document.createElementNS(svgNS, "text");
        calText.setAttribute("x", center);
        calText.setAttribute("y", center + 28);
        calText.setAttribute("text-anchor", "middle");
        calText.setAttribute("dominant-baseline", "central");
        calText.setAttribute("fill", "rgba(252, 211, 77, 0.7)");
        calText.style.fontSize = '12px';
        calText.style.fontWeight = '600';
        calText.textContent = mealCount === 0 ? '' : `${Math.round(calories)} ккал`;
        svg.appendChild(calText);

        container.appendChild(svg);
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
            total_fiber: currentMealAnalysis?.total_fiber ?? 0,
            ai_comment: currentFoodQuality ? currentFoodQuality.toxic_coach_comment : null,
            ai_score: currentFoodQuality ? currentFoodQuality.ai_score : null,
            oil_absorption_score: currentFoodQuality?.oil_absorption_score ?? null,
            ultra_processing_score: currentFoodQuality?.ultra_processing_score ?? null,
            hidden_ingredients_risk: currentFoodQuality?.hidden_ingredients_risk ?? null,
            amino_acid_score: currentFoodQuality?.amino_acid_score ?? null,
            animal_protein_ratio: currentFoodQuality?.animal_protein_ratio ?? null,
            protein_density: currentFoodQuality?.protein_density ?? null,
            omega6_omega3_ratio: currentFoodQuality?.omega6_omega3_ratio ?? null,
            trans_fat_ratio: currentFoodQuality?.trans_fat_ratio ?? null,
            saturated_fat_ratio: currentFoodQuality?.saturated_fat_ratio ?? null,
            monounsaturated_fat_ratio: currentFoodQuality?.monounsaturated_fat_ratio ?? null,
            polyunsaturated_fat_ratio: currentFoodQuality?.polyunsaturated_fat_ratio ?? null,
            glycemic_load: currentFoodQuality?.glycemic_load ?? null,
            fiber_to_carb_ratio: currentFoodQuality?.fiber_to_carb_ratio ?? null,
            added_sugar_ratio: currentFoodQuality?.added_sugar_ratio ?? null,
            nova_processing_level: currentFoodQuality?.nova_processing_level ?? null,
            ai_analysis_details: currentMealAnalysis?.ai_analysis_details ?? null,
        };

        try {
            const res = await fetchWithAuth('/meals/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(mealData)
            });
            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || 'Ошибка сохранения');
            }
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

        ringTooltipTimeout = setTimeout(hideRingTooltip, 25000);
    }

    function hideRingTooltip() {
        if (!ringTooltip) return;
        ringTooltip.classList.replace('opacity-100', 'opacity-0');
        ringTooltip.classList.add('pointer-events-none');
        ringTooltip.style.transform = 'scale(0.9)';
    }

    // --- ОБНОВЛЕНИЕ БЛОКА СОВЕТОВ ---
    function loadDailyQuality() {
        const loadQuality = async () => {
            try {
                const res = await fetchWithAuth('/users/me/daily-quality');
                const data = await res.json();
                dailyMeals = data.meals || [];
                dailyTotal = data.total || null;
                if (dailyMeals.length > 0) {
                    currentMealIndex = dailyMeals.length - 1;
                    isTotalView = false;
                } else {
                    currentMealIndex = -1;
                    isTotalView = true;
                }
                renderMealView();
            } catch (e) {
                console.error("Ошибка загрузки качества:", e);
                dailyMeals = [];
                dailyTotal = null;
                renderDailyQualityRing(null, 0);
                renderQualityCards({});
            }
        };
        loadQuality();
    }

    function updateDailyQualityRing(summary, periodSummary) {
        loadDailyQuality();
    }


    function calculateNutrientQualityScores() {
        const details = currentMealAnalysis?.ai_analysis_details;
        if (!details || details.length === 0) return null;

        const sums = { protein: 0, fat: 0, carbohydrates: 0 };
        const weightSums = { protein: 0, fat: 0, carbohydrates: 0 };

        details.forEach(detail => {
            const p = Number(detail.protein_g) || 0;
            const f = Number(detail.fat_g) || 0;
            const c = Number(detail.carbs_g) || 0;
            
            const criteria = detail.criteria || {};
            let pScore = detail.protein_quality_score;
            let fScore = detail.fat_quality_score;
            let cScore = detail.carbs_quality_score;

            if (pScore === null || pScore === undefined) pScore = criteria.protein_quality;
            if (fScore === null || fScore === undefined) fScore = criteria.oil_absorption !== null && criteria.oil_absorption !== undefined ? 10 - criteria.oil_absorption : null;
            if (cScore === null || cScore === undefined) cScore = criteria.processing !== null && criteria.processing !== undefined ? 10 - criteria.processing : null;

            if (pScore !== null && pScore !== undefined && p > 0) { sums.protein += pScore * p; weightSums.protein += p; }
            if (fScore !== null && fScore !== undefined && f > 0) { sums.fat += fScore * f; weightSums.fat += f; }
            if (cScore !== null && cScore !== undefined && c > 0) { sums.carbohydrates += cScore * c; weightSums.carbohydrates += c; }
        });

        return {
            protein: weightSums.protein > 0 ? Math.round(sums.protein / weightSums.protein) : null,
            fat: weightSums.fat > 0 ? Math.round(sums.fat / weightSums.fat) : null,
            carbohydrates: weightSums.carbohydrates > 0 ? Math.round(sums.carbohydrates / weightSums.carbohydrates) : null,
        };
    }

    function getScoreColor(score) {
        if (score === null || score === undefined) return 'var(--text-secondary)';
        if (score <= 40) return '#EF4444';
        if (score <= 70) return '#F59E0B';
        return '#10B981';
    }

    function getQualityBadgeColor(score) {
        if (score === null || score === undefined) return 'var(--text-secondary)';
        if (score >= 7) return '#10B981';
        if (score >= 4) return '#F59E0B';
        return '#EF4444';
    }
    function updateRingWithStatus(ringSvgElement, value, maxValue, nutrient = null) {
        if (!ringSvgElement) return;
        const bar = ringSvgElement.querySelector('.progress-ring-bar');
        if (!bar) return;

        const radius = bar.r.baseVal.value;
        const circum = 2 * Math.PI * radius;

        let fillPct = maxValue > 0 ? value / maxValue : 0;
        const isOverflow = fillPct > 1.0;
        const clampedPct = Math.min(fillPct, 1);

        let displayPct;
        let displayOverflowPct = 0;

        if (ringDisplayMode === 'remaining' && nutrient && nutrient !== 'score') {
            const remaining = maxValue - value;
            if (remaining <= 0) {
                displayPct = 0;
                displayOverflowPct = Math.min(-remaining / maxValue, 1);
            } else {
                displayPct = remaining / maxValue;
            }
        } else {
            displayPct = clampedPct;
            displayOverflowPct = isOverflow ? fillPct - 1 : 0;
        }

        const filledLength = displayPct * circum;
        bar.style.strokeDasharray = `${filledLength} ${circum - filledLength}`;
        bar.style.strokeDashoffset = '0';

        let overflowBar = ringSvgElement.querySelector('.progress-ring-overflow');
        if (displayOverflowPct > 0) {
            if (!overflowBar) {
                overflowBar = document.createElementNS("http://www.w3.org/2000/svg", "circle");
                overflowBar.setAttribute('cx', bar.getAttribute('cx'));
                overflowBar.setAttribute('cy', bar.getAttribute('cy'));
                overflowBar.setAttribute('r', bar.getAttribute('r'));
                overflowBar.setAttribute('stroke-width', bar.getAttribute('stroke-width'));
                overflowBar.setAttribute('fill', 'none');
                overflowBar.setAttribute('stroke-linecap', 'round');
                overflowBar.classList.add('progress-ring-overflow');
                ringSvgElement.insertBefore(overflowBar, bar.nextSibling);
            }
            const overflowLength = displayOverflowPct * circum;
            overflowBar.style.strokeDasharray = `${overflowLength} ${circum - overflowLength}`;
            overflowBar.style.strokeDashoffset = `-${filledLength}`;
            overflowBar.style.display = 'block';
            overflowBar.setAttribute('stroke', nutrient === 'protein' ? '#22C55E' : '#EF4444');
            overflowBar.removeAttribute('filter');
        } else if (overflowBar) {
            overflowBar.style.display = 'none';
        }

        bar.classList.remove('status-warning', 'status-danger', 'status-success');

        if (isOverflow) {
            const gradientMap = {
                calories: ['url(#avg-grad-calories)', 'url(#avg-glow-calories)'],
                protein: ['url(#avg-grad-protein)', 'url(#avg-glow-protein)'],
                fat: ['url(#avg-grad-fat)', 'url(#avg-glow-fat)'],
                carbohydrates: ['url(#avg-grad-carbs)', 'url(#avg-glow-carbs)'],
                score: ['url(#avg-grad-score)', 'url(#avg-glow-score)'],
            };
            if (nutrient && gradientMap[nutrient]) {
                bar.setAttribute('stroke', gradientMap[nutrient][0]);
                bar.setAttribute('filter', gradientMap[nutrient][1]);
            }
        } else if (displayPct > 0.95 && nutrient !== 'protein') {
            bar.classList.add('status-warning');
        } else if (displayPct > 1.05 && nutrient === 'protein') {
            bar.classList.add('status-success');
        } else {
            const gradientMap = {
                calories: ['url(#avg-grad-calories)', 'url(#avg-glow-calories)'],
                protein: ['url(#avg-grad-protein)', 'url(#avg-glow-protein)'],
                fat: ['url(#avg-grad-fat)', 'url(#avg-glow-fat)'],
                carbohydrates: ['url(#avg-grad-carbs)', 'url(#avg-glow-carbs)'],
                score: ['url(#avg-grad-score)', 'url(#avg-glow-score)'],
            };
            if (nutrient && gradientMap[nutrient]) {
                bar.setAttribute('stroke', gradientMap[nutrient][0]);
                bar.setAttribute('filter', gradientMap[nutrient][1]);
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
            let effectiveTargets = targets;
            if (!targets || !targets.target_calories) {
                const res = await fetchWithAuth('/users/me/average-stats');
                const data = await res.json();
                effectiveTargets = {
                    target_calories: data.target_calories || 2000,
                    target_protein: data.target_protein || 150,
                    target_fat: data.target_fat || 70,
                    target_carbohydrates: data.target_carbohydrates || 250,
                };
            }

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
                        ${createMiniRing(m.id, 'calories', m.total_calories, effectiveTargets.target_calories, 'amber')}
                        ${createMiniRing(m.id, 'protein', m.total_protein, effectiveTargets.target_protein, 'protein-white')}
                        ${createMiniRing(m.id, 'fat', m.total_fat, effectiveTargets.target_fat, 'golden-orange')}
                        ${createMiniRing(m.id, 'carbs', m.total_carbohydrates, effectiveTargets.target_carbohydrates, 'muted-teal')}
                    </div>
                `;
                mealLogsContainer.appendChild(card);

                ['calories', 'protein', 'fat', 'carbs'].forEach(type => {
                    const nutrientKey = type === 'carbs' ? 'carbohydrates' : type;
                    const ringSvgElement = card.querySelector(`#log-${m.id}-${type}-ring`);
                    if (ringSvgElement) {
                        updateRingWithStatus(ringSvgElement, m[`total_${nutrientKey}`], effectiveTargets[`target_${nutrientKey}`], nutrientKey);
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
            const averageStatsContainer = document.getElementById('average-stats');
            const graphWrapper = document.getElementById('graph-wrapper');
            const labelsContainer = document.getElementById('x-axis-labels-container');
            const graphContainer = document.getElementById('score-graph-container');
            const ringToggleEl = document.getElementById('ring-toggle');

            // Сразу скрываем график и очищаем контейнеры ДО запроса
            graphContainer.innerHTML = '';
            labelsContainer.innerHTML = '';
            graphWrapper.classList.add('opacity-0', 'pointer-events-none');
            labelsContainer.classList.add('opacity-0', 'pointer-events-none');

            const res = await fetchWithAuth(`/users/me/stats/summary-by-period?days=${days}`);
            const data = await res.json();

            // Обновляем средние показатели
            const s = data.period_summary;
            updateRingWithStatus(document.getElementById('avg-calories-ring'), s.avg_calories, s.target_calories, 'calories');
            updateRingWithStatus(document.getElementById('avg-protein-ring'), s.avg_protein, s.target_protein, 'protein');
            updateRingWithStatus(document.getElementById('avg-fat-ring'), s.avg_fat, s.target_fat, 'fat');
            updateRingWithStatus(document.getElementById('avg-carbs-ring'), s.avg_carbohydrates, s.target_carbohydrates, 'carbohydrates');

            if (ringDisplayMode === 'remaining') {
                document.getElementById('avg-calories-value').textContent = Math.round(s.target_calories - s.avg_calories);
                document.getElementById('avg-protein-value').textContent = Math.round(s.target_protein - s.avg_protein);
                document.getElementById('avg-fat-value').textContent = Math.round(s.target_fat - s.avg_fat);
                document.getElementById('avg-carbs-value').textContent = Math.round(s.target_carbohydrates - s.avg_carbohydrates);
            } else {
                document.getElementById('avg-calories-value').textContent = Math.round(s.avg_calories);
                document.getElementById('avg-protein-value').textContent = Math.round(s.avg_protein);
                document.getElementById('avg-fat-value').textContent = Math.round(s.avg_fat);
                document.getElementById('avg-carbs-value').textContent = Math.round(s.avg_carbohydrates);
            }

            // Передаем цели в историю приемов пищи
            fetchAndDisplayMealHistory(s);

            const scores = data.daily_breakdown.map(d => d.daily_score).filter(s => s !== null && s !== undefined);
            const avgScoreValue = document.getElementById('avg-score-value');
            const avgScoreBar = document.getElementById('avg-score-bar');
            const avgScoreRingContainer = document.getElementById('avg-score-ring-container');

            if (scores.length > 0) {
                const averageScore = Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);
                avgScoreValue.textContent = averageScore;
                updateRingWithStatus(document.getElementById('avg-score-ring'), averageScore, 100);

                let scoreColor = '#e11d48'; // red
                if (averageScore >= 95) scoreColor = '#FFD700'; // gold
                else if (averageScore >= 80) scoreColor = '#F0F0F0'; // white
                else if (averageScore >= 60) scoreColor = '#f59e0b'; // amber

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

            // Обновляем кольцо качества питания
            updateDailyQualityRing(data.progress_lab_summary, data.period_summary);

            // Обновление меток КБЖУ
            const caloriesLabel = document.getElementById('avg-calories-label');
            const proteinLabel = document.getElementById('avg-protein-label');
            const fatLabel = document.getElementById('avg-fat-label');
            const carbsLabel = document.getElementById('avg-carbs-label');

            if (days === 1) {
                // График уже скрыт и очищен выше
                if (ringToggleEl) ringToggleEl.parentElement.classList.remove('hidden');
                averageStatsContainer.classList.add('flex-grow', 'flex', 'items-center', 'justify-center', 'day-view-active');

                caloriesLabel.textContent = 'Калории';
                proteinLabel.textContent = 'Белки';
                fatLabel.textContent = 'Жиры';
                carbsLabel.textContent = 'Углеводы';

            } else {
                graphWrapper.classList.remove('opacity-0', 'pointer-events-none');
                labelsContainer.classList.remove('opacity-0', 'pointer-events-none');
                averageStatsContainer.classList.remove('flex-grow', 'flex', 'items-center', 'justify-center', 'day-view-active');
                if (ringToggleEl) ringToggleEl.parentElement.classList.add('hidden');

                caloriesLabel.textContent = 'Ккал';
                proteinLabel.textContent = 'Б';
                fatLabel.textContent = 'Ж';
                carbsLabel.textContent = 'У';

                // Рендеринг графика
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
            }
        } catch (e) { console.error("Ошибка графика:", e); }
        document.getElementById('stats-graph-panel')?.classList.remove('opacity-0');
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
            const scoreTooltipText = "Оценка показывает процент выполнения дневного плана питания (0-100).\n\n• Калории — 40% от оценки\n• Белки — 30% от оценки\n• Жиры — 15% от оценки\n• Углеводы — 15% от оценки\n\nПеребор по жирам и углеводам штрафуется сильнее. Перебор по белку при нормальных калориях даёт бонус +5.\n\n95-100 — отлично\n80-94 — хорошо\n60-79 — удовлетворительно\n<60 — нужно улучшить";
            const scoreColor = document.getElementById('avg-score-value').style.color || '#F0F0F0';
            showRingTooltip(avgScoreWrapper, 'Daily Score', scoreTooltipText, scoreColor);
        });
    }

    // --- Переключение табов ---
    const tabNutrition = document.getElementById('tab-nutrition');
    const tabHistory = document.getElementById('tab-history');
    const viewNutrition = document.getElementById('view-nutrition');
    const viewHistory = document.getElementById('view-history');

    let currentTab = 'nutrition';

    function switchTab(tab) {
        currentTab = tab;
        [tabNutrition, tabHistory].forEach(btn => {
            btn.classList.remove('active');
            btn.classList.add('text-gray-400');
        });
        [viewNutrition, viewHistory].forEach(v => v.classList.add('hidden'));

        if (tab === 'nutrition') {
            tabNutrition.classList.add('active');
            tabNutrition.classList.remove('text-gray-400');
            viewNutrition.classList.remove('hidden');
            loadDailyQuality();
        } else if (tab === 'history') {
            tabHistory.classList.add('active');
            tabHistory.classList.remove('text-gray-400');
            viewHistory.classList.remove('hidden');
            fetchScoreGraphData(1);
            fetchAndDisplayMealHistory({});
        }
    }

    if (tabNutrition) tabNutrition.onclick = () => switchTab('nutrition');
    if (tabHistory) tabHistory.onclick = () => switchTab('history');

    // --- Первоначальная загрузка данных ---
    if (oneDayBtn) {
        oneDayBtn.classList.add('active');
        oneDayBtn.classList.remove('text-gray-400');
    }
    switchTab('nutrition');
    resetWizard();

    // --- Тумблер режима колец ---
    const ringToggleEl = document.getElementById('ring-toggle');
    if (ringToggleEl) {
        ringToggleEl.addEventListener('click', () => {
            ringDisplayMode = ringDisplayMode === 'progress' ? 'remaining' : 'progress';
            ringToggleEl.classList.toggle('mode-remaining', ringDisplayMode === 'remaining');
            fetchScoreGraphData(1);
        });
    }

    // --- Свайп по кольцу качества ---
    const qualityContainer = document.getElementById('daily-quality-ring-container');
    if (qualityContainer) {
        let touchStartX = 0;
        qualityContainer.addEventListener('touchstart', (e) => {
            touchStartX = e.touches[0].clientX;
        });
        qualityContainer.addEventListener('touchend', (e) => {
            const diff = e.changedTouches[0].clientX - touchStartX;
            if (Math.abs(diff) > 50) {
                if (diff < 0 && !isTotalView) {
                    if (currentMealIndex < dailyMeals.length - 1) {
                        currentMealIndex++;
                        renderMealView();
                    } else if (dailyTotal) {
                        isTotalView = true;
                        renderMealView();
                    }
                } else if (diff > 0) {
                    if (isTotalView) {
                        isTotalView = false;
                        currentMealIndex = dailyMeals.length - 1;
                        renderMealView();
                    } else if (currentMealIndex > 0) {
                        currentMealIndex--;
                        renderMealView();
                    }
                }
            }
        });
    }
});