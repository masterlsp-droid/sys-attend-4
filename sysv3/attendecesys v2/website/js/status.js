import { piApi as api } from './api.js';

export class StatusIndicator {
    constructor(elementId) {
        this.el = document.getElementById(elementId);
        this.interval = null;
    }

    async check(overrideConfig = null) {
        this.el.className = 'status-badge status-checking';
        this.el.textContent = 'Checking...';
        try {
            await api.health(overrideConfig);
            this.el.className = 'status-badge status-online';
            this.el.textContent = 'Pi Online';
        } catch(e) {
            this.el.className = 'status-badge status-offline';
            this.el.textContent = 'Pi Offline';
        }
    }

    startPolling(intervalMs = 10000) {
        this.check();
        this.interval = setInterval(() => this.check(), intervalMs);
    }

    stopPolling() {
        if (this.interval) clearInterval(this.interval);
    }
}
