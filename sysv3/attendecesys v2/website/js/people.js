import { backendApi as api } from './api.js';
import { escapeHtml } from './utils.js';

export const initPeopleList = () => {
    const roleRadios = document.querySelectorAll('input[name="list-role"]');
    roleRadios.forEach(r => r.addEventListener('change', loadPeople));
    
    // Initial load
    loadPeople();
};

export const loadPeople = async () => {
    const role = document.querySelector('input[name="list-role"]:checked').value;
    const listEl = document.getElementById('people-list');
    
    try {
        listEl.innerHTML = '<li>Loading...</li>';
        const data = await api.getPeople(role);
        listEl.innerHTML = '';
        
        if (!data.people || data.people.length === 0) {
            listEl.innerHTML = '<li>No people found.</li>';
            return;
        }
        
        data.people.forEach(p => {
            const li = document.createElement('li');
            li.style.display = 'flex';
            li.style.justifyContent = 'space-between';
            li.style.alignItems = 'center';
            
            const info = document.createElement('div');
            info.style.display = 'flex';
            info.style.alignItems = 'center';
            info.style.gap = '0.5rem';
            info.style.flexWrap = 'wrap';

            let detailsHtml = `<strong>${escapeHtml(p.name)}</strong> <span class="text-muted">(${escapeHtml(p.person_id)})</span>`;
            if (p.class_name) {
                detailsHtml += ` <span class="badge class-badge">${escapeHtml(p.class_name)}</span>`;
            }
            if (p.subject) {
                detailsHtml += ` <span class="badge subject-badge">${escapeHtml(p.subject)}</span>`;
            }
            info.innerHTML = detailsHtml;
            
            const delBtn = document.createElement('button');
            delBtn.className = 'btn danger-btn';
            delBtn.style.padding = '4px 8px';
            delBtn.textContent = 'Delete';
            delBtn.onclick = async () => {
                if (!confirm(`Delete ${p.name}?`)) return;
                try {
                    await api.deletePerson(role, p.person_id);
                    loadPeople();
                } catch (e) {
                    alert('Error deleting person: ' + (e.data?.message || 'Unknown error'));
                }
            };
            
            li.appendChild(info);
            li.appendChild(delBtn);
            listEl.appendChild(li);
        });
    } catch (e) {
        listEl.innerHTML = '<li>Error loading people.</li>';
    }
};
