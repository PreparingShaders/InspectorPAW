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
        successMessage.textContent = '';
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
            const response = await fetch('/token', {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('accessToken', data.access_token);
                window.location.href = '/dashboard';
            } else {
                const errorData = await response.json();
                errorMessage.textContent = errorData.detail || 'Ошибка входа. Проверьте email и пароль.';
            }
        } catch (error) {
            errorMessage.textContent = 'Произошла ошибка сети. Попробуйте снова.';
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
                showLoginLink.click(); // Switch to login view
            } else {
                const errorData = await response.json();
                errorMessage.textContent = errorData.detail || 'Не удалось создать аккаунт.';
            }
        } catch (error) {
            errorMessage.textContent = 'Произошла ошибка сети. Попробуйте снова.';
        }
    });
});
