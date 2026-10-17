from email.message import EmailMessage
import aiosmtplib
from fastapi.templating import Jinja2Templates
from config import settings

templates = Jinja2Templates(directory="templates")

async def send_email(
    to_email: str,
    subject: str,
    plain_body: str,
    html_body: str | None = None
) -> None:
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to_email
    message["Subject"] = subject

    message.set_content(plain_body)

    if html_body:
        message.add_alternative(html_body, subtype="html")
    
    try:
        async with aiosmtplib.SMTP(
            hostname=settings.mail_server,
            port=settings.mail_port,
            username=settings.mail_username,
            password=settings.mail_password.get_secret_value() or None,
            start_tls=settings.mail_use_tls
        ) as smtp:
            
            await smtp.send_message(message)

        print(f"Email sent to {to_email}")

    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
    

async def send_password_reset_email(to_email: str, user_name: str, token: str ) -> None:
    reset_url = f"{settings.frontend_url}/reset-password?token={token}"

    template = templates.env.get_template("email/password_reset.html")
    html_content = template.render(reset_url=reset_url, username=user_name)

    plain_text = f"""Hi {user_name}
    You requested a password reset. Click the link to reset it:

    {reset_url}
    
    The link will expire in {settings.reset_token_expire_minutes} minutes.

    If you did not request this, please ignore this email.

    Thanks,
    FastAPI Blog Team.
    """

    await send_email(
        to_email=to_email,
        subject="Reset your password", 
        plain_body=plain_text, 
        html_body=html_content
    )
    
