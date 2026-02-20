"""Email notification service using SMTP with a local terminal simulated fallback."""

import asyncio
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging

from app.config import settings

logger = logging.getLogger(__name__)

SMTP_SERVER = settings.SMTP_SERVER
SMTP_PORT = settings.SMTP_PORT
SMTP_USERNAME = settings.SMTP_USERNAME
SMTP_PASSWORD = settings.SMTP_PASSWORD

HTML_TEMPLATE_BASE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: 'Inter', -apple-system, sans-serif; background-color: #f8f9fa; color: #333; margin: 0; padding: 0; }
        .container { max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
        .header { background: #0d6efd; padding: 30px 40px; text-align: center; }
        .header h1 { color: #ffffff; margin: 0; font-size: 24px; letter-spacing: -0.5px; }
        .content { padding: 40px; line-height: 1.6; }
        .content p { margin: 0 0 16px 0; }
        .message-box { background: #f8f9fa; border-left: 4px solid #6c757d; padding: 16px 20px; font-style: italic; color: #495057; margin-bottom: 24px; border-radius: 0 8px 8px 0; }
        .button-wrap { text-align: center; margin-top: 30px; }
        .btn { display: inline-block; background: #0d6efd; color: #ffffff; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: 600; text-transform: uppercase; font-size: 14px; letter-spacing: 0.5px; }
        .footer { background: #f1f3f5; padding: 20px; text-align: center; color: #6c757d; font-size: 13px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>N.E.S.T</h1>
        </div>
        <div class="content">
            {body}
        </div>
        <div class="footer">
            <p>You received this email because you are a registered user of N.E.S.T.</p>
        </div>
    </div>
</body>
</html>
"""

def _send_email_sync(recipient_email: str, subject: str, html_body: str):
    """Synchronous function to actually send or simulate the email."""
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        # Fallback Simulation
        print("\n" + "="*60)
        print(f"📧 SIMULATED EMAIL TO: {recipient_email}")
        print(f"📧 SUBJECT: {subject}")
        print(f"📧 CONTENT:\n{html_body}")
        print("="*60 + "\n")
        logger.info(f"Simulated email sent to {recipient_email}")
        return

    # Real SMTP Dispatch
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"N.E.S.T <{SMTP_USERNAME}>"
    msg["To"] = recipient_email

    part_html = MIMEText(html_body, "html")
    msg.attach(part_html)

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        logger.info(f"Real email successfully sent to {recipient_email}")
    except Exception as e:
        logger.error(f"Failed to send real email to {recipient_email}: {e}")
        # Print fallback so we don't lose the message during debugging
        print(f"FAILED EMAIL TO {recipient_email}: {e}")

async def send_invitation_email(recipient_email: str, team_name: str, lead_name: str, message: str = None):
    """Notify a user they have been invited to a team."""
    subject = f"You've been invited to join team {team_name}!"
    
    body = f"""
    <h2>Hello,</h2>
    <p>Great news! <strong>{lead_name}</strong> has invited you to join their team: <strong>{team_name}</strong>.</p>
    """
    
    if message:
        body += f'<div class="message-box">"{message}"<br><br>— {lead_name}</div>'
        
    body += """
    <p>Log into N.E.S.T to view your pending invitations and respond.</p>
    <div class="button-wrap">
        <a href="http://127.0.0.1:8000/teams/invitations" class="btn">View Invitation</a>
    </div>
    """
    
    html = HTML_TEMPLATE_BASE.replace("{body}", body)
    
    # Run synchronous SMTP in a threadpool to avoid blocking FastAPI event loop
    await asyncio.to_thread(_send_email_sync, recipient_email, subject, html)


async def send_join_request_email(recipient_email: str, team_name: str, requester_name: str, message: str = None):
    """Notify a Team Lead that a user wants to join their team."""
    subject = f"New join request for team {team_name}"
    
    body = f"""
    <h2>Hello,</h2>
    <p><strong>{requester_name}</strong> has requested to join your team: <strong>{team_name}</strong>.</p>
    """
    
    if message:
        body += f'<div class="message-box">"{message}"<br><br>— {requester_name}</div>'
        
    body += """
    <p>Log into N.E.S.T to review their profile and approve or decline the request.</p>
    <div class="button-wrap">
        <a href="http://127.0.0.1:8000/teams" class="btn">Review Request</a>
    </div>
    """
    
    html = HTML_TEMPLATE_BASE.replace("{body}", body)
    
    # Run synchronous SMTP in a threadpool
    await asyncio.to_thread(_send_email_sync, recipient_email, subject, html)
