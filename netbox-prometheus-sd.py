#!/usr/bin/env python3

import sys
import json
import argparse
import itertools

import pynetbox


DEFAULT_PROM_PORT = '10000'


def main(args):
    targets = []
    netbox = pynetbox.api(args.url, token=args.token)

    # Filter out devices without primary IP address as it is a requirement
    # to be polled by Prometheus
    devices = netbox.dcim.devices.filter(has_primary_ip=True)
    vm = netbox.virtualization.virtual_machines.filter(has_primary_ip=True)

    for device in itertools.chain(devices, vm):
        if device.custom_fields.get('prom_modules'):
            device_prom_port = device.custom_fields.get('prom_port', DEFAULT_PROM_PORT)
            labels = {'name': device.name}
            if device.tenant:
                labels['tenant'] = device.tenant.slug
                if device.tenant.group:
                    labels['tenant_group'] = device.tenant.group.slug
            if getattr(device, 'cluster', None):
                labels['nb_cluster'] = device.cluster.name
            if getattr(device, 'asset_tag', None):
                labels['nb_asset_tag'] = device.asset_tag
            if getattr(device, 'device_role', None):
                labels['nb_role'] = device.device_role.slug
            if getattr(device, 'device_type', None):
                labels['nb_type'] = device.device_type.model
            if getattr(device, 'rack', None):
                labels['nb_rack'] = device.rack.name
            if getattr(device, 'site', None):
                labels['nb_pop'] = device.site.slug
            if getattr(device, 'serial', None):
                labels['nb_serial'] = device.serial
            if getattr(device, 'parent_device', None):
                labels['nb_parent'] = device.parent_device.name

            for module in device.custom_fields['prom_modules'].split():
                labels['__param_module'] = module
                targets.append({'targets': ['%s:%s' % (str(device.primary_ip.address.ip), device_prom_port)],
                                'labels': labels.copy()})

    if args.output == '-':
        output = sys.stdout
    else:
        output = open(args.output, 'w')

    json.dump(targets, output, indent=4)

    output.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('url', help='URL to Netbox')
    parser.add_argument('token', help='Authentication Token')
    parser.add_argument('output', help='Output file')

    args = parser.parse_args()
    main(args)
