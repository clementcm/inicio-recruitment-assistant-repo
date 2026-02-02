// Auth Guard
const token = localStorage.getItem('inicio_token');
if (!token && window.location.pathname !== '/login') {
    window.location.href = '/login';
}

async function authFetch(url, options = {}) {
    const token = localStorage.getItem('inicio_token');
    if (!token) {
        window.location.href = '/login';
        return;
    }

    options.headers = {
        ...options.headers,
        'Authorization': `Bearer ${token}`
    };

    const response = await fetch(url, options);
    if (response.status === 401) {
        localStorage.removeItem('inicio_token');
        window.location.href = '/login';
    }
    return response;
}

// Logic to run when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Admin Link Injection
    if (localStorage.getItem('inicio_is_admin') === 'true') {
        const footer = document.querySelector('.sidebar-footer');
        if (footer) {
            // Check if already exists to prevent duplicate
            if (!footer.querySelector('.admin-link-btn')) {
                const adminBtn = document.createElement('button');
                adminBtn.className = 'settings-btn admin-link-btn';
                adminBtn.innerHTML = `
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                    </svg>
                    <span>Admin Dashboard</span>
                `;
                adminBtn.onclick = () => window.location.href = '/admin';
                adminBtn.style.marginBottom = '4px';
                footer.insertBefore(adminBtn, footer.firstChild);
            }
        }
    }

    // Sidebar Toggle Logic
    const sidebar = document.querySelector('.sidebar');
    const toggleBtnSidebar = document.getElementById('sidebar-toggle-sidebar');
    const toggleBtnFloat = document.getElementById('sidebar-toggle-float');

    if (sidebar && toggleBtnSidebar) {
        function toggleSidebar() {
            sidebar.classList.toggle('collapsed');
            document.body.classList.toggle('sidebar-collapsed');
        }

        toggleBtnSidebar.onclick = toggleSidebar;
        if (toggleBtnFloat) toggleBtnFloat.onclick = toggleSidebar;
    }

    // Logout Logic
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.onclick = () => {
            localStorage.removeItem('inicio_token');
            window.location.href = '/login';
        };
    }

    // Settings Modal Logic
    const settingsBtn = document.getElementById('settings-btn');
    const settingsModal = document.getElementById('settings-modal');
    const closeSettingsBtn = document.getElementById('close-settings');

    if (settingsBtn && settingsModal) {
        settingsBtn.onclick = () => settingsModal.classList.add('active');

        if (closeSettingsBtn) {
            closeSettingsBtn.onclick = () => settingsModal.classList.remove('active');
        }

        settingsModal.onclick = (e) => {
            if (e.target === settingsModal) settingsModal.classList.remove('active');
        };
    }
});
