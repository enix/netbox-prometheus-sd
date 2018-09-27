#!/usr/bin/env python3

import sys
import json
import argparse

import pynetbox


DEFAULT_PROM_PORT = '10000'


def main(args):
    targets = []
    netbox = pynetbox.api(args.url, token=args.token)

    # Filter out devices without primary IP address as it is a requirement
    # to be polled by Prometheus
    devices = netbox.dcim.devices.filter(has_primary_ip=True)

    for device in devices:
        if device.custom_fields.get('prom_modules'):
            device_prom_port = device.custom_fields.get('prom_port', DEFAULT_PROM_PORT)
            labels = {'name': device.name}
            if device.cluster:
                labels['nb_cluster'] = device.cluster.name
            if device.asset_tag:
                labels['nb_asset_tag'] = device.asset_tag
            if device.device_role:
                labels['nb_role'] = device.device_role.slug
            if device.device_type:
                labels['nb_type'] = device.device_type.model
            if device.rack:
                labels['nb_rack'] = device.rack.name
            if device.site:
                labels['nb_pop'] = device.site.slug
            if device.serial:
                labels['nb_serial'] = device.serial
            if device.parent_device:
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
