#!/usr/bin/env python

import ipaddress
from datetime import datetime
from datetime import timedelta

from himlarcli import tests
tests.is_virtual_env()

from himlarcli.keystone import Keystone
from himlarcli.neutron import Neutron
from himlarcli.nova import Nova
from himlarcli.parser import Parser
from himlarcli.printer import Printer
from himlarcli import utils as himutils
from himlarcli.global_state import GlobalState, SecGroupRule

parser = Parser()
options = parser.parse_args()
printer = Printer(options.format)

kc = Keystone(options.config, debug=options.debug)
kc.set_domain(options.domain)
kc.set_dry_run(options.dry_run)
logger = kc.get_logger()
regions = himutils.get_regions(options, kc)

# Initialize database connection
database = himutils.get_client(GlobalState, options, logger)


def action_list():
    blacklist, whitelist, notify = load_config()
    for region in regions:
        nova = himutils.get_client(Nova, options, logger, region)
        neutron = himutils.get_client(Neutron, options, logger, region)
        rules = neutron.get_security_group_rules(5)

        question = (f"Are you sure you will list {len(rules)} security group rules in {region}?")
        if not options.assume_yes and not himutils.confirm_action(question):
            return

        printer.output_dict({'header': f"Rules in {region} (project, ports, protocol, remote ip prefix)"})
        for rule in rules:
            if is_whitelist(rule, region, whitelist):
                continue
            if is_blacklist(rule, region, blacklist):
                continue

            # check if project exists
            project = kc.get_by_id('project', rule['project_id'])
            if not project:
                kc.debug_log(f"could not find project {rule['project_id']}")
                continue

            sec_group = neutron.get_security_group(rule['security_group_id'])
            if not rule_in_use(sec_group, nova):
                continue

            output = {
                '0': project.name,
                '1': f"{rule['port_range_min']}-{rule['port_range_max']}",
                '2': rule['protocol'],
                '3': rule['remote_ip_prefix']
            }
            printer.output_dict(output, one_line=True)


def action_check():
    count = {
        'total'         : 0,  # Total number of rules checked
        'whitelist'     : 0,  # Number of whitelisted rules
        'no_remote_ip'  : 0,  # Number of rules where remote IP is None
        'unused'        : 0,  # Number of rules not used on instances
        'proj_disabled' : 0,  # Number of rules for disabled projects
        'wrong_mask'    : 0,  # Number of rules with wrong netmask
        'bogus_0_mask'  : 0,  # Number of rules with bogus /0 mask
        'port_limit'    : 0,  # Number of rules exceeding port limits
        'ok'            : 0,  # Number of rules deemed OK
    }
    blacklist, whitelist, notify = load_config()
    for region in regions:
        nova = himutils.get_client(Nova, options, logger, region)
        neutron = himutils.get_client(Neutron, options, logger, region)
        rules = neutron.get_security_group_rules(1000)

        question = (f"Are you sure you will check {len(rules)} security group rules in {region}?")
        if not options.assume_yes and not himutils.confirm_action(question):
            return

        for rule in rules:
            count['total'] += 1
            if rule['remote_ip_prefix'] is None:
                count['no_remote_ip'] +=1
                continue

            # Only care about security groups that are being used
            sec_group = neutron.get_security_group(rule['security_group_id'])
            if not rule_in_use(sec_group, nova):
                count['unused'] += 1
                continue

            # Get IP version ('4' or '6')
            #version = ipaddress.ip_interface(rule['remote_ip_prefix']).version

            # check if project exists
            project = kc.get_by_id('project', rule['project_id'])
            if not project:
                kc.debug_log(f"could not find project {rule['project_id']}")
                continue

            # Ignore if project is disabled
            if not is_project_enabled(project):
                count['proj_disabled'] += 1
                continue

            # Check for bogus use of /0 mask
            if check_bogus_0_mask(rule, region, project):
                count['bogus_0_mask'] += 1
                continue

            # check for wrong netmask
            if check_wrong_mask(rule, region, project):
                count['wrong_mask'] += 1
                continue

            # Run through whitelist
            if is_whitelist(rule, region, whitelist):
                count['whitelist'] += 1
                continue

            # Run through blacklist
            if is_blacklist(rule, region, blacklist):
                continue

            # Check port limits
            if check_port_limits(rule, region, notify, project=project):
                count['port_limit'] += 1
                continue

            if rule['port_range_min'] is None and rule['port_range_max'] is None:
                ports = 'ALL'
            elif rule['port_range_min'] == rule['port_range_max']:
                ports = str(rule['port_range_min'])
            else:
                ports = f"{rule['port_range_min']}-{rule['port_range_max']}"

            verbose_info(f"[{region}] OK: {project.name} ports {ports}/{rule['protocol']} " +
                         f"ingress {rule['remote_ip_prefix']}")
            count['ok'] += 1
        print()
        print(f"Summary for region {region}:")
        print("====================================================")
        print(f"    Whitelisted rules:    {count['whitelist']}")
        print(f"    OK rules:             {count['ok']}")
        print(f"    Unused rules:         {count['unused']}")
        print(f"    Disabled projects:    {count['proj_disabled']}")
        print(f"    No remote IP:         {count['no_remote_ip']}")
        print(f"    Bogus /0 mask:        {count['bogus_0_mask']}")
        print(f"    Wrong mask:           {count['wrong_mask']}")
        print(f"    Port limits exceeded: {count['port_limit']}")
        print()
        print(f"  TOTAL rules checked in {region}: {count['total']}")
        print()
            
