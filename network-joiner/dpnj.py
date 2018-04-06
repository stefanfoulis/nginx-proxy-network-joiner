from collections import defaultdict

import click
import docker


client = docker.from_env()


def should_join_networks(proxy_name):
    vhosts = defaultdict(set)
    for container in client.containers.list():
        if container.name == proxy_name:
            # Ignore the proxy container, since it does not make sense that
            # it would have VIRTUAL_HOSTS.
            continue
        for env_var in container.attrs['Config']['Env']:
            if not env_var.startswith('VIRTUAL_HOST='):
                continue
            virtual_hosts = [
                virtual_host.strip()
                for virtual_host
                in env_var.split('VIRTUAL_HOST=', maxsplit=1)[1].split(',')
                if virtual_host.strip()
            ]
            if not virtual_hosts:
                continue
            networks = container.attrs['NetworkSettings']['Networks'].keys()
            for network_name in networks:
                if network_name == 'bridge':
                    continue
                for virtual_host in virtual_hosts:
                    vhosts[network_name].add(virtual_host)
    return vhosts


def currently_joined_networks(proxy_name, proxy_network_name):
    proxy = client.containers.get(proxy_name)
    networks = {}
    for network_name, network in proxy.attrs['NetworkSettings']['Networks'].items():
        if network_name == proxy_network_name:
            # Ignore the proxies own network.
            continue
        if network_name == 'bridge':
            continue
        networks[network_name] = set(network['Aliases'])
    return networks


def sync_networks(proxy_name, proxy_network_name):
    should_join_dict = should_join_networks(
        proxy_name=proxy_name,
    )
    currently_joined_dict = currently_joined_networks(
        proxy_name=proxy_name,
        proxy_network_name=proxy_network_name,
    )
    should_be_member_of = set(should_join_dict.keys())
    is_member_of = set(currently_joined_dict.keys())

    to_leave = is_member_of - should_be_member_of
    to_join = should_be_member_of - is_member_of
    already_joined = is_member_of & should_be_member_of
    click.echo(
        f'to leave: {to_leave}\n'
        f'to join: {to_join}\n'
        f'already joined: {already_joined}\n'
    )
    all_aliases = set()
    for aliases in should_join_dict.values():
        for alias in aliases:
            all_aliases.add(alias)
    click.echo(f'all aliases: {all_aliases}')

    for network_name in to_leave:
        network = client.networks.get(network_name)
        click.echo(f'disconnecting from {network_name}... ', nl=False)
        network.disconnect(proxy_name, force=True)
        click.echo(f'done', color='green')

    for network_name in to_join:
        network = client.networks.get(network_name)
        click.echo(f'connecting to {network_name}... ', nl=False)
        network.connect(proxy_name, aliases=list(all_aliases))
        click.echo(f'done', color='green')

    for network_name in already_joined:
        current_aliases = currently_joined_dict[network_name]
        if all_aliases.issubset(current_aliases):
            continue
        network = client.networks.get(network_name)
        click.echo(f're-connecting to {network_name} to update aliases... disconnecting... ', nl=False)
        network.disconnect(proxy_name, force=True)
        click.echo(f'connecting... ', nl=False)
        network.connect(proxy_name, aliases=list(all_aliases))
        click.echo(f'done', color='green')
        # We don't try to remove no longer needed aliases here because that
        # would be much more complicated and leaving outdated aliases does no
        # harm (I hope).

    if to_join:
        # nginx-proxy is a bit eager about marking a container as unreachable if
        # the the the proxy container is not in the network yet when nginx-proxy
        # initially detects the new container starting up. We will not always be
        # fast enough to add the proxy container to the new network.
        # Unfortunatly nginx-proxy won't detect that the container would now be
        # reachable until the next time the nginx config is re-generated.
        # So here we want to tell nginx-proxy to re-generate the config files.
        # We're taking the easiest and hackiest way to trigger it:
        #   create a new container.
        click.echo(f'telling {proxy_name} to regenerate config... ', nl=False)
        client.containers.run(
            'busybox:latest',
            auto_remove=True,
            name='proxy-regenerate-trigger',
        )
        click.echo(f'done', color='green')


def watch_for_events(proxy_name, proxy_network_name):
    click.echo('Watching for docker events...')
    for event in client.events(decode=True):
        if event['Type'] == 'container' and event['Action'] in ('start', 'stop', 'kill'):
            sync_networks(
                proxy_name=proxy_name,
                proxy_network_name=proxy_network_name,
            )


def debug_config(proxy_name, proxy_network_name):
    joined = currently_joined_networks(proxy_name, proxy_network_name)
    click.echo(f'Proxy: {proxy_name} on {proxy_network_name}')
    for network_name, aliases in joined.items():
        click.echo(f'  {network_name}: ')
        click.echo(f'      ' + ', '.join(sorted(aliases)))


def debug_config_loop(proxy_name, proxy_network_name):
    import time
    while True:
        debug_config(proxy_name, proxy_network_name)
        time.sleep(3)


@click.group()
def cli():
    click.echo('this is proxy network discoverer')


@cli.command()
@click.option(
    '--proxy-name',
    default='proxy',
    help='The docker container name of the proxy.',
)
@click.option(
    '--proxy-network-name',
    default='proxy_default',
    help='The docker container name of the proxy.',
)
@click.option(
    '--watch/--no-watch',
    default=False,
    help='Watch the docker events and update when changes occur.',
)
def sync(proxy_name, proxy_network_name, watch):
    click.echo(f'syncing... for {proxy_name} running in {proxy_network_name}')
    sync_networks(
        proxy_name=proxy_name,
        proxy_network_name=proxy_network_name,
    )
    if watch:
        watch_for_events(
            proxy_name=proxy_name,
            proxy_network_name=proxy_network_name,
        )


@cli.command()
@click.option(
    '--proxy-name',
    default='proxy',
    help='The docker container name of the proxy.',
)
@click.option(
    '--proxy-network-name',
    default='proxy_default',
    help='The docker container name of the proxy.',
)
@click.option(
    '--loop/--no-loop',
    default=False,
)
def debug(proxy_name, proxy_network_name, loop):
    click.echo(f'debugging... for {proxy_name} running in {proxy_network_name}')
    if loop:
        debug_config_loop(
            proxy_name=proxy_name,
            proxy_network_name=proxy_network_name,
        )
    else:
        debug_config(
            proxy_name=proxy_name,
            proxy_network_name=proxy_network_name,
        )


if __name__ == "__main__":
    cli()
