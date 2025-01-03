#!/usr/bin/env python

from datetime import date
import re

from himlarcli import tests as tests
tests.is_virtual_env()

from himlarcli.keystone import Keystone
from himlarcli.nova import Nova
from himlarcli.parser import Parser
from himlarcli.printer import Printer
from himlarcli import utils as himutils
from himlarcli.color import Color

parser = Parser()
options = parser.parse_args()
printer = Printer(options.format)

kc = Keystone(options.config, debug=options.debug)
kc.set_dry_run(options.dry_run)
logger = kc.get_logger()
nc = Nova(options.config, debug=options.debug, log=logger)
nc.set_dry_run(options.dry_run)


def action_instances():
    host = nc.get_host(nc.get_fqdn(options.host))
    if not host:
        himutils.sys_error('Could not find valid host %s' % options.host)
    search_opts = dict(all_tenants=1, host=host.hypervisor_hostname)
    instances = nc.get_all_instances(search_opts=search_opts)

    if options.format == 'table':
        output = {}
        output['header'] = [
            'ID',
            'NAME',
            'PROJECT',
            'AGE',
            'STATUS',
            'FLAVOR',
        ]
        output['align'] = [
            'l',
            'l',
            'l',
            'r',
            'l',
            'l',
        ]
        output['sortby'] = 2
        counter = 0
        for i in instances:
            project = kc.get_by_id('project', i.tenant_id)
            # Filter for project type
            if options.type:
                if hasattr(project, 'type') and project.type != options.type:
                    status['type'] = options.type
                    continue
            created = himutils.get_date(i.created, None, '%Y-%m-%dT%H:%M:%SZ')
            active_days = (date.today() - created).days

            # status color
            if i.status == 'ACTIVE':
                instance_status = Color.fg.red + i.status + Color.reset
            elif i.status == 'SHUTOFF':
                instance_status = Color.fg.GRN + i.status + Color.reset
            elif i.status == 'PAUSED':
                instance_status = Color.fg.BLU + i.status + Color.reset
            else:
                instance_status = Color.fg.YLW + i.status + Color.reset

            # project color
            if project is None:
                project_name = Color.fg.red + "None" + Color.reset
            else:
                project_name = Color.fg.cyn + project.name + Color.reset

            output[counter] = [
                Color.dim + i.id + Color.reset,
                Color.fg.GRN + i.name + Color.reset,
                project_name,
                active_days,
                instance_status,
                Color.fg.WHT + i.flavor['original_name'] + Color.reset,
            ]
            counter += 1
        printer.output_dict(output, sort=True, one_line=False)
    else:
        printer.output_dict({'header': 'Instance list (id, name, status, updated)'})
        status = {'total': 0}
        for i in instances:
            # Filter for project type
            if options.type:
                project = kc.get_by_id('project', i.tenant_id)
                if hasattr(project, 'type') and project.type != options.type:
                    status['type'] = options.type
                    continue
            output = {
                '1': i.id,
                '3': i.name,
                '4': i.status,
                #'2': i.updated,
                #'6'': getattr(i, 'OS-EXT-SRV-ATTR:instance_name'),
                '5': i.flavor['original_name']
            }
            printer.output_dict(output, sort=True, one_line=True)
            status['total'] += 1
            status[str(i.status).lower()] = status.get(str(i.status).lower(), 0) + 1
        printer.output_dict({'header': 'Counts'})
        printer.output_dict(status)


def action_show():
    host = nc.get_host(hostname=nc.get_fqdn(options.host), detailed=True)
    if not host:
        himutils.sys_error('Could not find valid host %s' % options.host)
    printer.output_dict(host.to_dict())

def action_users():
    users = nc.get_users(options.aggregate, simple=True)
    printer.output_dict({'header': 'User in %s' % options.aggregate,
                         'users': list(users)})

def action_move():
    hostname = nc.get_fqdn(options.host)
    if nc.add_host_to_aggregate(hostname=hostname, aggregate_name=options.aggregate, move=True):
        himutils.info(f"Host {hostname} moved to aggregate {options.aggregate}")

def action_add():
    hostname = nc.get_fqdn(options.host)
    if nc.add_host_to_aggregate(hostname=hostname, aggregate_name=options.aggregate, move=False):
        himutils.info(f"Host {hostname} added to aggregate {options.aggregate}")

