// /static/js/api.js

async function fetchWithAuth(url, options = {}) {
    const token = localStorage.getItem('accessToken');

    const headers = {
        ...options.headers,
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const newOptions = {
        ...options,
        headers,
    };

    try {
        const response = await fetch(url, newOptions);

        if (response.status === 401) {
            // Токен недействителен или истек
            localStorage.removeItem('accessToken');
            // Перенаправляем на страницу входа
            window.location.href = '/';
            // Возвращаем "пустой" промис, чтобы прервать дальнейшее выполнение
            return new Promise(() => {});
        }

        return response;
    } catch (error) {
        console.error('Fetch error:', error);
        throw error;
    }
}
