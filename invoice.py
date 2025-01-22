#!/usr/bin/env python

from himlarcli import tests
tests.is_virtual_env()

from himlarcli.keystone import Keystone
from himlarcli.nova import Nova
from himlarcli import utils as himutils

parser = Parser()
options = parser.parse_args()
printer = Printer(options.format)

kc = Keystone(options.config, debug=options.debug)
kc.set_domain(options.domain)
kc.set_dry_run(options.dry_run)
logger = kc.get_logger()
regions = himutils.get_regions(options, kc)

#---------------------------------------------------------------------
# Action functions
#---------------------------------------------------------------------
def action_list():
#    search_filter = dict()
#    if options.filter and options.filter != 'all':
#        search_filter['type'] = options.filter
#    projects = kc.get_projects(**search_filter)

    for region in regions:
        nova  = himutils.get_client(Nova, options, logger, region)
        quotas = nova.get_quota(project.id).copy()
        print(quotas)


#---------------------------------------------------------------------
# Run local function with the same name as the action (Note: - => _)
#---------------------------------------------------------------------
action = locals().get('action_' + options.action.replace('-', '_'))
if not action:
    himutils.fatal(f"Function action_{options.action} not implemented")
action()
