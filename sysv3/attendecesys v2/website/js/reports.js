import { backendApi as api, piApi } from './api.js';
import { escapeHtml, formatTime, formatDate } from './utils.js';
import { generatePDF } from './pdf.js';
import { generateCSV } from './csv.js';

let pollInterval = null;

export const initReports = () => {
    loadHistory();
    document.getElementById('filter-date').addEventListener('change', loadHistory);
    document.getElementById('filter-subject').addEventListener('input', loadHistory);
    
    document.getElementById('end-session-btn')?.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to stop the current session?')) return;
        try {
            await api.stopSession();
            alert('Session stopped.');
            document.getElementById('active-session').classList.add('hidden');
            loadHistory();
        } catch (e) {
            alert('Error stopping session: ' + (e.data?.message || 'Unknown error'));
        }
    });
};

export const startLivePolling = () => {
    pollLiveSession();
    pollInterval = setInterval(pollLiveSession, 5000);
};

export const stopLivePolling = () => {
    if (pollInterval) clearInterval(pollInterval);
};

const pollLiveSession = async () => {
    try {
        const data = await api.currentSession();
        const noSession = document.getElementById('no-session');
        const activeSession = document.getElementById('active-session');
        
        if (!data || !data.active) {
            noSession.classList.remove('hidden');
            activeSession.classList.add('hidden');
            return;
        }

        noSession.classList.add('hidden');
        activeSession.classList.remove('hidden');

        document.getElementById('live-subject').textContent = escapeHtml(data.subject);
        document.getElementById('live-teacher').textContent = escapeHtml(data.teacher?.name || '');
        document.getElementById('live-present-count').textContent = data.present_count || 0;
        
        if (data.auto_close_at) {
            const diff = new Date(data.auto_close_at) - new Date();
            if (diff > 0) {
                const m = Math.floor(diff / 60000);
                const s = Math.floor((diff % 60000) / 1000);
                document.getElementById('live-countdown').textContent = `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
            } else {
                document.getElementById('live-countdown').textContent = '00:00';
            }
        }

        const listEl = document.getElementById('live-present-list');
        listEl.innerHTML = '';
        if (data.present) {
            data.present.forEach(p => {
                const li = document.createElement('li');
                li.innerHTML = `<span>${escapeHtml(p.name)} (${escapeHtml(p.roll_no)})</span><span>${formatTime(p.time_recorded)}</span>`;
                listEl.appendChild(li);
            });
        }
    } catch(e) {
        console.error('Poll error', e);
    }
};

const loadHistory = async () => {
    const date = document.getElementById('filter-date').value;
    const subject = document.getElementById('filter-subject').value;
    const tbody = document.querySelector('#history-table tbody');
    const emptyState = document.getElementById('history-empty');

    try {
        const params = {};
        if (date) params['from_'] = date;
        if (subject) params.subject = subject;

        const data = await api.sessionsHistory(params);
        tbody.innerHTML = '';
        
        if (!data.sessions || data.sessions.length === 0) {
            emptyState.classList.remove('hidden');
            document.getElementById('history-table').classList.add('hidden');
            return;
        }

        emptyState.classList.add('hidden');
        document.getElementById('history-table').classList.remove('hidden');

        data.sessions.forEach(s => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>#${s.session_id}</td>
                <td>${formatDate(s.start_time)}</td>
                <td>${escapeHtml(s.subject)}</td>
                <td>${escapeHtml(s.teacher?.name)}</td>
                <td>${formatTime(s.start_time)}</td>
                <td>${formatTime(s.end_time)}</td>
                <td>${s.total_present || 0}</td>
                <td>
                    <div class="action-buttons">
                        <button class="btn btn-delete-report" data-id="${s.session_id}" title="Delete Report" aria-label="Delete Report">
                            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="3 6 5 6 21 6"></polyline>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                                <line x1="10" y1="11" x2="10" y2="17"></line>
                                <line x1="14" y1="11" x2="14" y2="17"></line>
                            </svg>
                        </button>
                        <button class="btn text-btn btn-pdf" data-id="${s.session_id}">PDF</button>
                        <button class="btn text-btn btn-csv" data-id="${s.session_id}">CSV</button>
                    </div>
                </td>
            `;
            tbody.appendChild(tr);
        });

        document.querySelectorAll('.btn-delete-report').forEach(btn => btn.addEventListener('click', async (e) => {
            const btnEl = e.currentTarget;
            const id = btnEl.getAttribute('data-id');
            if (!confirm(`Are you sure you want to delete session #${id} and its report?`)) return;
            try {
                btnEl.disabled = true;
                await api.deleteSession(id);
                loadHistory();
            } catch (err) {
                alert('Error deleting session: ' + (err.data?.message || 'Unknown error'));
                btnEl.disabled = false;
            }
        }));

        document.querySelectorAll('.btn-pdf').forEach(btn => btn.addEventListener('click', async (e) => {
            const id = e.currentTarget.getAttribute('data-id');
            const sessionData = await api.sessionDetails(id);
            generatePDF(sessionData);
        }));

        document.querySelectorAll('.btn-csv').forEach(btn => btn.addEventListener('click', async (e) => {
            const id = e.currentTarget.getAttribute('data-id');
            const sessionData = await api.sessionDetails(id);
            generateCSV(sessionData);
        }));
    } catch(e) {
        console.error('History load error', e);
        tbody.innerHTML = '';
        emptyState.textContent = 'Error loading history.';
        emptyState.classList.remove('hidden');
    }
};
