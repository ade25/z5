import os
import getpass
from fabric.api import cd
from fabric.api import env
from fabric.api import local
from fabric.api import run
from fabric.api import task
from fabric.colors import green
from fabric.colors import red

from ade25.fabfiles import project
from ade25.fabfiles.server import setup
from ade25.fabfiles.server import controls
from ade25.fabfiles import hotfix as hf

from slacker import Slacker
slack = Slacker('xoxp-2440800772-2440800774-136782824743-8ab4ddccedc95a8deb53d6cde10d9976')

env.use_ssh_config = True
env.forward_agent = True
env.port = '22222'
env.user = 'root'
env.hostname = 'z4'
env.code_user = 'root'
env.prod_user = 'www'
env.webserver = '/opt/webserver/buildout.webserver'
env.code_root = '/opt/webserver/buildout.webserver'
env.host_root = '/opt/sites'
env.local_dir = '/Users/cb/ops/z4'

env.hosts = ['z4.ade25.de']
env.hosted_sites = {
}

env.hosted_sites_locations = [
]


@task
def restart():
    """ Restart all """
    with cd(env.webserver):
        run('nice bin/supervisorctl restart all')


@task
def restart_nginx():
    """ Restart Nginx """
    controls.restart_nginx()


@task
def restart_varnish():
    """ Restart Varnish """
    controls.restart_varnish()


@task
def restart_haproxy():
    """ Restart HAProxy """
    controls.restart_haproxy()


@task
def ctl(*cmd):
    """Runs an arbitrary supervisorctl command."""
    with cd(env.webserver):
        run('nice bin/supervisorctl ' + ' '.join(cmd))


@task
def prepare_deploy():
    """ Push committed local changes to git """
    local('git push')

@task
def add_site(site_id=None):
    opts = dict(
        filename=os.path.join(
            env.local_dir, 'buildout.d', 'templates', 'nginx.conf'
        ),
        replacement='site{0}.conf;'.format(site_id)
    )
    cmd = r"sed -i '' '/%(replacement)s/s/^#*//g' %(filename)s " % opts
    local(cmd)
    print(green('site{0} has been activated'.format(site_id)))


@task
def remove_site(site_id=None):
    opts = dict(
        filename=os.path.join(
            env.local_dir, 'buildout.d', 'templates', 'nginx.conf'
        ),
        replacement='site{0}.conf;'.format(site_id)
    )
    cmd = r"sed -i '' '/%(replacement)s/s/^/#/g' %(filename)s " % opts
    local(cmd)
    print(red('site{0} has been deactivated'.format(site_id)))


@task
def add_cert(servername=None):
    setup.certbot(servername)
    setup.certbot('www.{0}'.format(servername))


@task
def deploy(actor=None):
    """ Deploy current master to production server """
    opts = dict(
        actor=actor or env.get('actor') or getpass.getuser(),
    )
    project.site.update()
    project.site.build()
    with cd(env.webserver):
        run('bin/supervisorctl reread')
        run('bin/supervisorctl update')
    msg = '[z4] z4.ade25.de server configuration deployed by %(actor)s' % opts
    user = 'fabric'
    icon = ':shipit:'
    slack.chat.post_message('#development', msg, username=user, icon_emoji=icon)


@task
def update(sitename=None, actor=None):
    """ Deploy changes to a hosted site """
    opts = dict(
        sitename=sitename,
        actor=actor or env.get('actor') or getpass.getuser(),
    )
    path = '{0}/{1}/buildout.{2}'.format(env.host_root, sitename, sitename)
    with cd(path):
        run('nice git pull')
        run('nice bin/buildout -Nc deployment.cfg')
    with cd(env.webserver):
        run('nice bin/supervisorctl restart instance-%(sitename)s' % opts)
    msg = '[z4] %(sitename)s deployed by %(actor)s' % opts
    user = 'fabric'
    icon = ':shipit:'
    slack.chat.post_message('#development', msg, username=user, icon_emoji=icon)


@task
def hotfix(addon=None):
    """ Apply hotfix to all hosted sites """
    hf.prepare_sites()
    hf.process_hotfix()
