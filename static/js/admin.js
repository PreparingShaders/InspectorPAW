document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('accessToken');
    if (!token) {
        window.location.href = '/';
        return;
    }

    const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
    };

    const usersTableBody = document.getElementById('users-table-body');
    let currentUserIdForPasswordReset = null;
    let debounceTimer;

    async function fetchUsers() {
        try {
            const response = await fetch('/admin/users', { headers });
            if (response.status === 403) {
                alert('Доступ запрещен. У вас нет прав администратора.');
                window.location.href = '/dashboard';
                return;
            }
            if (!response.ok) {
                throw new Error('Не удалось загрузить пользователей');
            }
            const users = await response.json();
            renderUsers(users);
        } catch (error) {
            console.error(error);
            alert(error.message);
        }
    }

    function renderUsers(users) {
        usersTableBody.innerHTML = '';
        users.forEach(user => {
            const row = document.createElement('tr');
            row.className = 'border-b border-gray-700/50';

            const premiumDate = user.premium_expires_at ? new Date(user.premium_expires_at).toISOString().split('T')[0] : '';

            row.innerHTML = `
                <td class="px-2 py-3 text-sm">${user.id}</td>
                <td class="px-2 py-3 text-sm">${user.email}</td>
                <td class="px-2 py-3">
                    <select data-user-id="${user.id}" data-field="role" class="bg-gray-700 rounded p-1 text-sm w-full">
                        <option value="user" ${user.role === 'user' ? 'selected' : ''}>User</option>
                        <option value="admin" ${user.role === 'admin' ? 'selected' : ''}>Admin</option>
                    </select>
                </td>
                <td class="px-2 py-3">
                    <input type="date" data-user-id="${user.id}" data-field="premium_expires_at" value="${premiumDate}" class="bg-gray-700 rounded p-1 text-sm w-full">
                </td>
                <td class="px-2 py-3 text-center">
                    <input type="checkbox" data-user-id="${user.id}" data-field="is_active" class="form-checkbox h-5 w-5 text-blue-500 bg-gray-700 border-gray-600 rounded" ${user.is_active ? 'checked' : ''}>
                </td>
                <td class="px-2 py-3">
                    <button data-user-id="${user.id}" data-user-email="${user.email}" class="bg-yellow-600 hover:bg-yellow-700 text-white font-bold py-1 px-2 rounded text-xs reset-password-btn">Пароль</button>
                </td>
            `;
            usersTableBody.appendChild(row);
        });
    }

    async function updateUser(userId, field, value) {
        // Если значение даты пустое, отправляем null
        const bodyValue = (field === 'premium_expires_at' && value === '') ? null : value;

        try {
            const response = await fetch(`/admin/users/${userId}`, {
                method: 'PUT',
                headers,
                body: JSON.stringify({ [field]: bodyValue })
            });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Не удалось обновить пользователя');
            }
            // Можно добавить небольшое уведомление об успехе
        } catch (error) {
            console.error(error);
            alert(error.message);
            fetchUsers(); // Перезагружаем данные при ошибке
        }
    }

    usersTableBody.addEventListener('change', (event) => {
        const target = event.target;
        if (target.matches('select[data-user-id]') || target.matches('input[data-user-id]')) {
            const userId = target.dataset.userId;
            const field = target.dataset.field;
            let value = target.type === 'checkbox' ? target.checked : target.value;

            // Для полей с задержкой (например, дата)
            if (target.type === 'date') {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => {
                    updateUser(userId, field, value);
                }, 800); // Задержка в 800 мс
            } else {
                updateUser(userId, field, value);
            }
        }
    });

    usersTableBody.addEventListener('click', (event) => {
        if (event.target.classList.contains('reset-password-btn')) {
            currentUserIdForPasswordReset = event.target.dataset.userId;
            const userEmail = event.target.dataset.userEmail;
            openModal(userEmail);
        }
    });

    window.openModal = function(userEmail) {
        document.getElementById('reset-user-email').textContent = userEmail;
        document.getElementById('password-reset-modal').classList.remove('hidden');
    }

    window.closeModal = function() {
        document.getElementById('password-reset-modal').classList.add('hidden');
        document.getElementById('new-password-input').value = '';
        currentUserIdForPasswordReset = null;
    }

    window.submitPasswordReset = async function() {
        const newPassword = document.getElementById('new-password-input').value;
        if (!newPassword || newPassword.length < 8) {
            alert('Пароль должен содержать не менее 8 символов.');
            return;
        }

        try {
            const response = await fetch('/admin/users/reset-password', {
                method: 'POST',
                headers,
                body: JSON.stringify({
                    user_id: parseInt(currentUserIdForPasswordReset),
                    new_password: newPassword
                })
            });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Не удалось сбросить пароль');
            }
            alert('Пароль успешно сброшен.');
            closeModal();
        } catch (error) {
            console.error(error);
            alert(error.message);
        }
    }

    fetchUsers();
});