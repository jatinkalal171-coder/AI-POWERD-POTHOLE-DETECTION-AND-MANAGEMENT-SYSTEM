import datetime
from backend.database import get_db

def check_and_escalate_overdue_repairs():
    """
    Scans database for unresolved potholes and repairs beyond configured deadlines.
    Creates notifications and logs escalation events.
    """
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    # Fetch all active repairs with assigned deadlines
    cursor.execute('''
    SELECT r.id as repair_id, r.pothole_id, r.assigned_officer_name, r.deadline, r.assigned_date, p.priority_score, p.risk_level
    FROM repairs r
    JOIN potholes p ON r.pothole_id = p.pothole_id
    WHERE r.repair_status IN ('ASSIGNED', 'IN_PROGRESS')
    ''')
    repairs = cursor.fetchall()

    escalated_count = 0

    for rep in repairs:
        if not rep['deadline']:
            continue

        try:
            deadline_dt = datetime.datetime.strptime(rep['deadline'], "%Y-%m-%d")
        except ValueError:
            try:
                deadline_dt = datetime.datetime.strptime(rep['deadline'], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue

        days_overdue = (now - deadline_dt).days

        if days_overdue > 0:
            # Overdue detected!
            if days_overdue >= 10:
                alert_type = "CRITICAL_DELAY"
                title = f"🔴 CRITICAL DELAY: {rep['pothole_id']}"
                msg = f"Pothole {rep['pothole_id']} is severely overdue by {days_overdue} days! Escalated to Senior Executive."
            elif days_overdue >= 7:
                alert_type = "ESCALATED"
                title = f"⚠️ ESCALATED: {rep['pothole_id']}"
                msg = f"Repair order for {rep['pothole_id']} has been escalated due to 7+ days delay."
            else:
                alert_type = "OVERDUE"
                title = f"⚠️ Overdue Alert: {rep['pothole_id']}"
                msg = f"Repair deadline passed for {rep['pothole_id']} (Overdue by {days_overdue} days)."

            # Check if notification was already sent today for this repair
            cursor.execute('''
            SELECT COUNT(*) FROM notifications 
            WHERE message LIKE ? AND date(created_at) = date('now')
            ''', (f"%{rep['pothole_id']}%",))
            
            if cursor.fetchone()[0] == 0:
                cursor.execute('''
                INSERT INTO notifications (user_id, title, message, type, read_status, created_at)
                VALUES (1, ?, ?, ?, 0, ?)
                ''', (title, msg, alert_type, now_str))

                cursor.execute('''
                INSERT INTO audit_logs (user_id, user_name, action, pothole_id, details, timestamp)
                VALUES (0, 'System Escalation Engine', 'Repair Escalated', ?, ?, ?)
                ''', (rep['pothole_id'], msg, now_str))

                escalated_count += 1

    conn.commit()
    conn.close()
    return escalated_count
