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

#def old_action_list():
#    search_filter = dict()
#    if options.filter and options.filter != 'all':
#        search_filter['type'] = options.filter
#    projects = ksclient.get_projects(**search_filter)
#    instances = dict()
#    volumes = dict()
#
#    # Initiate Designate object
#    dc = himutils.get_client(Designate, options, logger)
#
#    # Project counter
#    count = 0
#
#    # Loop through projects
#    for project in projects:
#        project_type = project.type if hasattr(project, 'type') else '(unknown)'
#        project_admin = project.admin if hasattr(project, 'admin') else '(unknown)'
#        project_created = project.createdate if hasattr(project, 'createdate') else '(unknown)'
#        project_roles = ksclient.list_roles(project_name=project.name)
#
#        # Get Zones
#        zones = dc.list_project_zones(project.id)
#
#        # Counters
#        instances_total = 0
#        volumes_total = 0
#
#        # Get Instances
#        for region in regions:
#            # Initiate Nova object
#            nc = himutils.get_client(Nova, options, logger, region)
#
#            # Get a list of instances in project
#            instances[region] = nc.get_project_instances(project_id=project.id)
#            for i in instances[region]:
#                instances_total += 1
#
#        # Get Volumes
#        for region in regions:
#            # Initiate Cinder object
#            cc = himutils.get_client(Cinder, options, logger)
#
#            # Get a list of volumes in project
#            volumes[region] = cc.get_volumes(detailed=True, search_opts={'project_id': project.id})
#            for i in volumes[region]:
#                volumes_total += 1
#
#        # Print header for project
#        print "PROJECT: %s" % project.name
#        print '=' * 80
#
#        # Print project metadata
#        table_metadata = PrettyTable()
#        table_metadata.border = 0
#        table_metadata.header = 0
#        table_metadata.field_names = ['meta','value']
#        table_metadata.align['meta'] = 'r'
#        table_metadata.align['value'] = 'l'
#        table_metadata.add_row(['ID:', project.id])
#        table_metadata.add_row(['Admin:', project_admin])
#        table_metadata.add_row(['Type:', project_type])
#        table_metadata.add_row(['Created:', project_created])
#        table_metadata.add_row(['Description:', project.description])
#        if len(project_roles) > 0:
#            users = []
#            for role in project_roles:
#                user = role['group'].replace('-group', '')
#                users.append(user)
#            table_metadata.add_row(['Users:', "\n".join(users)])
#        print(table_metadata)
#
#        # Print Zones table
#        if len(zones) > 0:
#            table_zones = PrettyTable()
#            table_zones.field_names = ['id', 'name']
#            table_zones.align['id'] = 'l'
#            table_zones.align['name'] = 'l'
#            for zone in zones:
#                table_zones.add_row([zone['id'], zone['name']])
#            print "\n  Zones (%d): " % len(zones)
#            print(table_zones)
#
#        # Print Volumes table
#        if volumes_total > 0:
#            table_volumes = PrettyTable()
#            table_volumes.field_names = ['id', 'size', 'region']
#            table_volumes.align['id'] = 'l'
#            table_volumes.align['size'] = 'r'
#            table_volumes.align['region'] = 'l'
#            for region in regions:
#                for volume in volumes[region]:
#                    table_volumes.add_row([volume.id, "%d GiB" % volume.size, region])
#            print "\n  Volumes (%d): " % volumes_total
#            print(table_volumes)
#
#        # Print Instances table
#        if instances_total > 0:
#            table_instances = PrettyTable()
#            table_instances.field_names = ['id', 'name', 'region', 'flavor', 'image (status)']
#            table_instances.align['id'] = 'l'
#            table_instances.align['name'] = 'l'
#            table_instances.align['region'] = 'l'
#            table_instances.align['flavor'] = 'l'
#            table_instances.align['image (status)'] = 'l'
#            for region in regions:
#                # Initiate Glance object
#                gc = himutils.get_client(Glance, options, logger)
#                for i in instances[region]:
#                    filters = {'id': i.image['id']}
#                    image = gc.find_image(filters=filters, limit=1)
#                    if len(image) == 1:
#                        image_name = image[0]['name']
#                        image_status = image[0]['status']
#                    else:
#                        image_name = '(unknown)'
#                        image_status = '(unknown)'
#                    row = []
#                    row.append(i.id)
#                    row.append(i.name)
#                    row.append(region)
#                    row.append(i.flavor["original_name"])
#                    row.append("%s (%s)" % (image_name, image_status))
#                    table_instances.add_row(row)
#            print "\n  Instances (%d): " % instances_total
#            print(table_instances)
#
#        # Print some vertical space and increase project counter
#        print "\n\n"
#        count += 1
#
#    # Finally print out number of projects
#    printer.output_dict({'header': 'Project list count', 'count': count})

