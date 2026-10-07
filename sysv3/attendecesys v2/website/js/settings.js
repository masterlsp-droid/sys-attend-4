export const getSettings = () => {
    return {
        piAddress: localStorage.getItem('piAddress') || 'http://attendance-pi.local:5000',
        apiKey: localStorage.getItem('apiKey') || ''
    };
};

export const saveSettings = (piAddress, apiKey) => {
    localStorage.setItem('piAddress', piAddress);
    localStorage.setItem('apiKey', apiKey);
};

export const initSettingsUI = (onSave, onTest) => {
    const modal = document.getElementById('settings-modal');
    const form = document.getElementById('settings-form');
    const msgBox = document.getElementById('settings-message');
    
    document.getElementById('settings-btn').addEventListener('click', () => {
        const { piAddress, apiKey } = getSettings();
        document.getElementById('pi-address').value = piAddress;
        document.getElementById('api-key').value = apiKey;
        msgBox.classList.add('hidden');
        modal.classList.remove('hidden');
    });
    
    document.getElementById('close-settings').addEventListener('click', () => {
        modal.classList.add('hidden');
    });
    
    document.getElementById('test-conn-btn').addEventListener('click', async () => {
        const url = document.getElementById('pi-address').value;
        const key = document.getElementById('api-key').value;
        try {
            await onTest(url, key);
            msgBox.textContent = 'Connection successful!';
            msgBox.className = 'message-box success';
        } catch(e) {
            msgBox.textContent = 'Connection failed: ' + (e.data?.message || 'Network Error');
            msgBox.className = 'message-box error';
        }
    });

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        saveSettings(document.getElementById('pi-address').value, document.getElementById('api-key').value);
        modal.classList.add('hidden');
        if(onSave) onSave();
    });
};