def add_or_update_db(database, rule_id, secgroup_id, project_id, region):
    limit = 30
    existing_object = database.get_first(SecGroupRule,
                                         rule_id=rule_id,
                                         secgroup_id=secgroup_id,
                                         project_id=project_id,
                                         region=region)
    if existing_object is None:
        rule_entry = { 'rule_id'     : rule_id,
                       'secgroup_id' : secgroup_id,
                       'project_id'  : project_id,
                       'region'      : region,
                       'notified'    : datetime.now(),
                       'created'     : datetime.now(),
                      }
        rule_object = SecGroupRule.create(rule_entry)
        database.add(rule_object)
    else:
        last_notified = existing_object.notified
        if datetime.now() > last_notified + timedelta(days=limit):
            verbose_warning(f"[{region}] More than {limit} days since {rule_id} was notified")
            rule_diff = { 'notified': datetime.now() }
            database.update(existing_object, rule_diff)

# Check for wrong use of mask 0. Returns true if the mask is 0 and the
# IP is not one of "0.0.0.0" or "::"
def check_bogus_0_mask(rule, region, project):
    ip = ipaddress.ip_interface(rule['remote_ip_prefix']).ip
    if str(rule['remote_ip_prefix']).endswith('/0') and ip.compressed not in ('0.0.0.0', '::'):
        min_mask = minimum_netmask(ip, rule['ethertype'])
        verbose_error(f"[{region}] Bogus /0 mask: {rule['remote_ip_prefix']} " +
                      f"({project.name}). Minimum netmask: {min_mask}")
        if options.notify:
            add_or_update_db(database=database,
                             rule_id=rule['id'],
                             secgroup_id=rule['security_group_id'],
                             project_id=rule['project_id'],
                             region=region)
        return True
    return False

# Check if the netmask is wrong for the IP
def check_wrong_mask(rule, region, project):
    mask = ipaddress.ip_interface(rule['remote_ip_prefix']).netmask
    ip = ipaddress.ip_interface(rule['remote_ip_prefix']).ip
    packed = int(ip)
    if packed & int(mask) != packed:
        min_mask = minimum_netmask(ip, rule['ethertype'])
        verbose_error(f"[{region}] {rule['remote_ip_prefix']} has wrong netmask " +
                      f"({project.name}). Minimum netmask: {min_mask}")
        if options.notify:
            add_or_update_db(database=database,
                             rule_id=rule['id'],
                             secgroup_id=rule['security_group_id'],
                             project_id=rule['project_id'],
                             region=region)
        return True
    return False

# Calculates minimum netmask for a given IP
def minimum_netmask(ip, family):
    if family == "IPv6":
        maxmask = 128
    elif family == "IPv4":
        maxmask = 32
    packed = int(ip)
    for i in range(maxmask,0,-1):
        mask = ipaddress.ip_interface(f'{ip}/{i}').netmask
        if packed & int(mask) != packed:
            return i+1
    return 0

