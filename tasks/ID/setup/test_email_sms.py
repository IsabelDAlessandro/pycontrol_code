import smtplib, ssl
from email.mime.text import MIMEText
from email.utils import formatdate

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_USER = "isabeladalessandro@gmail.com"          # the Gmail you made the App Password for
SMTP_PASS = "ebucrajsqxsrzgjm"            # 16 chars, no spaces

SMS_TO   = "9788847725@tmomail.net"          # T-Mobile SMS/MMS gateway
ALSO_TO  = "isabeladalessandro@gmail.com"            # also send to yourself for verification

body = "PyControl test: if you see this via SMS, gateway works."
msg = MIMEText(body)
msg["From"] = SMTP_USER
msg["To"]   = SMS_TO
msg["Cc"]   = ALSO_TO
msg["Date"] = formatdate(localtime=True)
msg["Subject"] = "PyControl finished"

with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ssl.create_default_context()) as s:
    s.login(SMTP_USER, SMTP_PASS)
    s.sendmail(SMTP_USER, [SMS_TO, ALSO_TO], msg.as_string())

print("Sent to SMS and email.")
