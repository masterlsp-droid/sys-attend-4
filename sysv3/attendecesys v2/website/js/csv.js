import { formatDate, formatTime } from './utils.js';

export const generateCSV = (session) => {
    const BOM = "\uFEFF";
    const headerRow = ["session_id", "subject", "teacher", "date", "start_time", "end_time", "total_present", "sr_no", "roll_no", "student_name", "time_recorded", "match_confidence", "status"];
    
    const escapeCSV = (val) => {
        if (val === null || val === undefined) return '""';
        let str = String(val);
        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
            str = '"' + str.replace(/"/g, '""') + '"';
        }
        return str;
    };

    const common = [
        session.session_id,
        session.subject,
        session.teacher?.name,
        formatDate(session.start_time),
        formatTime(session.start_time),
        formatTime(session.end_time),
        session.total_present
    ].map(escapeCSV);

    let rows = [headerRow.join(',')];

    if (!session.attendance || session.attendance.length === 0) {
        rows.push([...common, "", "", "", "", "", ""].join(','));
    } else {
        session.attendance.forEach((s, idx) => {
            const studentData = [
                idx + 1,
                s.roll_no,
                s.name,
                formatTime(s.time_recorded),
                (s.confidence || 0).toFixed(1) + '%',
                "Present"
            ].map(escapeCSV);
            rows.push([...common, ...studentData].join(','));
        });
    }

    const csvContent = BOM + rows.join("\r\n");
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    
    const link = document.createElement("a");
    link.setAttribute("href", url);
    const safeSubject = (session.subject || 'Session').replace(/[^a-z0-9]/gi, '_');
    link.setAttribute("download", `Attendance_${safeSubject}_${formatDate(session.start_time)}_S${session.session_id}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
};
