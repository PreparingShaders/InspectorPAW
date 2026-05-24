document.addEventListener('DOMContentLoaded', () => {
    const logoutButton = document.getElementById('logout-button-nav');
    if (logoutButton) {
        logoutButton.addEventListener('click', () => {
            localStorage.removeItem('accessToken');
            window.location.href = '/';
        });
    }
});