def action_remove():
    hostname = nc.get_fqdn(options.host)
    if nc.remove_host_from_aggregate(hostname=hostname, aggregate_name=options.aggregate):
        himutils.info(f"Host {hostname} removed from aggregate {options.aggregate}")

def action_enable():
    host = nc.get_host(hostname=nc.get_fqdn(options.host), detailed=True)
    if not host:
        himutils.fatal(f"Could not find valid host {options.host}")
    if host.status != 'enabled' and not options.dry_run:
        nc.enable_host(host.hypervisor_hostname)
        himutils.info(f"Host {host.hypervisor_hostname} enabled")

def action_disable():
    host = nc.get_host(hostname=nc.get_fqdn(options.host), detailed=True)
    if not host:
        himutils.fatal(f"Could not find valid host {options.host}")
    if host.status != 'disabled' and not options.dry_run:
        nc.disable_host(host.hypervisor_hostname)
        himutils.info(f"Host {host.hypervisor_hostname} disabled")

def action_list():
    aggregates = nc.get_all_aggregate_hosts()
    if options.aggregate == 'all':
        hosts = nc.get_hosts()
    else:
        hosts = nc.get_aggregate_hosts(options.aggregate, True)
    if options.format == 'table':
        output = {}
        output['header'] = [
            'NAME',
            'AGGREGATES',
            'VMs',
            'vCPUs',
            'MEMORY (GiB)',
            'DISK (GB)',
            'STATE',
            'STATUS',
        ]
        output['align'] = [
            'l',
            'l',
            'r',
            'r',
            'r',
            'r',
            'l',
            'l',
        ]
        output['sortby'] = 0
        counter = 0
        for host in hosts:
            r_hostname = Color.fg.blu + re.sub('\.mgmt\..+?\.uhdc\.no$', '', host.hypervisor_hostname) + Color.reset
            r_aggregate = ','.join(aggregates.get(host.hypervisor_hostname, []))
            r_vms = str(host.running_vms)
            r_vcpus = f"{host.vcpus_used} / {host.vcpus}"
            r_mem = f"{int(host.memory_mb_used/1024)} / {int(host.memory_mb/1024)}"
            if re.search(r"^(central1|windows1|placeholder1|hpc1)$", r_aggregate):
                r_disk = "-"
            else:
                r_disk = f"{host.local_gb_used} / {host.local_gb}"
            r_status = host.status.upper()
            if host.status == 'enabled':
                r_aggregate = Color.fg.ylw + r_aggregate + Color.reset
                r_status = Color.fg.GRN + r_status + Color.reset
            else:
                r_aggregate = Color.fg.YLW + r_aggregate + Color.reset
                r_vms = Color.dim + r_vms + Color.reset
                r_vcpus = Color.dim + r_vcpus + Color.reset
                r_mem = Color.dim + r_mem + Color.reset
                r_disk = Color.dim + r_disk + Color.reset
                r_status = Color.fg.red + r_status + Color.reset
            if host.state == 'up':
                r_state = Color.fg.GRN + host.state.upper() + Color.reset
            else:
                r_state = Color.fg.red + host.state.upper() + Color.reset
            output[counter] = [
                r_hostname,
                r_aggregate,
                r_vms,
                r_vcpus,
                r_mem,
                r_disk,
                r_state,
                r_status,
            ]
            counter += 1
        printer.output_dict(output, sort=True, one_line=False)
    else:
        header = {'header': 'Hypervisor list (name, aggregates, vms, vcpu_used,' +
                  'ram_gb_used, local_gb_used, state, status)'}
        printer.output_dict(header)
        for host in hosts:
            output = {
                '1': host.hypervisor_hostname,
                '2': ','.join(aggregates.get(host.hypervisor_hostname, 'unknown')),
                '3': host.running_vms,
                '4': host.vcpus_used,
                '5': int(host.memory_mb_used/1024),
                '6': host.local_gb_used,
                '7': host.state,
                '8': host.status,
            }
            printer.output_dict(output, sort=True, one_line=True)

# Run local function with the same name as the action
action = locals().get('action_' + options.action)
if not action:
    himutils.sys_error("Function action_%s() not implemented" % options.action)
action()
