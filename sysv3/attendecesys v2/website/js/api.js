import { getSettings } from './settings.js';

const request = async (url, options = {}, headers = {}) => {
    if (options.body && !(options.body instanceof FormData) && !headers['Content-Type']) {
        headers['Content-Type'] = 'application/json';
    }

    const timeout = options.timeout || 8000;
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);

    try {
        const response = await fetch(url, {
            ...options,
            headers,
            signal: controller.signal
        });
        clearTimeout(id);
        
        let data;
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.indexOf("application/json") !== -1) {
            data = await response.json();
        } else {
            data = { message: await response.text() };
        }
        
        if (!response.ok) {
            throw { status: response.status, data: data || { error: 'UNKNOWN', message: 'An unknown error occurred' } };
        }
        return data;
    } catch (err) {
        clearTimeout(id);
        if (err.name === 'AbortError') throw { status: 408, data: { error: 'TIMEOUT', message: 'Request timed out' } };
        if (err.status) throw err;
        throw { status: 0, data: { error: 'NETWORK_ERROR', message: 'Cannot reach server' } };
    }
};

export const backendApi = {
    health: () => request('/api/health'),
    enrollStart: (data) => request('/api/enroll/start', { method: 'POST', body: JSON.stringify(data) }),
    currentSession: () => request('/api/current-session'),
    stopSession: () => request('/api/current-session/stop', { method: 'POST' }),
    sessionsHistory: (params) => {
        const qs = new URLSearchParams(params).toString();
        return request(`/api/sessions-history?${qs}`);
    },
    sessionDetails: (id) => request(`/api/sessions-history/${id}`),
    deleteSession: (id) => request(`/api/sessions-history/${id}`, { method: 'DELETE' }),
    getClasses: () => request('/api/classes'),
    createClass: (data) => request('/api/classes', { method: 'POST', body: JSON.stringify(data) }),
    deleteClass: (id) => request(`/api/classes/${id}`, { method: 'DELETE' }),
    getDashboardStats: () => request('/api/dashboard-stats'),
    getPeople: (role, className = null) => {
        let qs = `role=${role}`;
        if (className) qs += `&class_name=${encodeURIComponent(className)}`;
        return request(`/api/people?${qs}`);
    },
    deletePerson: (role, id) => request(`/api/people/${role}/${id}`, { method: 'DELETE' })
};

export const piApi = {
    health: (overrideConfig = null) => {
        const { piAddress, apiKey } = overrideConfig || getSettings();
        const headers = apiKey ? { 'X-API-Key': apiKey } : {};
        return request(`${piAddress}/api/health`, {}, headers);
    },
    embed: (formData) => {
        const { piAddress, apiKey } = getSettings();
        const headers = apiKey ? { 'X-API-Key': apiKey } : {};
        return request(`${piAddress}/api/embed`, { 
            method: 'POST', 
            body: formData,
            timeout: 30000 
        }, headers);
    },
    attendance: (data) => {
        // Send attendance to backend via pi routes
        return request(`/api/pi/attendance`, {
            method: 'POST',
            body: JSON.stringify(data),
            timeout: 10000
        });
    }
};
