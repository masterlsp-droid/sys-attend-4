import { backendApi, piApi } from './api.js';
import { Camera } from './camera.js';
import { escapeHtml } from './utils.js';

let camera;
let capturedBlobs = [];

export const populateClassesDropdown = async () => {
    const select = document.getElementById('enroll-class');
    const hint = document.getElementById('no-classes-hint');
    if (!select) return;

    try {
        const res = await backendApi.getClasses();
        const classes = res.classes || [];
        
        const currentVal = select.value;
        select.innerHTML = '<option value="" disabled selected>-- Select Class / Division --</option>';
        
        if (classes.length === 0) {
            if (hint) hint.classList.remove('hidden');
            const opt = document.createElement('option');
            opt.value = "";
            opt.textContent = "No classes available (Create one in Dashboard)";
            opt.disabled = true;
            select.appendChild(opt);
        } else {
            if (hint) hint.classList.add('hidden');
            classes.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c.name;
                opt.textContent = `${c.name} (${c.student_count || 0} enrolled)`;
                if (c.name === currentVal) opt.selected = true;
                select.appendChild(opt);
            });
        }
    } catch (e) {
        console.error('Failed to load classes for dropdown:', e);
    }
};

export const initEnrollment = () => {
    const videoEl = document.getElementById('webcam');
    camera = new Camera(videoEl);
    
    populateClassesDropdown();
    window.addEventListener('classesUpdated', populateClassesDropdown);

    document.getElementById('goto-dashboard-link')?.addEventListener('click', (e) => {
        e.preventDefault();
        document.querySelector('.tab-btn[data-tab="dashboard"]')?.click();
    });
    
    const roleRadios = document.querySelectorAll('input[name="role"]');
    const classGroup = document.getElementById('class-select-group');
    const classSelect = document.getElementById('enroll-class');
    const subjectGroup = document.getElementById('subject-group');
    const personIdLabel = document.getElementById('person-id-label');
    const personIdInput = document.getElementById('person_id');
    const subjectInput = document.getElementById('subject');
    
    roleRadios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            if (e.target.value === 'teacher') {
                subjectGroup.classList.remove('hidden');
                subjectInput.required = true;
                personIdLabel.textContent = 'Employee ID';
                personIdInput.placeholder = 'e.g. T01';
                if (classSelect) classSelect.required = false;
                if (classGroup) classGroup.classList.add('hidden');
            } else {
                subjectGroup.classList.add('hidden');
                subjectInput.required = false;
                personIdLabel.textContent = 'Roll No';
                personIdInput.placeholder = 'e.g. 101';
                if (classSelect) classSelect.required = true;
                if (classGroup) classGroup.classList.remove('hidden');
            }
        });
    });

    const captureBtn = document.getElementById('capture-btn');
    const thumbnailsDiv = document.getElementById('thumbnails');
    const submitBtn = document.getElementById('submit-enrollment');
    const msgBox = document.getElementById('enroll-message');

    captureBtn.addEventListener('click', async () => {
        captureBtn.textContent = 'Capturing...';
        captureBtn.disabled = true;
        msgBox.classList.add('hidden');
        
        try {
            capturedBlobs = await camera.captureFrames(3, 200);
            
            thumbnailsDiv.innerHTML = '';
            capturedBlobs.forEach(blob => {
                const img = document.createElement('img');
                img.src = URL.createObjectURL(blob);
                thumbnailsDiv.appendChild(img);
            });
            thumbnailsDiv.classList.remove('hidden');
            submitBtn.disabled = false;
            captureBtn.textContent = 'Retake';
        } catch (e) {
            msgBox.textContent = 'Camera error: ' + e.message;
            msgBox.className = 'message-box error';
            msgBox.classList.remove('hidden');
            captureBtn.textContent = 'Capture Face';
        }
        captureBtn.disabled = false;
    });

    document.getElementById('enrollment-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        if (capturedBlobs.length === 0) return;

        submitBtn.disabled = true;
        submitBtn.textContent = 'Enrolling...';
        msgBox.classList.add('hidden');

        const role = document.querySelector('input[name="role"]:checked').value;
        const className = document.getElementById('enroll-class')?.value || '';

        if (role === 'student' && !className) {
            msgBox.textContent = 'Please select a Class / Division before enrolling.';
            msgBox.className = 'message-box error';
            msgBox.classList.remove('hidden');
            submitBtn.disabled = false;
            submitBtn.textContent = 'Enroll';
            return;
        }

        const formData = new FormData();
        formData.append('role', role);
        formData.append('name', document.getElementById('name').value.trim());
        formData.append('person_id', document.getElementById('person_id').value.trim());
        if (role === 'student' && className) {
            formData.append('class_name', className);
        }
        if (role === 'teacher') {
            formData.append('subject', document.getElementById('subject').value.trim());
        }
        capturedBlobs.forEach(blob => formData.append('images', blob, 'face.jpg'));

        try {
            const startData = {
                role: formData.get('role'),
                name: formData.get('name'),
                person_id: formData.get('person_id')
            };
            if (role === 'student' && className) {
                startData.class_name = className;
            }
            if (formData.get('role') === 'teacher') {
                startData.subject = formData.get('subject');
            }
            
            const startRes = await backendApi.enrollStart(startData);
            formData.append('enrollment_token', startRes.enrollment_token);
            
            const piRes = await piApi.embed(formData);
            
            msgBox.textContent = `Enrolled successfully: ${piRes.name || formData.get('name')}${className ? ' (' + className + ')' : ''}`;
            msgBox.className = 'message-box success';
            document.getElementById('enrollment-form').reset();
            thumbnailsDiv.innerHTML = '';
            thumbnailsDiv.classList.add('hidden');
            capturedBlobs = [];
            
            // Refresh people list and dashboard stats
            const { loadPeople } = await import('./people.js');
            loadPeople();
            window.dispatchEvent(new CustomEvent('classesUpdated'));
            
            if (document.querySelector('input[name="role"]:checked').value === 'teacher') {
                subjectGroup.classList.remove('hidden');
                if (classGroup) classGroup.classList.add('hidden');
            } else {
                subjectGroup.classList.add('hidden');
                if (classGroup) classGroup.classList.remove('hidden');
            }
        } catch (err) {
            const errorMsg = err.data?.detail?.message || err.data?.message || 'Enrollment failed';
            msgBox.textContent = escapeHtml(errorMsg);
            msgBox.className = 'message-box error';
        }
        msgBox.classList.remove('hidden');
        submitBtn.disabled = false;
        submitBtn.textContent = 'Enroll';
    });
};

export const startCamera = () => {
    if (camera) camera.start().catch(e => {
        const msgBox = document.getElementById('enroll-message');
        msgBox.textContent = 'Could not start camera: ' + e.message;
        msgBox.className = 'message-box error';
        msgBox.classList.remove('hidden');
    });
};

export const stopCamera = () => {
    if (camera) camera.stop();
};
