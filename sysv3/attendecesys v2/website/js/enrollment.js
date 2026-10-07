import { backendApi, piApi } from './api.js';
import { Camera } from './camera.js';
import { escapeHtml } from './utils.js';

let camera;
let capturedBlobs = [];

export const initEnrollment = () => {
    const videoEl = document.getElementById('webcam');
    camera = new Camera(videoEl);
    
    const roleRadios = document.querySelectorAll('input[name="role"]');
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
            } else {
                subjectGroup.classList.add('hidden');
                subjectInput.required = false;
                personIdLabel.textContent = 'Roll No';
                personIdInput.placeholder = 'e.g. 101';
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

        const formData = new FormData();
        formData.append('role', document.querySelector('input[name="role"]:checked').value);
        formData.append('name', document.getElementById('name').value.trim());
        formData.append('person_id', document.getElementById('person_id').value.trim());
        if (formData.get('role') === 'teacher') {
            formData.append('subject', document.getElementById('subject').value.trim());
        }
        capturedBlobs.forEach(blob => formData.append('images', blob, 'face.jpg'));

        try {
            const startData = {
                role: formData.get('role'),
                name: formData.get('name'),
                person_id: formData.get('person_id')
            };
            if (formData.get('role') === 'teacher') {
                startData.subject = formData.get('subject');
            }
            
            const startRes = await backendApi.enrollStart(startData);
            formData.append('enrollment_token', startRes.enrollment_token);
            
            const piRes = await piApi.embed(formData);
            
            msgBox.textContent = `Enrolled successfully: ${piRes.name || formData.get('name')}`;
            msgBox.className = 'message-box success';
            document.getElementById('enrollment-form').reset();
            thumbnailsDiv.innerHTML = '';
            thumbnailsDiv.classList.add('hidden');
            capturedBlobs = [];
            
            // Refresh people list
            const { loadPeople } = await import('./people.js');
            loadPeople();
            
            if (document.querySelector('input[name="role"]:checked').value === 'teacher') {
                subjectGroup.classList.remove('hidden');
            } else {
                subjectGroup.classList.add('hidden');
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
