const API_URL = '/api/admin/users';
let editingUser = null;

// Ensure authFetch is available (loaded from shared.js)
if (typeof authFetch === 'undefined') {
    console.error("authFetch not found. Ensure shared.js is loaded.");
}

async function fetchUsers() {
    try {
        console.log("Fetching users...");
        const res = await authFetch(API_URL);
        if (!res) return; // authFetch redirects if 401

        if (res.status === 403) {
            alert("Access Denied: Admin privileges required.");
            window.location.href = '/';
            return;
        }

        if (!res.ok) throw new Error('Failed to fetch users');

        const users = await res.json();
        renderTable(users);
    } catch (e) {
        console.error("Fetch error:", e);
    }
}

function renderTable(users) {
    const tbody = document.getElementById('user-table-body');
    if (!tbody) return;
    tbody.innerHTML = users.map(user => `
        <tr>
            <td>${user.id}</td>
            <td>
                ${user.email} 
                ${user.is_admin ? '<span class="admin-badge">ADMIN</span>' : ''}
            </td>
            <td>
                <span class="status-badge ${user.is_approved ? 'approved' : 'pending'}">
                    ${user.is_approved ? 'Active' : 'Pending Approval'}
                </span>
            </td>
            <td>
                ${!user.is_approved ? `<button class="action-btn approve" onclick="approveUser(${user.id})">Approve</button>` : ''}
                <button class="action-btn" onclick="editUser(${user.id}, '${user.email}', ${user.is_admin})">Edit</button>
                <button class="action-btn delete" onclick="deleteUser(${user.id})">Delete</button>
            </td>
        </tr>
    `).join('');
}

async function approveUser(id) {
    if (!confirm('Approve this user?')) return;
    await authFetch(`${API_URL}/${id}/approve`, { method: 'PUT' });
    fetchUsers();
}

async function deleteUser(id) {
    if (!confirm('Are you sure? This cannot be undone.')) return;
    await authFetch(`${API_URL}/${id}`, { method: 'DELETE' });
    fetchUsers();
}

// Global Modal Functions
window.openModal = function () {
    editingUser = null;
    const title = document.getElementById('modalTitle');
    if (title) title.innerText = 'Add User';

    document.getElementById('editUserId').value = '';

    const emailInput = document.getElementById('userEmail');
    if (emailInput) {
        emailInput.value = '';
        emailInput.disabled = false;
    }

    document.getElementById('userPassword').value = '';
    document.getElementById('pwd-hint').innerText = '(Required)';
    document.getElementById('userIsAdmin').checked = false;

    const modal = document.getElementById('userModal');
    modal.style.display = 'flex';
    setTimeout(() => modal.classList.add('active'), 10);
};

window.editUser = function (id, email, isAdmin) {
    editingUser = id;
    document.getElementById('modalTitle').innerText = 'Edit User';
    document.getElementById('editUserId').value = id;
    document.getElementById('userEmail').value = email;
    document.getElementById('userEmail').disabled = true;
    document.getElementById('userPassword').value = '';
    document.getElementById('pwd-hint').innerText = '(Leave blank to keep unchanged)';
    document.getElementById('userIsAdmin').checked = isAdmin;

    const modal = document.getElementById('userModal');
    modal.style.display = 'flex';
    setTimeout(() => modal.classList.add('active'), 10);
};

window.closeModal = function () {
    const modal = document.getElementById('userModal');
    modal.classList.remove('active');
    setTimeout(() => modal.style.display = 'none', 300);
};

window.saveUser = async function () {
    const email = document.getElementById('userEmail').value;
    const password = document.getElementById('userPassword').value;
    const isAdmin = document.getElementById('userIsAdmin').checked;

    if (!editingUser && !password) return alert('Password required for new user');

    try {
        const headers = { 'Content-Type': 'application/json' };

        if (editingUser) {
            const payload = { is_admin: isAdmin };
            if (password) payload.password = password;

            const res = await authFetch(`${API_URL}/${editingUser}`, {
                method: 'PUT',
                headers,
                body: JSON.stringify(payload)
            });
            if (!res.ok) throw new Error('Update failed');
        } else {
            const res = await authFetch(API_URL, {
                method: 'POST',
                headers,
                body: JSON.stringify({ email, password })
            });
            if (!res.ok) throw new Error('Create failed');
            if (isAdmin) {
                const createdUser = await res.json();
                await authFetch(`${API_URL}/${createdUser.id}`, {
                    method: 'PUT',
                    headers,
                    body: JSON.stringify({ is_admin: true })
                });
            }
        }
        closeModal();
        fetchUsers();
    } catch (e) {
        alert(e.message);
    }
};

document.addEventListener('DOMContentLoaded', () => {
    // Modal Outside Click
    const modal = document.getElementById('userModal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeModal();
        });
    }

    // New Chat Button Redirect (for Admin Sidebar)
    const newChatBtn = document.getElementById('new-chat-btn');
    if (newChatBtn) {
        newChatBtn.onclick = () => window.location.href = '/';
    }

    // Load data
    fetchUsers();
    loadSystemConfig();
});

// System Config Logic
window.loadSystemConfig = async function () {
    try {
        const res = await authFetch('/api/admin/config');
        if (res.ok) {
            const configs = await res.json();
            configs.forEach(c => {
                const el = document.getElementById(c.key === 'UNIPILE_DSN' ? 'config-dsn' :
                    c.key === 'UNIPILE_API_KEY' ? 'config-api-key' :
                        c.key === 'LINKEDIN_ACCOUNT_ID' ? 'config-account-id' : null);
                if (el) el.value = c.value;
            });
        }
    } catch (e) {
        console.error("Failed to load config", e);
    }
};

window.saveSystemConfig = async function () {
    const updates = [
        { key: 'UNIPILE_DSN', value: document.getElementById('config-dsn').value },
        { key: 'UNIPILE_API_KEY', value: document.getElementById('config-api-key').value },
        { key: 'LINKEDIN_ACCOUNT_ID', value: document.getElementById('config-account-id').value }
    ];

    try {
        const res = await authFetch('/api/admin/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates)
        });
        if (res.ok) {
            alert('Configuration updated successfully!');
        } else {
            alert('Failed to update configuration.');
        }
    } catch (e) {
        console.error("Failed to save config", e);
        alert('Error saving configuration.');
    }
};
