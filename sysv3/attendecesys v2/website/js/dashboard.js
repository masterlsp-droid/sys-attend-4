import { backendApi as api } from './api.js';
import { escapeHtml, formatDate } from './utils.js';

let currentModalClassName = null;

export const initDashboard = () => {
    loadDashboardData();

    // Create Class Form
    const form = document.getElementById('create-class-form');
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const input = document.getElementById('class-name-input');
            const submitBtn = document.getElementById('create-class-btn');
            const msgBox = document.getElementById('class-form-message');
            const name = input.value.trim();

            if (!name) return;

            submitBtn.disabled = true;
            submitBtn.textContent = 'Creating...';
            msgBox.classList.add('hidden');

            try {
                await api.createClass({ name });
                msgBox.textContent = `Class "${name}" created successfully!`;
                msgBox.className = 'message-box success';
                msgBox.classList.remove('hidden');
                input.value = '';
                
                // Refresh dashboard data and dispatch event for enrollment dropdown
                await loadDashboardData();
                window.dispatchEvent(new CustomEvent('classesUpdated'));
            } catch (err) {
                const errorMsg = err.data?.detail?.message || err.data?.message || 'Failed to create class';
                msgBox.textContent = escapeHtml(errorMsg);
                msgBox.className = 'message-box error';
                msgBox.classList.remove('hidden');
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Create Class';
            }
        });
    }

    // Class Details Modal Handlers
    const modal = document.getElementById('class-details-modal');
    const closeBtn = document.getElementById('close-class-modal');
    const closeBtnBottom = document.getElementById('close-class-modal-btn');
    const enrollBtn = document.getElementById('modal-enroll-btn');

    const closeModal = () => {
        if (modal) modal.classList.add('hidden');
        currentModalClassName = null;
    };

    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    if (closeBtnBottom) closeBtnBottom.addEventListener('click', closeModal);
    
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeModal();
        });
    }

    // Modal action: Go directly to enrollment with this class pre-selected
    if (enrollBtn) {
        enrollBtn.addEventListener('click', () => {
            const classNameToEnroll = currentModalClassName;
            closeModal();
            
            // Switch to Enrollment tab
            const enrollTabBtn = document.querySelector('.tab-btn[data-tab="enrollment"]');
            if (enrollTabBtn) {
                enrollTabBtn.click();
            }

            // Set student role and pre-select class
            const studentRadio = document.querySelector('input[name="role"][value="student"]');
            if (studentRadio) {
                studentRadio.checked = true;
                studentRadio.dispatchEvent(new Event('change'));
            }

            if (classNameToEnroll) {
                const classSelect = document.getElementById('enroll-class');
                if (classSelect) {
                    classSelect.value = classNameToEnroll;
                }
            }

            const nameInput = document.getElementById('name');
            if (nameInput) {
                setTimeout(() => nameInput.focus(), 150);
            }
        });
    }
};

export const loadDashboardData = async () => {
    await Promise.all([
        loadStats(),
        loadClasses()
    ]);
};

const loadStats = async () => {
    try {
        const stats = await api.getDashboardStats();
        const elClasses = document.getElementById('stat-total-classes');
        const elStudents = document.getElementById('stat-total-students');
        const elTeachers = document.getElementById('stat-total-teachers');
        const elSessions = document.getElementById('stat-total-sessions');

        if (elClasses) elClasses.textContent = stats.total_classes ?? 0;
        if (elStudents) elStudents.textContent = stats.total_students ?? 0;
        if (elTeachers) elTeachers.textContent = stats.total_teachers ?? 0;
        if (elSessions) elSessions.textContent = stats.total_sessions ?? 0;
    } catch (e) {
        console.error('Failed to load dashboard stats:', e);
    }
};

