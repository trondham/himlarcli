from himlarcli.client import Client
from swiftclient import client as swiftclient
from swiftclient.exceptions import ClientException
import keystoneauth1.exceptions as exceptions
import re

class Swift(Client):
    """ Client for swift compatible object storage (ceph radosgw).

        Container and object operations are done directly on the object
        storage account of a project. This requires that the himlarcli user
        has the ResellerAdmin role. """

    """ Constant used to mark a class as region aware """
    USE_REGION = True

    service_type = 'object-store'

    """ Prefix for the account part of the storage url. Only used if the
        endpoint in the service catalog has no account part, and then only if
        it is set with 'object_account_prefix' in config.ini """
    account_prefix = None

    """ Number of items to fetch in each listing request """
    page_size = 1000

    """ Match the storage url from the service catalog and split it in the api
        part (base) and the account part (prefix + project id) """
    account_re = re.compile(r'^(?P<base>.*/v1(\.0)?)'
                            r'(/(?P<prefix>[^/]*?)'
                            r'(?P<project>[0-9a-f]{32}|[0-9a-f-]{36}))?$')

    def __init__(self, config_path, debug=False, log=None, region=None):
        """ Create a new swift client to manage object storage
            `**config_path`` path to ini file with config
        """
        super(Swift, self).__init__(config_path, debug, log, region)
        self.cacert = self.get_config('openstack', 'keystone_cachain')
        self.account_prefix = self.get_config('openstack',
                                              'object_account_prefix',
                                              self.account_prefix)
        self.endpoint = self.__get_endpoint()
        self.connections = dict()
        self.logged_errors = list()
        self.debug_log('use object-store endpoint %s in %s'
                       % (self.endpoint, self.region))

    def get_client(self):
        """ Return the swift connection for the project of the himlarcli user.
            Use get_connection() for the account of another project """
        return self.__new_connection(self.endpoint)

    def get_account_url(self, project_id):
        """ Return the storage url for the object storage account of a project.
            Return None if the account can not be addressed in the url. The
            account is then decided by the token alone, and we can not reach
            the object storage of another project.
            version: 2026-08 """
        if not self.endpoint:
            return None
        match = self.account_re.match(self.endpoint.rstrip('/'))
        if not match:
            self.__log_once('Swift: unknown storage url format: %s' % self.endpoint)
            return None
        # Reuse the account prefix from the catalog endpoint if it has one
        prefix = match.group('prefix')
        if prefix is None:
            prefix = self.account_prefix
        if prefix is None:
            self.__log_once('Swift: the object-store endpoint %s in %s has no '
                            'account in the url (rgw swift account in url = '
                            'false). Object storage for other projects can not '
                            'be reached, and will NOT be deleted!'
                            % (self.endpoint, self.region))
            return None
        return '%s/%s%s' % (match.group('base'), prefix, project_id)

    def get_connection(self, project_id, refresh=False):
        """ Return a swift connection to the object storage account of a
            project. Connections are cached per project.
            version: 2026-08 """
        if project_id in self.connections and not refresh:
            return self.connections[project_id]
        url = self.get_account_url(project_id)
        if not url:
            return None
        self.connections[project_id] = self.__new_connection(url)
        return self.connections[project_id]

    def get_account(self, project_id):
        """ Return usage for the object storage account of a project. Return
            None if the project has no object storage account, i.e. the project
            has never used object storage.
            version: 2026-08 """
        try:
            headers = self.__call(project_id, 'head_account')
        except ClientException as e:
            self.__log_client_exception(e, project_id, 'get account')
            return None
        if not headers:
            return None
        return {
            'containers': int(headers.get('x-account-container-count', 0)),
            'objects': int(headers.get('x-account-object-count', 0)),
            'bytes': int(headers.get('x-account-bytes-used', 0)),
        }

    def list_containers(self, project_id):
        """ Return all containers owned by a project
            version: 2026-08 """
        containers = list()
        marker = ''
        while True:
            try:
                chunk = self.__call(project_id, 'get_account',
                                    marker=marker, limit=self.page_size)
            except ClientException as e:
                self.__log_client_exception(e, project_id, 'list containers')
                return containers
            if not chunk or not chunk[1]:
                break
            containers += chunk[1]
            marker = chunk[1][-1]['name']
        return containers

    def list_objects(self, project_id, container):
        """ Return all objects in a container owned by a project
            version: 2026-08 """
        return list(self.__list_objects(project_id, container))

    def delete_container(self, project_id, container):
        """ Delete a container and all objects in it. Return the number of
            objects and bytes deleted.
            version: 2026-08 """
        result = {'objects': 0, 'bytes': 0}
        # All objects must be deleted before we can delete the container
        for obj in self.__list_objects(project_id, container):
            if self.delete_object(project_id, container, obj['name']):
                result['objects'] += 1
                result['bytes'] += int(obj.get('bytes', 0))
        self.debug_log('delete container %s in project %s (%s)'
                       % (container, project_id, self.region))
        if self.dry_run:
            return result
        try:
            self.__call(project_id, 'delete_container', container)
        except ClientException as e:
            self.__log_client_exception(e, project_id,
                                        'delete container %s' % container)
        return result

    def delete_object(self, project_id, container, name):
        """ Delete a single object. Large object manifests are deleted together
            with their segments if the object store supports it.
            version: 2026-08 """
        self.debug_log('delete object %s/%s in project %s (%s)'
                       % (container, name, project_id, self.region))
        if self.dry_run:
            return True
        # Not all swift compatible object stores (e.g. ceph radosgw) support
        # deleting a large object manifest and its segments in one request.
        # Fall back to a plain delete if the request is rejected. Orphan
        # segments are removed together with the segment container.
        for query_string in ['multipart-manifest=delete', None]:
            try:
                self.__call(project_id, 'delete_object', container, name,
                            query_string=query_string)
                return True
            except ClientException as e:
                if query_string and e.http_status in (400, 501):
                    self.debug_log('no manifest delete support, retry %s/%s'
                                   % (container, name))
                    continue
                if e.http_status != 404:
                    self.__log_client_exception(e, project_id,
                                                'delete object %s/%s' % (container, name))
                return False
        return False

    def purge_project_objects(self, project_id):
        """ Delete all containers and objects owned by a project. Return the
            number of containers, objects and bytes deleted.
            version: 2026-08 """
        result = {'containers': 0, 'objects': 0, 'bytes': 0}
        containers = self.list_containers(project_id)
        if not containers:
            return result
        # Delete segment containers last, in case a manifest in another
        # container still points to segments in them
        containers.sort(key=lambda x: x['name'].endswith('+segments'))
        for container in containers:
            deleted = self.delete_container(project_id, container['name'])
            result['containers'] += 1
            result['objects'] += deleted['objects']
            result['bytes'] += deleted['bytes']
        return result

    def __call(self, project_id, method, *args, **kwargs):
        """ Call a method on the swift connection of a project. Retry once with
            a new token if the token has expired. """
        conn = self.get_connection(project_id)
        if not conn:
            return None
        try:
            return getattr(conn, method)(*args, **kwargs)
        except ClientException as e:
            if e.http_status != 401:
                raise
            self.debug_log('token expired, reconnect to project %s' % project_id)
            conn = self.get_connection(project_id, refresh=True)
            return getattr(conn, method)(*args, **kwargs)

    def __list_objects(self, project_id, container):
        """ Generator that pages through all objects in a container """
        marker = ''
        while True:
            try:
                chunk = self.__call(project_id, 'get_container', container,
                                    marker=marker, limit=self.page_size)
            except ClientException as e:
                self.__log_client_exception(e, project_id,
                                            'list container %s' % container)
                return
            if not chunk or not chunk[1]:
                return
            for obj in chunk[1]:
                yield obj
            marker = chunk[1][-1]['name']

    def __new_connection(self, url):
        return swiftclient.Connection(preauthurl=url,
                                      preauthtoken=self.sess.get_token(),
                                      cacert=self.cacert,
                                      retries=3)

    def __log_once(self, message):
        """ Log an error only once per client, to avoid the same message for
            every project when we loop over many projects """
        if message in self.logged_errors:
            return
        self.logged_errors.append(message)
        self.log_error(message)

    def __log_client_exception(self, exception, project_id, action):
        """ A 404 means that the project has no object storage account, i.e.
            the project has never used object storage. Anything else is an
            error. """
        if exception.http_status == 404:
            self.debug_log('no object storage account for project %s in %s'
                           % (project_id, self.region))
        else:
            self.log_error('Swift: failed to %s for project %s in %s: %s'
                           % (action, project_id, self.region, exception))

    def __get_endpoint(self):
        """ Return the object-store endpoint for this region from the service
            catalog """
        try:
            endpoint = self.sess.get_endpoint(service_type=self.service_type,
                                              region_name=self.region,
                                              interface='public')
        except exceptions.EndpointNotFound:
            self.logger.debug('=> no %s endpoint in region %s',
                              self.service_type, self.region)
            return None
        return endpoint
