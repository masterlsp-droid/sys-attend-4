import { initSettingsUI } from './settings.js';
import { StatusIndicator } from './status.js';
import { initDashboard, loadDashboardData } from './dashboard.js';
import { initEnrollment, populateClassesDropdown, startCamera, stopCamera } from './enrollment.js';
import { initReports, startLivePolling, stopLivePolling } from './reports.js';
import { piApi } from './api.js';

document.addEventListener('DOMContentLoaded', () => {
    // Tab switching
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            btn.classList.add('active');
            const tabId = `tab-${btn.dataset.tab}`;
            const targetEl = document.getElementById(tabId);
            if (targetEl) targetEl.classList.add('active');

            if (btn.dataset.tab === 'dashboard') {
                stopCamera();
                stopLivePolling();
                loadDashboardData();
            } else if (btn.dataset.tab === 'enrollment') {
                populateClassesDropdown();
                startCamera();
                stopLivePolling();
            } else if (btn.dataset.tab === 'reports') {
                stopCamera();
                startLivePolling();
            }
        });
    });

    const statusObj = new StatusIndicator('pi-status');
    
    // Settings
    initSettingsUI(
        () => statusObj.check(), // onSave
        (url, key) => piApi.health({ piAddress: url, apiKey: key }) // onTest
    );

    // Initial check
    statusObj.startPolling(10000);

    // Init views
    initDashboard();
    initEnrollment();
    initReports();
    
    import('./people.js').then(m => m.initPeopleList());
});

// Handle Page Visibility for Reports polling
document.addEventListener('visibilitychange', () => {
    const activeTabBtn = document.querySelector('.tab-btn.active');
    if (activeTabBtn && activeTabBtn.dataset.tab === 'reports') {
        if (document.hidden) {
            stopLivePolling();
        } else {
            startLivePolling();
        }
    }
});
