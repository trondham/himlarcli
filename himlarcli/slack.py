import requests
import configparser
from himlarcli import utils

class Slack:

    def __init__(self, config_path, debug=False, log=None):
        self.config_path = config_path
        self.config = utils.get_himlarcli_config(config_path)
        self.logger = utils.get_logger(__name__, self.config, debug, log)
        self.dry_run = False
        self.webhook_url = self.get_config('slack_publish', 'url')
        self.slack_user = self.get_config('slack_publish', 'user')
        self.slack_channel = self.get_config('slack_publish', 'channel')

    def set_dry_run(self, dry_run):
        self.dry_run = True if dry_run else False

    def publish_slack(self, msg, channel=None, user=None):
        if not channel:
            channel = self.slack_channel
        if not user:
            user = self.slack_user
        payload = {'channel': channel, 'username': user, 'text': msg}
        log_msg = 'Message published to %s by %s: %s' % (channel, user, msg)
        if not self.dry_run:
            response = requests.post(self.webhook_url, json=payload)
            if response.status_code != 200:
                self.logger.error('=> Slack post failed (%s): %s',
                                  response.status_code, response.text)
                return
        else:
            log_msg = 'DRY-RUN: ' + log_msg
        self.logger.debug('=> %s', log_msg)

    def get_config(self, section, option):
        try:
            return self.config.get(section, option)
        except (configparser.NoOptionError, configparser.NoSectionError):
            return None