def rule_in_use(sec_group, nova):
    instances = nova.get_project_instances(sec_group['project_id'])
    for i in instances:
        if not hasattr(i, 'security_groups'):
            continue
        for group in i.security_groups:
            if group['name'] == sec_group['name']:
                return True
    return False

def is_project_enabled(project):
    return project.enabled

def check_port_limits(rule, region, notify, project=None):
    for limit in notify['network_port_limits']:
        max_mask  = notify['network_port_limits'][limit]['max_mask']
        min_mask  = notify['network_port_limits'][limit]['min_mask']
        max_ports = notify['network_port_limits'][limit]['max_ports']
        rule_mask = int(ipaddress.ip_network(rule['remote_ip_prefix']).prefixlen)
        protocol = rule['protocol']

        if rule['port_range_max'] is None and rule['port_range_min'] is None:
            rule_ports = 65536
        else:
            rule_ports = int(rule['port_range_max']) - int(rule['port_range_min']) + 1

        if rule_mask > max_mask or rule_mask < min_mask:
            continue
        if rule_mask <= max_mask and rule_mask >= min_mask and rule_ports <= max_ports:
            continue

        verbose_warning(f"[{region}] {project.name} {rule['remote_ip_prefix']} " +
                        f"{rule['port_range_min']}-{rule['port_range_max']}/{protocol} " +
                        f"has too many open ports ({rule_ports} > {max_ports})")
        if options.notify:
            add_or_update_db(database=database,
                             rule_id=rule['id'],
                             secgroup_id=rule['security_group_id'],
                             project_id=rule['project_id'],
                             region=region)
        return True
    return False

def is_blacklist(rule, region, blacklist):
    # Blacklisting is currently not implemented
    return False

def verbose_info(string):
    if options.verbose >= 3:
        himutils.info(string)

def verbose_warning(string):
    if options.verbose >= 2:
        himutils.warning(string)

def verbose_error(string):
    if options.verbose >= 1:
        himutils.error(string)

def is_whitelist(rule, region, whitelist):
    #valid_none_check = ['remote_ip_prefix']
    for k, v in whitelist.items():
        # whitelist none empty property
        if "!None" in v and rule[k]:
            verbose_info(f"[{region}] WHITELIST: Remote group {rule['remote_group_id']}")
            return True
        # single port match: both port_range_min and port_range_max need to match
        if k == 'port':
            if rule['port_range_min'] in v and rule['port_range_max'] in v:
                verbose_info(f"[{region}] WHITELIST: port {rule['port_range_min']}")
                return True
        # remote ip
        elif k == 'remote_ip_prefix':
            try:
                rule_network = ipaddress.ip_network(rule['remote_ip_prefix'])
            except ValueError:
                return False
            for r in v:
                rule_white = ipaddress.ip_network(r)
                if rule_network.version != rule_white.version:
                    continue
                # NOTE: If python is 3.7 or newer, replace with subnet_of()
                if (rule_network.network_address >= rule_white.network_address and
                    rule_network.broadcast_address <= rule_white.broadcast_address):
                    verbose_info(f"[{region}] WHITELIST: {rule['remote_ip_prefix']} " +
                                 f"is part of {r}")
                    return True
        # whitelist match
        elif rule[k] in v:
            verbose_info(f"[{region}] WHITELIST: {k} {rule[k]}")
            return True
    return False

def load_config():
    config_files = {
        'blacklist': 'config/security_group/blacklist.yaml',
        'whitelist': 'config/security_group/whitelist.yaml',
        'notify': 'config/security_group/notify.yaml'}
    config = {}
    for file_type, config_file in config_files.items():
        config[file_type] = himutils.load_config(config_file)
        kc.debug_log(f"{file_type}: {config[file_type]}")
    return [(v) for v in config.values()]


# Run local function with the same name as the action (Note: - => _)
action = locals().get('action_' + options.action.replace('-', '_'))
if not action:
    himutils.fatal(f"Function action_{options.action} not implemented")
action()