def action_show():
    project = ksclient.get_project_by_name(project_name=options.project)
    if not project:
        himutils.sys_error('No project found with name %s' % options.project)
    __print_metadata(project)
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
        __print_zones(project)
        __print_volumes(project)
        __print_instances(project)

        # Print some vertical space and increase project counter
        print "\n\n"
        count += 1

    # Finally print out number of projects
    printer.output_dict({'header': 'Project list count', 'count': count})

def __print_metadata(project):
    project_type = project.type if hasattr(project, 'type') else '(unknown)'
    project_admin = project.admin if hasattr(project, 'admin') else '(unknown)'
    project_created = project.createdate if hasattr(project, 'createdate') else '(unknown)'
    project_roles = ksclient.list_roles(project_name=project.name)

    # Print header for project
    print "PROJECT: %s" % project.name
    print '=' * 80

    # Print project metadata
    table_metadata = PrettyTable()
    table_metadata.border = 0
    table_metadata.header = 0
    table_metadata.field_names = ['meta','value']
    table_metadata.align['meta'] = 'r'
    table_metadata.align['value'] = 'l'
    table_metadata.add_row(['ID:', project.id])
    table_metadata.add_row(['Admin:', project_admin])
    table_metadata.add_row(['Type:', project_type])
    table_metadata.add_row(['Created:', project_created])
    table_metadata.add_row(['Description:', project.description])
    if len(project_roles) > 0:
        users = []
        for role in project_roles:
            user = role['group'].replace('-group', '')
            users.append(user)
        table_metadata.add_row(['Users:', "\n".join(users)])
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

def __print_volumes(project):
    volumes_total = 0
    volumes = dict()

    # Get Volumes
    for region in regions:
        # Initiate Cinder object
        cc = himutils.get_client(Cinder, options, logger)

        # Get a list of volumes in project
        volumes[region] = cc.get_volumes(detailed=True, search_opts={'project_id': project.id})
        for i in volumes[region]:
            volumes_total += 1

    # Print Volumes table
    if volumes_total > 0:
        table_volumes = PrettyTable()
        table_volumes.field_names = ['id', 'size', 'region']
        table_volumes.align['id'] = 'l'
        table_volumes.align['size'] = 'r'
        table_volumes.align['region'] = 'l'
        for region in regions:
            for volume in volumes[region]:
                table_volumes.add_row([volume.id, "%d GiB" % volume.size, region])
        print "\n  Volumes (%d): " % volumes_total
        print(table_volumes)

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
        table_instances.field_names = ['id', 'name', 'region', 'flavor', 'image (status)']
        table_instances.align['id'] = 'l'
        table_instances.align['name'] = 'l'
        table_instances.align['region'] = 'l'
        table_instances.align['flavor'] = 'l'
        table_instances.align['image (status)'] = 'l'
        for region in regions:
            # Initiate Glance object
            gc = himutils.get_client(Glance, options, logger)
            for i in instances[region]:
                if 'id' not in i.image:
                    image_name = 'N/A'
                    image_status = 'N/A'
                else:
                    filters = {'id': i.image['id']}
                    image = gc.find_image(filters=filters, limit=1)
                    if len(image) == 1:
                        image_name = image[0]['name']
                        image_status = image[0]['status']
                    else:
                        image_name = 'N/A'
                        image_status = 'N/A'
                row = []
                row.append(i.id)
                row.append(i.name)
                row.append(region)
                row.append(i.flavor["original_name"])
                row.append("%s (%s)" % (image_name, image_status))
                table_instances.add_row(row)
        print "\n  Instances (%d): " % instances_total
        print(table_instances)


# Run local function with the same name as the action (Note: - => _)
action = locals().get('action_' + options.action.replace('-', '_'))
if not action:
    himutils.sys_error("Function action_%s() not implemented" % options.action)
action()
