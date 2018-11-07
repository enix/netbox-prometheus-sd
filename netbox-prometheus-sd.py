#!/usr/bin/env python3

import sys
import json
import argparse
import itertools

import pynetbox


def main(args):
    targets = []
    netbox = pynetbox.api(args.url, token=args.token)

    # Filter out devices without primary IP address as it is a requirement
    # to be polled by Prometheus
    devices = netbox.dcim.devices.filter(has_primary_ip=True)
    vm = netbox.virtualization.virtual_machines.filter(has_primary_ip=True)

    for device in itertools.chain(devices, vm):
        if device.custom_fields.get(args.custom_field):
            labels = {'__meta_netbox_name': device.name,
                      '__meta_netbox_port': str(args.port)}
            if device.tenant:
                labels['__meta_netbox_tenant'] = device.tenant.slug
                if device.tenant.group:
                    labels['__meta_netbox_tenant_group'] = device.tenant.group.slug
            if getattr(device, 'cluster', None):
                labels['__meta_netbox_cluster'] = device.cluster.name
            if getattr(device, 'asset_tag', None):
                labels['__meta_netbox_asset_tag'] = device.asset_tag
            if getattr(device, 'device_role', None):
                labels['__meta_netbox_role'] = device.device_role.slug
            if getattr(device, 'device_type', None):
                labels['__meta_netbox_type'] = device.device_type.model
            if getattr(device, 'rack', None):
                labels['__meta_netbox_rack'] = device.rack.name
            if getattr(device, 'site', None):
                labels['__meta_netbox_pop'] = device.site.slug
            if getattr(device, 'serial', None):
                labels['__meta_netbox_serial'] = device.serial
            if getattr(device, 'parent_device', None):
                labels['__meta_netbox_parent'] = device.parent_device.name

            try:
                device_targets = json.loads(device.custom_fields[args.custom_field])
            except ValueError:
                continue  # Ignore errors while decoding the target json FIXME: logging

            if not isinstance(device_targets, list):
                device_targets = [device_targets]

            for target in device_targets:
                target_labels = labels.copy()
                target_labels.update(target)
                targets.append({'targets': ['%s:%s' % (str(device.primary_ip.address.ip),
                                                       target_labels['__meta_netbox_port'])],
                                'labels': target_labels})

    if args.output == '-':
        output = sys.stdout
    else:
        output = open(args.output, 'w')

    json.dump(targets, output, indent=4)

    output.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', default=10000,
                        help='Default target port; Can be overridden using the __meta_netbox_port label')
    parser.add_argument('-f', '--custom-field', default='prom_labels',
                        help='Netbox custom field to use to get the target labels')
    parser.add_argument('url', help='URL to Netbox')
    parser.add_argument('token', help='Authentication Token')
    parser.add_argument('output', help='Output file')

    args = parser.parse_args()
    main(args)
