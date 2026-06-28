document.addEventListener('DOMContentLoaded', () => {
    const loginView = document.getElementById('login-view');
    const registerView = document.getElementById('register-view');
    const forgotPasswordView = document.getElementById('forgot-password-view');

    const showRegisterLink = document.getElementById('show-register');
    const showLoginLink = document.getElementById('show-login');
    const showForgotPasswordLink = document.getElementById('show-forgot-password');
    const backToLoginLink = document.getElementById('back-to-login');

    const errorMessage = document.getElementById('error-message');
    const successMessage = document.getElementById('success-message');

    // --- View Toggling ---
    showRegisterLink.addEventListener('click', (e) => {
        e.preventDefault();
        loginView.style.display = 'none';
        forgotPasswordView.style.display = 'none';
        registerView.style.display = 'block';
        clearMessages();
    });

    showLoginLink.addEventListener('click', (e) => {
        e.preventDefault();
        registerView.style.display = 'none';
        forgotPasswordView.style.display = 'none';
        loginView.style.display = 'block';
        clearMessages();
    });

    showForgotPasswordLink.addEventListener('click', (e) => {
        e.preventDefault();
        loginView.style.display = 'none';
        registerView.style.display = 'none';
        forgotPasswordView.style.display = 'block';
        clearMessages();
    });

    backToLoginLink.addEventListener('click', (e) => {
        e.preventDefault();
        showLoginLink.click();
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

            const userResponse = await fetch('/users/me', {
                headers: { 'Authorization': `Bearer ${accessToken}` }
            });

            if (!userResponse.ok) {
                throw new Error('Не удалось получить данные пользователя.');
            }

            const user = await userResponse.json();

            if (!user.date_of_birth || !user.gender || !user.height_cm || !user.goal || user.metrics.length === 0) {
                window.location.href = '/profile';
            } else {
                window.location.href = '/daily-quality';
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
        const passwordConfirm = document.getElementById('register-password-confirm').value;

        if (password !== passwordConfirm) {
            errorMessage.textContent = 'Пароли не совпадают.';
            errorMessage.style.display = 'block';
            return;
        }

        try {
            const response = await fetch('/users/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email: email,
                    password: password,
                    password_confirm: passwordConfirm
                }),
            });

            if (response.ok) {
                if (response.redirected) {
                    window.location.href = response.url;
                } else {
                    window.location.href = `/verify-email?email=${encodeURIComponent(email)}`;
                }
            } else {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Не удалось создать аккаунт.');
            }
        } catch (error) {
            errorMessage.textContent = error.message;
            errorMessage.style.display = 'block';
        }
    });

    // --- Forgot Password Form Handling ---
    document.getElementById('forgot-password-form').addEventListener('submit', async function(event) {
        event.preventDefault();
        clearMessages();

        const email = document.getElementById('forgot-email').value;
        const formData = new FormData();
        formData.append('email', email);

        try {
            const response = await fetch('/forgot-password', {
                method: 'POST',
                body: formData,
            });

            if (response.ok) {
                if (response.redirected) {
                    window.location.href = response.url;
                } else {
                    // На случай, если редирект не сработает, покажем сообщение
                    successMessage.textContent = 'Если email верный, мы отправили код для сброса пароля.';
                    successMessage.style.display = 'block';
                }
            } else {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Произошла ошибка.');
            }
        } catch (error) {
            errorMessage.textContent = error.message;
            errorMessage.style.display = 'block';
        }
    });
});