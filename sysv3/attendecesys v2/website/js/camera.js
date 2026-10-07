export class Camera {
    constructor(videoElement) {
        this.video = videoElement;
        this.stream = null;
    }

    async start() {
        if (this.stream) return;
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({ 
                video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' } 
            });
            this.video.srcObject = this.stream;
            await this.video.play();
        } catch (err) {
            throw new Error('Camera access denied or unavailable.');
        }
    }

    stop() {
        if (this.stream) {
            this.stream.getTracks().forEach(t => t.stop());
            this.video.srcObject = null;
            this.stream = null;
        }
    }

    async captureFrames(count = 3, intervalMs = 200) {
        if (!this.stream) throw new Error('Camera not started');
        const frames = [];
        const canvas = document.createElement('canvas');
        canvas.width = this.video.videoWidth;
        canvas.height = this.video.videoHeight;
        const ctx = canvas.getContext('2d');

        for (let i = 0; i < count; i++) {
            ctx.drawImage(this.video, 0, 0, canvas.width, canvas.height);
            const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.85));
            frames.push(blob);
            if (i < count - 1) await new Promise(r => setTimeout(r, intervalMs));
        }
        return frames;
    }
}
