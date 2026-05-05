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

    async function fetchUsers() {
        try {
            const response = await fetch('/admin/users', { headers });
            if (response.status === 403) {
                alert('Access Denied');
                window.location.href = '/dashboard';
                return;
            }
            if (!response.ok) {
                throw new Error('Failed to fetch users');
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
            row.innerHTML = `
                <td class="border-t border-gray-700 px-4 py-2">${user.id}</td>
                <td class="border-t border-gray-700 px-4 py-2">${user.email}</td>
                <td class="border-t border-gray-700 px-4 py-2">
                    <select data-user-id="${user.id}" data-field="role" class="bg-gray-700 rounded p-1">
                        <option value="user" ${user.role === 'user' ? 'selected' : ''}>User</option>
                        <option value="admin" ${user.role === 'admin' ? 'selected' : ''}>Admin</option>
                    </select>
                </td>
                <td class="border-t border-gray-700 px-4 py-2">
                    <input type="checkbox" data-user-id="${user.id}" data-field="is_premium" class="form-checkbox h-5 w-5 text-blue-600 bg-gray-700 border-gray-600" ${user.is_premium ? 'checked' : ''}>
                </td>
                <td class="border-t border-gray-700 px-4 py-2">
                    <input type="checkbox" data-user-id="${user.id}" data-field="is_active" class="form-checkbox h-5 w-5 text-blue-600 bg-gray-700 border-gray-600" ${user.is_active ? 'checked' : ''}>
                </td>
                <td class="border-t border-gray-700 px-4 py-2">
                    <button data-user-id="${user.id}" data-user-email="${user.email}" class="bg-yellow-600 hover:bg-yellow-700 text-white font-bold py-1 px-2 rounded text-xs reset-password-btn">Reset Password</button>
                </td>
            `;
            usersTableBody.appendChild(row);
        });
    }

    async function updateUser(userId, field, value) {
        try {
            const response = await fetch(`/admin/users/${userId}`, {
                method: 'PUT',
                headers,
                body: JSON.stringify({ [field]: value })
            });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to update user');
            }
            // Optionally, show a success message
        } catch (error) {
            console.error(error);
            alert(error.message);
            fetchUsers(); // Re-fetch to revert optimistic update
        }
    }

    usersTableBody.addEventListener('change', (event) => {
        const target = event.target;
        if (target.matches('select[data-user-id]') || target.matches('input[type="checkbox"][data-user-id]')) {
            const userId = target.dataset.userId;
            const field = target.dataset.field;
            const value = target.type === 'checkbox' ? target.checked : target.value;
            updateUser(userId, field, value);
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
            alert('Password must be at least 8 characters long.');
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
                throw new Error(errorData.detail || 'Failed to reset password');
            }
            alert('Password has been reset successfully.');
            closeModal();
        } catch (error) {
            console.error(error);
            alert(error.message);
        }
    }

    fetchUsers();
});