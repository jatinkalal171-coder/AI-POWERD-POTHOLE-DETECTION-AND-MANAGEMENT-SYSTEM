import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import os
from backend.config import SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, MUNICIPALITY_EMAIL

def send_email_alert(to_email, subject, body_html, attachment_path=None):
    """
    Send an HTML email with optional attachment. If SMTP credentials are not set,
    log the notification safely without crashing.
    """
    recipient = to_email or MUNICIPALITY_EMAIL

    if not SMTP_USERNAME or not SMTP_PASSWORD:
        print(f"[EMAIL SIMULATION] Subject: '{subject}' -> Sent to: {recipient}")
        print(f"[EMAIL BODY]:\n{body_html[:200]}...")
        return True

    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USERNAME
        msg['To'] = recipient
        msg['Subject'] = subject

        msg.attach(MIMEText(body_html, 'html'))

        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                attach = MIMEApplication(f.read(), _subtype="pdf")
                attach.add_header('Content-Disposition', 'attachment', filename=os.path.basename(attachment_path))
                msg.attach(attach)

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"[SUCCESS] Email sent successfully to {recipient}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send email alert: {e}")
        return False
