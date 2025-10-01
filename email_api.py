from setup import mail_config
from smtplib import SMTP_SSL
from email.mime.text import MIMEText
import datetime


def send_email(to_email, to_name, subject, body, html):
    smtp = SMTP_SSL(mail_config['url'], mail_config['port'])
    print('connected')
    smtp.login(mail_config['user'], mail_config['pass'])
    print('logged in')
    from_addr = mail_config['from']
    to_addr = f'{to_name} <{to_email}>'

    msg = MIMEText(html, 'html')
    msg['Subject'] = subject
    msg['From'] = from_addr
    try:
        smtp.sendmail(from_addr, to_addr, msg.as_string())
    finally:
        smtp.quit()
    