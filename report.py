#!/usr/bin/env python
from himlarcli.keystone import Keystone
from himlarcli.nova import Nova
from himlarcli.cinder import Cinder
from himlarcli.neutron import Neutron
from himlarcli.parser import Parser
from himlarcli.printer import Printer
from himlarcli.mail import Mail
from himlarcli import utils as himutils
from datetime import datetime
from email.mime.text import MIMEText
import re

import textwrap
from himlarcli.glance import Glance
from himlarcli import utils as utils
from prettytable import PrettyTable

himutils.is_virtual_env()

parser = Parser()
parser.set_autocomplete(True)
options = parser.parse_args()
printer = Printer(options.format)
project_msg_file = 'notify/project_created.txt'
project_hpc_msg_file = 'notify/project_created_hpc.txt'
access_msg_file = 'notify/access_granted_rt.txt'
access_user_msg_file = 'notify/access_granted_user.txt'

ksclient = Keystone(options.config, debug=options.debug)
ksclient.set_dry_run(options.dry_run)
ksclient.set_domain(options.domain)
logger = ksclient.get_logger()
#novaclient = Nova(options.config, debug=options.debug, log=logger)
if hasattr(options, 'region'):
    regions = ksclient.find_regions(region_name=options.region)
else:
    regions = ksclient.find_regions()

if not regions:
    himutils.sys_error('no regions found with this name!')

def action_xlist():
    search_filter = dict()
    if options.filter and options.filter != 'all':
        search_filter['type'] = options.filter
    projects = ksclient.get_projects(**search_filter)
    instances = dict()
    count = 0
    for project in projects:
        project_type = project.type if hasattr(project, 'type') else '(unknown)'
        project_admin = project.admin if hasattr(project, 'admin') else '(unknown)'
        roles = ksclient.list_roles(project_name=project)

        instances_total = 0
        for region in regions:
            novaclient = himutils.get_client(Nova, options, logger, region)
            instances[region] = novaclient.get_project_instances(project_id=project.id)
            for i in instances[region]:
                instances_total += 1

        print "Project: %s  [%d instances]" % (project.name, instances_total)
        print "---------------------------------------------------------------------------"
        print "  ID:      %s" % project.id
        print "  Type:    %s" % project_type
        print "  Created: %s" % project.createdate
        print "  Admin:   %s" % project_admin

        if len(roles) > 0:
            print "  Users: "
            #printer.output_dict({'header': 'Roles in project %s' % project})
            for role in roles:
                printer.output_dict(role, sort=True, one_line=True)

        print "\n                 ".join(textwrap.wrap("  Description: " + project.description, 60))

        if instances_total > 0:
            print "  Instances: "
            for region in regions:
                for i in instances[region]:
                    print "             %s  %s  %s" % (i.id, region, i.name)
        print
        count += 1

    printer.output_dict({'header': 'Project list count', 'count': count})

def action_list():
    search_filter = dict()
    if options.filter and options.filter != 'all':
        search_filter['type'] = options.filter
    projects = ksclient.get_projects(**search_filter)
    instances = dict()
    gc = utils.get_client(Glance, options, logger)
    count = 0
    for project in projects:
        project_type = project.type if hasattr(project, 'type') else '(unknown)'
        project_admin = project.admin if hasattr(project, 'admin') else '(unknown)'
        project_created = project.createdate if hasattr(project, 'createdate') else '(unknown)'
        project_roles = ksclient.list_roles(project_name=project)

        instances_total = 0
        for region in regions:
            novaclient = himutils.get_client(Nova, options, logger, region)
            instances[region] = novaclient.get_project_instances(project_id=project.id)
            for i in instances[region]:
                instances_total += 1

        outputs = ['id', 'name', 'region', 'flavor', 'image (status)']
        x = PrettyTable()
        x.field_names = outputs
        x.align['id'] = 'l'
        x.align['name'] = 'l'

        print "PROJECT: %s  [%d instances]" % (project.name, instances_total)
        print '=' * 80
        print "  ID:    %s" % project.id
        print "  Admin: %s" % project_admin
        print "  Type:  %s" % project_type

        if len(project_roles) > 0:
            print "  Users: "
            #printer.output_dict({'header': 'Roles in project %s' % project})
            for role in project_roles:
                #printer.output_dict(role, sort=True, one_line=True)
                user = role['group'].replace('-group', '')
                print "    %s" % user
                #print role.group

        print "  Created: %s" % project_created
        print "\n               ".join(textwrap.wrap("  Description: " + project.description, 60))
        if instances_total > 0:
            print "  Instances: "
            for region in regions:
                for i in instances[region]:
                    filters = {'id': i.image['id']}
                    image = gc.find_image(filters=filters, limit=1)
                    if len(image) == 1:
                        image_name = image[0]['name']
                        image_status = image[0]['status']
                    else:
                        image_name = '(unknown)'
                        image_status = '(unknown)'

                    array = []
                    array.append(i.id)
                    array.append(i.name)
                    array.append(region)
                    array.append(i.flavor["original_name"])
                    array.append("%s (%s)" % (image_name, image_status))
                    x.add_row(array)
                    #print "             %s  %s %s %s/%s %s" % (i.id, region, i.flavor["original_name"], image_name, image_status, i.name)         

            print(x)
        print

        count += 1

    printer.output_dict({'header': 'Project list count', 'count': count})

    
# Run local function with the same name as the action (Note: - => _)
action = locals().get('action_' + options.action.replace('-', '_'))
if not action:
    himutils.sys_error("Function action_%s() not implemented" % options.action)
action()
