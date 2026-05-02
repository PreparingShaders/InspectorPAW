document.addEventListener('DOMContentLoaded', () => {
    const loginView = document.getElementById('login-view');
    const registerView = document.getElementById('register-view');
    const showRegisterLink = document.getElementById('show-register');
    const showLoginLink = document.getElementById('show-login');
    const errorMessage = document.getElementById('error-message');
    const successMessage = document.getElementById('success-message');

    // --- View Toggling ---
    showRegisterLink.addEventListener('click', (e) => {
        e.preventDefault();
        loginView.style.display = 'none';
        registerView.style.display = 'block';
        clearMessages();
    });

    showLoginLink.addEventListener('click', (e) => {
        e.preventDefault();
        registerView.style.display = 'none';
        loginView.style.display = 'block';
        clearMessages();
    });

    function clearMessages() {
        errorMessage.textContent = '';
        errorMessage.style.display = 'none';
        successMessage.textContent = '';
        successMessage.style.display = 'none';
    }

    // --- Login Form Handling ---
    document.getElementById('login-form').addEventListener('submit', async function(event) {
        event.preventDefault();
        clearMessages();

        const email = event.target.username.value;
        const password = event.target.password.value;

        const formData = new FormData();
        formData.append('username', email);
        formData.append('password', password);

        try {
            // Step 1: Get Token
            const tokenResponse = await fetch('/token', {
                method: 'POST',
                body: formData
            });

            if (!tokenResponse.ok) {
                const errorData = await tokenResponse.json();
                throw new Error(errorData.detail || 'Ошибка входа. Проверьте email и пароль.');
            }

            const tokenData = await tokenResponse.json();
            const accessToken = tokenData.access_token;
            localStorage.setItem('accessToken', accessToken);

            // Step 2: Check if profile is complete
            const userResponse = await fetch('/users/me', {
                headers: { 'Authorization': `Bearer ${accessToken}` }
            });

            if (!userResponse.ok) {
                throw new Error('Не удалось получить данные пользователя.');
            }

            const user = await userResponse.json();

            // Check for essential profile data.
            // Note: `metrics` being empty is a valid check for the initial weight.
            if (!user.date_of_birth || !user.gender || !user.height_cm || !user.goal || user.metrics.length === 0) {
                window.location.href = '/profile';
            } else {
                window.location.href = '/dashboard';
            }

        } catch (error) {
            errorMessage.textContent = error.message;
            errorMessage.style.display = 'block';
        }
    });

    // --- Register Form Handling ---
    document.getElementById('register-form').addEventListener('submit', async function(event) {
        event.preventDefault();
        clearMessages();

        const email = document.getElementById('register-email').value;
        const password = document.getElementById('register-password').value;

        try {
            const response = await fetch('/users/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    email: email,
                    password: password,
                }),
            });

            if (response.ok) {
                successMessage.textContent = 'Аккаунт успешно создан! Теперь вы можете войти.';
                successMessage.style.display = 'block';
                showLoginLink.click(); // Switch to login view
            } else {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Не удалось создать аккаунт.');
            }
        } catch (error) {
            errorMessage.textContent = error.message;
            errorMessage.style.display = 'block';
        }
    });
});