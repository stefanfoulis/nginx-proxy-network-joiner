from collections import defaultdict

import click
import docker
from pprint import pformat


client = docker.from_env()


def should_join_networks(proxy_name):
    vhosts = defaultdict(list)
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
            networks = list(container.attrs['NetworkSettings']['Networks'].keys())
            for network in networks:
                for virtual_host in virtual_hosts:
                    vhosts[network].append(virtual_host)
    return vhosts


def already_joined_networks(proxy_name, proxy_network_name):
    proxy = client.containers.get(proxy_name)
    networks = {}
    for network_name, network in proxy.attrs['NetworkSettings']['Networks'].items():
        if network_name == proxy_network_name:
            # Ignore the proxies own network.
            continue
        networks[network_name] = network['Aliases']
    return networks


def sync_networks(proxy_name, proxy_network_name):
    should_join_dict = should_join_networks(
        proxy_name=proxy_name,
    )
    already_joined_dict = already_joined_networks(
        proxy_name=proxy_name,
        proxy_network_name=proxy_network_name,
    )
    should = set(should_join_dict.keys())
    joined = set(already_joined_dict.keys())

    to_leave = joined - should
    to_join = should - joined
    already_joined = joined & should
    click.echo(
        f'to leave: {to_leave}\n'
        f'to join: {to_join}\n'
        f'already joined: {already_joined}\n'
    )
    for network_name in to_leave:
        network = client.networks.get(network_name)
        click.echo(f'disconnecting from {network_name}... ', nl=False)
        network.disconnect(proxy_name, force=True)
        click.echo(f'done', color='green')

    for network_name in to_join:
        network = client.networks.get(network_name)
        click.echo(f'connecting to {network_name}... ', nl=False)
        network.connect(proxy_name)
        click.echo(f'done', color='green')

    # nginx-proxy is a bit eager about marking a container as unreachable if
    # the the the proxy container is not in the network yet when nginx-proxy
    # initially detects the new container starting up. We might not be fast
    # enough to add the proxy container to the new network.
    # So we tell nginx-proxy to re-generate the config files.
    proxy = client.containers.get(proxy_name)
    proxy.kill(signal='HUP')
    # TODO: rejoin already_joined if aliases have changed


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
def sync(proxy_name, proxy_network_name):
    click.echo(f'syncing... for {proxy_name} running in {proxy_network_name}')
    sync_networks(proxy_name=proxy_name, proxy_network_name=proxy_network_name)


if __name__ == "__main__":
    cli()