export const loadClasses = async () => {
    const tbody = document.querySelector('#classes-table tbody');
    const emptyState = document.getElementById('classes-empty');
    if (!tbody || !emptyState) return;

    try {
        const res = await api.getClasses();
        const classes = res.classes || [];
        tbody.innerHTML = '';

        if (classes.length === 0) {
            emptyState.classList.remove('hidden');
            document.getElementById('classes-table').classList.add('hidden');
            return;
        }

        emptyState.classList.add('hidden');
        document.getElementById('classes-table').classList.remove('hidden');

        classes.forEach(c => {
            const tr = document.createElement('tr');
            tr.className = 'clickable-row';
            tr.setAttribute('title', `Click to view students in ${c.name}`);
            tr.innerHTML = `
                <td>
                    <div class="class-name-cell">
                        <span class="class-folder-icon">📁</span>
                        <strong>${escapeHtml(c.name)}</strong>
                    </div>
                </td>
                <td><span class="badge class-badge">${c.student_count || 0} enrolled</span></td>
                <td>${formatDate(c.created_at)}</td>
                <td>
                    <button class="btn btn-delete-class" data-id="${c.id}" data-name="${escapeHtml(c.name)}" title="Delete Class" aria-label="Delete Class">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="3 6 5 6 21 6"></polyline>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                            <line x1="10" y1="11" x2="10" y2="17"></line>
                            <line x1="14" y1="11" x2="14" y2="17"></line>
                        </svg>
                    </button>
                </td>
            `;

            // Row click to open class roster
            tr.addEventListener('click', (e) => {
                if (e.target.closest('.btn-delete-class')) return;
                openClassDetails(c.name, c.student_count);
            });

            tbody.appendChild(tr);
        });

        tbody.querySelectorAll('.btn-delete-class').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const btnEl = e.currentTarget;
                const id = btnEl.getAttribute('data-id');
                const name = btnEl.getAttribute('data-name');
                if (!confirm(`Are you sure you want to delete class "${name}"? Enrolled students will not be deleted, but unassigned from this class.`)) return;

                try {
                    btnEl.disabled = true;
                    await api.deleteClass(id);
                    await loadDashboardData();
                    window.dispatchEvent(new CustomEvent('classesUpdated'));
                } catch (err) {
                    alert('Error deleting class: ' + (err.data?.message || 'Unknown error'));
                    btnEl.disabled = false;
                }
            });
        });
    } catch (e) {
        console.error('Failed to load classes:', e);
        tbody.innerHTML = '';
        emptyState.textContent = 'Error loading classes.';
        emptyState.classList.remove('hidden');
    }
};

const openClassDetails = async (className, studentCount) => {
    const modal = document.getElementById('class-details-modal');
    const titleEl = document.getElementById('modal-class-name');
    const countEl = document.getElementById('modal-class-count');
    const tbody = document.querySelector('#modal-students-table tbody');
    const emptyState = document.getElementById('modal-students-empty');
    const table = document.getElementById('modal-students-table');

    if (!modal || !titleEl || !countEl || !tbody || !emptyState || !table) return;

    currentModalClassName = className;
    titleEl.textContent = className;
    countEl.textContent = `${studentCount || 0} Enrolled`;

    // Show loading indicator
    table.classList.remove('hidden');
    emptyState.classList.add('hidden');
    tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; padding: 2rem; color: var(--text-muted);">Loading enrolled students...</td></tr>`;
    modal.classList.remove('hidden');

    try {
        const res = await api.getPeople('student', className);
        const students = res.people || [];

        countEl.textContent = `${students.length} Enrolled`;

        if (students.length === 0) {
            tbody.innerHTML = '';
            table.classList.add('hidden');
            emptyState.textContent = `No students enrolled in "${className}" yet.`;
            emptyState.classList.remove('hidden');
            return;
        }

        table.classList.remove('hidden');
        emptyState.classList.add('hidden');
        tbody.innerHTML = '';

        students.forEach((s, idx) => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="color: var(--text-muted); font-weight: 600;">${idx + 1}</td>
                <td><strong>${escapeHtml(s.name)}</strong></td>
                <td><span class="badge roll-badge">${escapeHtml(s.person_id || '—')}</span></td>
                <td style="color: var(--text-muted); font-size: 0.88rem;">${formatDate(s.created_at)}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error('Failed to load students for class:', err);
        tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--danger); padding: 1.5rem;">Failed to load students for this class.</td></tr>`;
    }
};
