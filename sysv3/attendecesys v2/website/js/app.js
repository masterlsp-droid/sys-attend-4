import { initSettingsUI } from './settings.js';
import { StatusIndicator } from './status.js';
import { initEnrollment, startCamera, stopCamera } from './enrollment.js';
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
            document.getElementById(tabId).classList.add('active');

            if (btn.dataset.tab === 'enrollment') {
                startCamera();
                stopLivePolling();
            } else {
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
    initEnrollment();
    initReports();
    
    import('./people.js').then(m => m.initPeopleList());
    
    startCamera(); // Enrollment is default tab
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
