import { formatDate, formatTime } from './utils.js';

export const generatePDF = (session) => {
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();

    doc.setFont("helvetica", "bold");
    doc.setFontSize(16);
    doc.text("Smart Attendance System", 14, 20);
    
    doc.setFontSize(12);
    doc.text(`Official Lecture Attendance Sheet - ${session.subject}`, 14, 28);
    
    doc.setFont("helvetica", "normal");
    doc.setFontSize(10);
    
    doc.text(`Subject: ${session.subject}`, 14, 40);
    doc.text(`Teacher: ${session.teacher?.name || 'N/A'}`, 100, 40);
    
    doc.text(`Start Time: ${formatDate(session.start_time)} ${formatTime(session.start_time)}`, 14, 46);
    doc.text(`End Time: ${formatDate(session.end_time)} ${formatTime(session.end_time)}`, 100, 46);
    
    doc.text(`Session ID: #${session.session_id}`, 14, 52);
    doc.text(`Total Present: ${session.total_present} students`, 100, 52);
    
    doc.text(`Status: ${session.status}`, 14, 58);

    if (!session.attendance || session.attendance.length === 0) {
        doc.text("No students recorded for this session", 14, 70);
    } else {
        const body = session.attendance.map((s, idx) => [
            idx + 1,
            s.roll_no,
            s.name,
            formatTime(s.time_recorded),
            (s.confidence || 0).toFixed(1) + '%',
            'Present'
        ]);

        doc.autoTable({
            startY: 65,
            head: [['#', 'Roll No.', 'Student Name', 'Time Recorded', 'Match Confidence', 'Status']],
            body: body,
            theme: 'grid',
            headStyles: { fillColor: [59, 130, 246] }
        });
    }

    doc.setFontSize(8);
    const dateStr = new Date().toLocaleString();
    doc.text(`Report generated automatically on ${dateStr} via Smart Attendance System.`, 14, doc.lastAutoTable ? doc.lastAutoTable.finalY + 10 : 80);

    const safeSubject = (session.subject || 'Session').replace(/[^a-z0-9]/gi, '_');
    doc.save(`Attendance_${safeSubject}_${formatDate(session.start_time)}_S${session.session_id}.pdf`);
};
