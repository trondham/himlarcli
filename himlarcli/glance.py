import sys
import itertools
import utils
from client import Client
from glanceclient import Client as glclient
from keystoneclient.v3 import client as ksclient

class Glance(Client):

    version = 2
    """ All images """
    images = None
    """ Active image """
    image = None

    def __init__(self, config_path, debug=False):
        super(Glance,self).__init__(config_path, debug)
        self.ksclient = ksclient.Client(session=self.sess)
        self.endpoint = self.__get_endpoint()
        self.client = glclient(self.version, session=self.sess)
        self.logger.debug('=> init glance client')

    def get_client(self):
        return self.client

    def get_image(self, name):
        if not self.images:
            self.__get_images()
        # Make sure we loop a new generator from the start
        self.images, image_list = itertools.tee(self.images)
        for image in image_list:
            if name == image['name']:
                self.logger.debug('=> image found %s' % name)
                self.image = image
                return image
        self.logger.debug('=> image not found %s' % name)
        return None

    def create_image(self, source_path, **kwargs):
        self.logger.debug('=> create new image %s' % kwargs['name'])
        self.image = self.client.images.create(**kwargs)
        self.upload_image(source_path)
        return self.image

    def delete_image(self):
        self.logger.debug('=> image delete %s' % self.image.name)
        self.client.images.delete(self.image.id)

    def update_image(self, **kwargs):
        if not self.image:
            self.logger.debug('=> image not found %s' % name)
            if name:
                self.get_image(name)
            else:
                self.logger.critical('Image must exist before upload.')
                sys.exit(1)
        self.client.images.update(self.image.id, **kwargs)

    def deactivate(self, name=None):
        if not self.image:
            self.logger.debug('=> image not found %s' % name)
            if name:
                self.get_image(name)
            else:
                self.logger.critical('Image must exist to deactivate.')
                sys.exit(1)
        self.client.images.deactivate(self.image.id)

    def upload_image(self, source_path, name=None):
        if not self.image:
            self.logger.debug('=> image not found %s' % name)
            if name:
                self.get_image(name)
            else:
                self.logger.critical('Image must exist before upload.')
                sys.exit(1)
        try:
            self.client.images.upload(self.image.id, open(source_path, 'rb'))
            self.logger.debug('=> upload new image %s' % source_path)
        except BaseException as e:
            print e
            self.logger.critical('Upload of %s failed' % self.image.name)
            sys.exit(1)

    def __get_endpoint(self, interface='internal'):
        if not self.ksclient:
            return
        image_services = self.ksclient.services.list(type='image')
        endpoints = self.ksclient.endpoints.list(region=self.region,
                                                interface=interface,
                                                enabled=True)
        for endpoint in endpoints:
            for service in image_services:
                if service.id == endpoint.service_id:
                    self.logger.debug("=> image internal endpoint %s" % endpoint.url)
                    return endpoint.url
        self.logger.debug("=> image endpoint not found!")

    def __get_images(self):
        self.images = self.client.images.list()
