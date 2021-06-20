#!/usr/bin/env python
from himlarcli.keystone import Keystone
from himlarcli.nova import Nova
from himlarcli.cinder import Cinder
from himlarcli.designate import Designate
from himlarcli.glance import Glance
from himlarcli.parser import Parser
from himlarcli.printer import Printer
from himlarcli import utils as himutils
from prettytable import PrettyTable
import re
import sys

himutils.is_virtual_env()

parser = Parser()
parser.set_autocomplete(True)
options = parser.parse_args()
printer = Printer(options.format)

ksclient = Keystone(options.config, debug=options.debug)
ksclient.set_dry_run(options.dry_run)
ksclient.set_domain(options.domain)
logger = ksclient.get_logger()

if hasattr(options, 'region'):
    regions = ksclient.find_regions(region_name=options.region)
else:
    regions = ksclient.find_regions()

if not regions:
    himutils.sys_error('no regions found with this name!')

#---------------------------------------------------------------------
# Main functions
#---------------------------------------------------------------------
def action_show():
    project = ksclient.get_project_by_name(project_name=options.project)
    if not project:
        himutils.sys_error('No project found with name %s' % options.project)
    __print_metadata(project)
    if options.detail:
        __print images(project)
        sys.exit(0)
        __print_zones(project)
        __print_volumes(project)
        __print_instances(project)

def action_list():
    search_filter = dict()
    if options.filter and options.filter != 'all':
        search_filter['type'] = options.filter
    projects = ksclient.get_projects(**search_filter)

    # Project counter
    count = 0

    # Loop through projects
    for project in projects:
        __print_metadata(project)
        if options.detail:
            __print_zones(project)
            __print_volumes(project)
            __print_instances(project)

        # Print some vertical space and increase project counter
        print "\n\n"
        count += 1

    # Finally print out number of projects
    printer.output_dict({'header': 'Project list count', 'count': count})

def action_user():
    if not ksclient.is_valid_user(email=options.user, domain=options.domain):
        print "%s is not a valid user. Please check your spelling or case." % options.user
        sys.exit(1)
    user = ksclient.get_user_objects(email=options.user, domain=options.domain)

    # Project counter
    count = 0

    for project in user['projects']:
        if options.admin and project.admin != options.user:
            continue
        __print_metadata(project)
        if options.detail:
            __print_zones(project)
            __print_volumes(project)
            __print_instances(project)

        # Print some vertical space and increase project counter
        print "\n\n"
        count += 1

    # Finally print out number of projects
    printer.output_dict({'header': 'Project list count', 'count': count})

#---------------------------------------------------------------------
# Helper functions
#---------------------------------------------------------------------
def __print_metadata(project):
    project_type = project.type if hasattr(project, 'type') else '(unknown)'
    project_admin = project.admin if hasattr(project, 'admin') else '(unknown)'
    project_created = project.createdate if hasattr(project, 'createdate') else '(unknown)'
    project_enddate = project.enddate if hasattr(project, 'enddate') else 'None'
    project_roles = ksclient.list_roles(project_name=project.name)

    # Make project create date readable
    project_created = re.sub(r'T\d\d:\d\d:\d\d.\d\d\d\d\d\d', '', project_created)

    # Print header for project
    if hasattr(options, 'user') and not options.admin:
        prole = 'admin' if options.user == project.admin else 'member'
        print "PROJECT: %s (%s)" % (project.name, prole)
    else:
        print "PROJECT: %s" % project.name
    print '=' * 80

    # Print project metadata
    table_metadata = PrettyTable()
    table_metadata._max_width = {'value' : 70}
    table_metadata.border = 0
    table_metadata.header = 0
    table_metadata.field_names = ['meta','value']
    table_metadata.align['meta'] = 'r'
    table_metadata.align['value'] = 'l'
    table_metadata.add_row(['ID:', project.id])
    table_metadata.add_row(['Admin:', project_admin])
    table_metadata.add_row(['Type:', project_type])
    table_metadata.add_row(['Created:', project_created])
    table_metadata.add_row(['Enddate:', project_enddate])
    table_metadata.add_row(['Description:', project.description])
    if len(project_roles) > 0:
        users = dict()
        users['user'] = []
        users['object'] = []
        for role in project_roles:
            user = role['group'].replace('-group', '')
            users[role['role']].append(user)
        table_metadata.add_row(['Users:', "\n".join(users['user'])])
        if len(users['object']) > 0:
            table_metadata.add_row(['Object Users:', "\n".join(users['object'])])
    if not options.detail:
        zones     = __count_zones(project)
        volumes   = __count_volumes(project)
        instances = __count_instances(project)
        volume_list   = []
        instance_list = []
        for region in regions:
            volume_list.append("%d (%s)" % (volumes[region], region))
            instance_list.append("%d (%s)" % (instances[region], region))
        table_metadata.add_row(['Zones:', zones])
        table_metadata.add_row(['Volumes:', ', '.join(volume_list)])
        table_metadata.add_row(['Instances:', ', '.join(instance_list)])
    print(table_metadata)

def __print_zones(project):
    # Initiate Designate object
    dc = himutils.get_client(Designate, options, logger)

    # Get Zones
    zones = dc.list_project_zones(project.id)

    # Print Zones table
    if len(zones) > 0:
        table_zones = PrettyTable()
        table_zones.field_names = ['id', 'name']
        table_zones.align['id'] = 'l'
        table_zones.align['name'] = 'l'
        for zone in zones:
            table_zones.add_row([zone['id'], zone['name']])
        print "\n  Zones (%d): " % len(zones)
        print(table_zones)

