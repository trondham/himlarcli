#!/usr/bin/env python

from himlarcli.keystone import Keystone
from himlarcli.nova import Nova
from himlarcli.cinder import Cinder
from himlarcli.parser import Parser
from himlarcli.printer import Printer
from himlarcli import utils as himutils

himutils.is_virtual_env()

parser = Parser()
options = parser.parse_args()
printer = Printer(options.format)

ksclient = Keystone(options.config, debug=options.debug)
ksclient.set_dry_run(options.dry_run)
logger = ksclient.get_logger()

# Aggregate with local disk
local_aggregates = ['group1', 'group2', 'group3', 'alice1']

if hasattr(options, 'region'):
    regions = ksclient.find_regions(region_name=options.region)
else:
    regions = ksclient.find_regions()

if not regions:
    himutils.sys_error('no valid regions found!')

def action_volume():
    projects = ksclient.get_all_projects()
    for region in regions:
        cc = himutils.get_client(Cinder, options, logger, region)
        nc = himutils.get_client(Nova, options, logger, region)

        # vms pool
        vms_pool = dict({'in_use_gb': 0})
        for aggregate in nc.get_aggregates(True):
            if aggregate in local_aggregates:
                continue
            hosts = nc.get_aggregate_hosts(aggregate, True)
            for host in hosts:
                vms_pool['in_use_gb'] += int(host.local_gb_used)
        printer.output_dict({'header': 'Nova OS-disk: %s pool vms (max usage)' % region})
        printer.output_dict(vms_pool)

        # cinder quotas and volume usages
        quotas = dict({'in_use': 0, 'quota': 0})
        for project in projects:
            if not hasattr(project, "type"): # unknown project type
              logger.debug('=> unknow project type %s', project.name)
              continue
            # Filter demo
            if not options.demo and project.type == 'demo':
                continue
            quota = cc.get_quota(project_id=project.id, usage=True)
            quotas['in_use'] += quota['gigabytes']['in_use']
            quotas['quota'] += quota['gigabytes']['limit']

        # cinder volume usage
        volumes = cc.get_volumes(True)
        volume_usage = {'count': 0, 'size': 0}
        for volume in volumes:
            volume_usage['size'] += volume.size
            volume_usage['count'] += 1

        # cinder pools
        pools = cc.get_pools(detail=True)
        tmp = pools.to_dict()
        for pool in pools.pools:
            name = pool['capabilities']['volume_backend_name']
            #print pool
            out_pool = dict()
            out_pool['total_capacity_gb'] = pool['capabilities']['total_capacity_gb']
            out_pool['free_capacity_gb'] = pool['capabilities']['free_capacity_gb']
            printer.output_dict({'header': 'Cinder pool: %s pool %s' % (region, name)})
            printer.output_dict(out_pool)
        out_pools = dict()
        out_pools['number_of_volumes'] = volume_usage['count']
        out_pools['total_quota_gb'] = float(quotas['quota'])
        out_pools['total_in_volume_gb'] = volume_usage['size']
        out_pools['used_in_volume_gb'] = float(quotas['in_use'])
        printer.output_dict({'header': '%s openstack volume service' % region})
        printer.output_dict(out_pools)


def action_instance():
    #ToDo
    for region in regions:
        flavors = dict()
        cores = ram = 0
        novaclient = Nova(options.config, debug=options.debug, log=logger, region=region)
        instances = novaclient.get_instances()
        total = 0
        for i in instances:
            # Filter demo
            project = ksclient.get_by_id('project', i.tenant_id)
            if not options.demo and project and 'DEMO' in project.name:
                continue
            flavor_name = i.flavor.get('original_name', 'unknown')
            flavors[flavor_name] = flavors.get(flavor_name, 0) + 1
            cores += i.flavor.get('vcpus', 0)
            ram += i.flavor.get('ram', 0)
            total += 1
        printer.output_dict({'header': '%s instances' % region})
        printer.output_dict(flavors)
        printer.output_dict({'header': '%s resources' % region})
        printer.output_dict({'cores': cores,
                             'ram': '%.1f MB' % int(ram),
                             'instances': total})


# Run local function with the same name as the action
action = locals().get('action_' + options.action)
if not action:
    himutils.sys_error("Function action_%s() not implemented" % options.action)
action()
