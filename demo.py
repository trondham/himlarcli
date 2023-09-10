#!/usr/bin/env python

from datetime import date

from himlarcli import tests
tests.is_virtual_env()

from himlarcli.keystone import Keystone
from himlarcli.nova import Nova
from himlarcli.cinder import Cinder
from himlarcli.mail import Mail
from himlarcli.parser import Parser
from himlarcli.printer import Printer
from himlarcli import utils as himutils
from himlarcli.global_state import GlobalState, DemoInstance

parser = Parser()
options = parser.parse_args()
printer = Printer(options.format)

kc = Keystone(options.config, debug=options.debug)
kc.set_domain(options.domain)
kc.set_dry_run(options.dry_run)
logger = kc.get_logger()
regions = himutils.get_regions(options, kc)

today_iso = date.today().isoformat()

# Initialize database connection
db = himutils.get_client(GlobalState, options, logger)

def action_list():
    projects = kc.get_projects(type='demo')
    printer.output_dict({'header': 'Demo project (instances, vcpus, volumes, gb, name)'})
    count = {'size': 0, 'vcpus': 0, 'instances': 0}
    for project in projects:
        ins_data = {'count': 0, 'vcpu': 0}
        vol_data = dict({'count': 0, 'size': 0})
        for region in regions:
            nc = himutils.get_client(Nova, options, logger, region)
            cc = himutils.get_client(Cinder, options, logger, region)
            instances = nc.get_project_instances(project_id=project.id)
            ins_data = {'count': 0, 'vcpus': 0}
            for i in instances:
                ins_data['vcpus'] += i.flavor['vcpus']
                ins_data['count'] += 1
            volumes = cc.get_volumes(detailed=True, search_opts={'project_id': project.id})
            for volume in volumes:
                vol_data['size'] += volume.size
                vol_data['count'] += 1
        output = {
            '5': project.name,
            '1': ins_data['count'],
            '2': ins_data['vcpus'],
            '3': vol_data['count'],
            '4': vol_data['size']
        }
        printer.output_dict(output, one_line=True)
        count['size'] += vol_data['size']
        count['vcpus'] += ins_data['vcpus']
        count['instances'] += ins_data['count']
    printer.output_dict({
        'header': 'Count',
        'instances': count['instances'],
        'volume_gb': count['size'],
        'vcpus': count['vcpus']})

def action_instances():
    projects = kc.get_projects(type='demo')
    printer.output_dict({'header': 'Demo instances (id, lifetime in days, name, flavor)'})
    count = 0
    for project in projects:
        for region in regions:
            nc = himutils.get_client(Nova, options, logger, region)
            instances = nc.get_project_instances(project_id=project.id)
            for i in instances:
                created = himutils.get_date(i.created, None, '%Y-%m-%dT%H:%M:%SZ')
                active_days = (date.today() - created).days
                if int(active_days) < int(options.day):
                    continue
                output = {
                    '0': i.id,
                    '2': i.name,
                    '1': (date.today() - created).days,
                    '3': i.flavor['original_name']
                }
                count += 1
                printer.output_dict(output, one_line=True)
    printer.output_dict({'header': 'Count', 'count': count})

def action_expired():
    max_days = 90
    projects = kc.get_projects(type='demo')

    # logfile
    logfile = f'logs/demo-logs/expired_instances/demo-notify-expired-instances-{today_iso}.log'

    # mail parameters
    mail = himutils.get_client(Mail, options, logger)
    subject = '[NREC] Your demo instance is due for deletion'
    fromaddr = mail.get_config('mail', 'from_addr')
    bccaddr = 'iaas-logs@usit.uio.no'

    inputday = options.day
    question = f'Send mail to instances that have been running for {inputday} days?'
    if not options.force and not himutils.confirm_action(question):
        return
    template = options.template
    if not himutils.file_exists(template, logger):
        himutils.fatal(f'Could not find template file {template}')
    if not options.template:
        himutils.fatal('Specify a template file. E.g. -t notify/demo-notify-expired-instances.txt')
    if not options.day:
        himutils.fatal('Specify the number of days for running demo instances. E.g. -d 30')
    for region in regions:
        nc = himutils.get_client(Nova, options, logger, region)
        for project in projects:
            instances = nc.get_project_instances(project_id=project.id)
            for instance in instances:
                created = himutils.get_date(instance.created, None, '%Y-%m-%dT%H:%M:%SZ')
                active_days = (date.today() - created).days
                kc.debug_log(f'{instance.id} running for {active_days} days')
                if int(active_days) == int(inputday):
                    mapping = dict(project=project.name,
                                   enddate=int((max_days)-int(inputday)),
                                   activity=int(active_days),
                                   region=region.upper(),
                                   instance=instance.name)
                    body_content = himutils.load_template(inputfile=template, mapping=mapping, log=logger)
                    msg = mail.get_mime_text(subject, body_content, fromaddr)
                    kc.debug_log(f'Sending mail to {instance.id} that has been active for {active_days} days')
                    mail.send_mail(project.admin, msg, fromaddr, None, bccaddr)
                    himutils.append_to_logfile(logfile, date.today(), region, project.admin, instance.name, active_days)
                    print(f'Mail sendt to {project.admin}')

# Delete demo instances older than 90 days
def action_delete():
    days = 90
    question = f'Delete demo instances older than {days} days?'
    if not options.force and not himutils.confirm_action(question):
        return
    projects = kc.get_projects(type='demo')
    logfile = f'logs/demo-logs/deleted_instances/deleted-expired-demo-instances-{today_iso}.log'
    for region in regions:
        for project in projects:
            nc = himutils.get_client(Nova, options, logger, region)
            instances = nc.get_project_instances(project_id=project.id)
            for instance in instances:
                created = himutils.get_date(instance.created, None, '%Y-%m-%dT%H:%M:%SZ')
                active_days = (date.today() - created).days
                kc.debug_log(f'Found instance {instance.id} for user {project.admin}')
                if int(active_days) >= days:
                    nc.delete_instance(instance)
                    if not options.dry_run:
                        himutils.append_to_logfile(logfile, "deleted:", project.name, instance.name, "active for:", active_days)

# Run local function with the same name as the action (Note: - => _)
action = locals().get('action_' + options.action.replace('-', '_'))
if not action:
    himutils.fatal(f"Function action_{options.action} not implemented")
action()
