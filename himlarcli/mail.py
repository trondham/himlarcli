from himlarcli.client import Client
import ConfigParser
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class Mail(Client):

    def __init__(self, config_path, debug=False, log=None):
        super(Mail, self).__init__(config_path, debug, log)
        self.logger.debug('=> config file: %s' % config_path)
        self.server = smtplib.SMTP(self.get_config('mail', 'smtp'), 25)
        self.server.starttls()

    def send_mail(self, toaddr, mail):
        fromaddr = self.get_config('mail', 'from_addr')
        try:
            self.server.sendmail(fromaddr, toaddr, mail)
        except smtplib.SMTPRecipientsRefused as e:
            self.log_error(e)

    def close(self):
        self.server.quit()

    def rt_mail(self, ticket, msg):
        mail = MIMEMultipart('alternative')
        mail['References'] = 'RT-Ticket-' + int(ticket) + '@uninett.no'
        mail['Subject'] = 'fixme'
        mail['From'] = 'UH-IaaS support <support@uh-iaas.no>'
        mail['Reply-To'] = 'support@uh-iaas.no'
        mail['X-RT-Owner'] = 'Nobody'
        mail['X-RT-Queue'] = 'UH-IaaS'
        mail['X-RT-Ticket'] = 'uninett.no #' + int(ticket)
        mail.attach(MIMEText(msg, 'plain', 'utf-8'))
        return mail

    def get_client(self):
        return self.client