def __count_zones(project):
    # Initiate Designate object
    dc = himutils.get_client(Designate, options, logger)

    # Get Zones
    zones = dc.list_project_zones(project.id)

    return len(zones)

def __print_images(project):
    images_total = 0
    images = dict()

    # Get Volumes
    for region in regions:
        # Initiate Glance object
        gc = himutils.get_client(Cinder, options, logger, region)

        # Get a list of volumes in project
        filters = {'project_id': project.id}
        image = gc.find_image(filters=filters, limit=1)
        images[region] = gc.find_image(filters=filters, limit=1)
        for i in images[region]:
            images_total += 1

    # Print Volumes table
#    if volumes_total > 0:
#        table_volumes = PrettyTable()
#        table_volumes.field_names = ['id', 'size', 'type', 'status', 'region']
#        table_volumes.align['id'] = 'l'
#        table_volumes.align['size'] = 'r'
#        table_volumes.align['type'] = 'l'
#        table_volumes.align['status'] = 'l'
#        table_volumes.align['region'] = 'l'
#        for region in regions:
#            for volume in volumes[region]:
#                table_volumes.add_row([volume.id, "%d GiB" % volume.size, volume.volume_type, volume.status, region])
#        print "\n  Volumes (%d): " % volumes_total
#        print(table_volumes)

def __count_images(project):
    volumes = dict()

    # Get Volumes
    for region in regions:
        # Initiate Cinder object
        cc = himutils.get_client(Cinder, options, logger, region)

        # Get a count of volumes in project
        volumes[region] = len(cc.get_volumes(search_opts={'project_id': project.id}))

    return volumes

def __print_volumes(project):
    volumes_total = 0
    volumes = dict()

    # Get Volumes
    for region in regions:
        # Initiate Cinder object
        cc = himutils.get_client(Cinder, options, logger, region)

        # Get a list of volumes in project
        volumes[region] = cc.get_volumes(detailed=True, search_opts={'project_id': project.id})
        for i in volumes[region]:
            volumes_total += 1

    # Print Volumes table
    if volumes_total > 0:
        table_volumes = PrettyTable()
        table_volumes.field_names = ['id', 'size', 'type', 'status', 'region']
        table_volumes.align['id'] = 'l'
        table_volumes.align['size'] = 'r'
        table_volumes.align['type'] = 'l'
        table_volumes.align['status'] = 'l'
        table_volumes.align['region'] = 'l'
        for region in regions:
            for volume in volumes[region]:
                table_volumes.add_row([volume.id, "%d GiB" % volume.size, volume.volume_type, volume.status, region])
        print "\n  Volumes (%d): " % volumes_total
        print(table_volumes)

def __count_volumes(project):
    volumes = dict()

    # Get Volumes
    for region in regions:
        # Initiate Cinder object
        cc = himutils.get_client(Cinder, options, logger, region)

        # Get a count of volumes in project
        volumes[region] = len(cc.get_volumes(search_opts={'project_id': project.id}))

    return volumes

def __print_instances(project):
    instances_total = 0
    instances = dict()

    # Get Instances
    for region in regions:
        # Initiate Nova object
        nc = himutils.get_client(Nova, options, logger, region)

        # Get a list of instances in project
        instances[region] = nc.get_project_instances(project_id=project.id)
        for i in instances[region]:
            instances_total += 1

    # Print Instances table
    if instances_total > 0:
        table_instances = PrettyTable()
        table_instances.field_names = ['id', 'name', 'IPv4', 'IPv6',  'region', 'flavor', 'image [status]']
        table_instances.align['id'] = 'l'
        table_instances.align['name'] = 'l'
        table_instances.align['IPv4'] = 'l'
        table_instances.align['IPv6'] = 'l'
        table_instances.align['region'] = 'l'
        table_instances.align['flavor'] = 'l'
        table_instances.align['image [status]'] = 'l'
        for region in regions:
            # Initiate Glance object
            gc = himutils.get_client(Glance, options, logger, region)
            for i in instances[region]:
                network = i.addresses.keys()[0] if len(i.addresses.keys()) > 0 else 'unknown'
                ipv4_list = []
                ipv6_list = []
                for interface in i.addresses[network]:
                    if interface['version'] == 4:
                        ipv4_list.append(interface['addr'])
                    if interface['version'] == 6:
                        ipv6_list.append(interface['addr'])
                ipv4_addresses = ", ".join(ipv4_list)
                ipv6_addresses = ", ".join(ipv6_list)
                if 'id' not in i.image:
                    image_name = 'UNKNOWN'
                    image_status = 'N/A'
                else:
                    filters = {'id': i.image['id']}
                    image = gc.find_image(filters=filters, limit=1)
                    if len(image) == 1:
                        image_name = image[0]['name']
                        image_status = image[0]['status']
                    else:
                        image_name = 'UNKNOWN'
                        image_status = 'N/A'
                row = []
                row.append(i.id)
                row.append(i.name)
                row.append(ipv4_addresses)
                row.append(ipv6_addresses)
                row.append(region)
                row.append(i.flavor["original_name"])
                row.append("%s [%s]" % (image_name, image_status))
                table_instances.add_row(row)
        print "\n  Instances (%d): " % instances_total
        print(table_instances)

def __count_instances(project):
    instances = dict()

    # Get Instances
    for region in regions:
        # Initiate Nova object
        nc = himutils.get_client(Nova, options, logger, region)

        # Get a list of instances in project
        instances[region] = len(nc.get_project_instances(project_id=project.id))

    return instances


#=====================================================================
# Main program
#=====================================================================
# Run local function with the same name as the action (Note: - => _)
action = locals().get('action_' + options.action.replace('-', '_'))
if not action:
    himutils.sys_error("Function action_%s() not implemented" % options.action)
action()
