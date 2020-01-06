#!/usr/bin/env python3

import sys
import os
import json
import argparse
import itertools
import netaddr
import logging
from urllib3.exceptions import RequestError

import pynetbox


class Discovery(object):
    def __init__(self, args):
        super(Discovery, self).__init__()
        self.args = args

    def run(self):
        self.netbox = pynetbox.api(self.args.url, token=self.args.token)
        if self.args.discovery == 'device':
            targets = self.discover_device()
        elif self.args.discovery == 'circuit':
            targets = self.discover_circuit()
        else:
            return

        temp_file = None
        if self.args.output == '-':
            output = sys.stdout
        else:
            temp_file = '{}.tmp'.format(self.args.output)
            output = open(temp_file, 'w')

        json.dump(targets, output, indent=4)
        output.write('\n')

        if temp_file:
            output.close()
            os.rename(temp_file, self.args.output)
        else:
            output.flush()

    def discover_device(self):
        targets = []

        # Filter out devices without primary IP address as it is a requirement
        # to be polled by Prometheus
        devices = self.netbox.dcim.devices.filter(has_primary_ip=True)
        vm = self.netbox.virtualization.virtual_machines.filter(
            has_primary_ip=True)
        ips = self.netbox.ipam.ip_addresses.filter(
            **{'cf_%s' % self.args.custom_field: '{'})

        for device in itertools.chain(devices, vm, ips):
            if device.custom_fields.get(self.args.custom_field):
                labels = {'__port__': str(self.args.port)}
                if getattr(device, 'name', None):
                    labels['__meta_netbox_name'] = device.name
                else:
                    labels['__meta_netbox_name'] = repr(device)

                if getattr(device, 'site', None):
                    labels['__meta_netbox_pop'] = device.site.slug

                try:
                    device_targets = json.loads(
                        device.custom_fields[self.args.custom_field])
                except ValueError as e:
                    logging.exception(e)
                    continue

                if not isinstance(device_targets, list):
                    device_targets = [device_targets]

                for target in device_targets:
                    target_labels = labels.copy()
                    target_labels.update(target)
                    if hasattr(device, 'primary_ip'):
                        address = device.primary_ip
                    else:
                        address = device
                    targets.append({'targets': ['%s:%s' % (str(netaddr.IPNetwork(
                        address.address).ip), target_labels['__port__'])], 'labels': target_labels})

        return targets

    def get_circuit_ip(self, circuit_id):
        try:
            ta = self.netbox.circuits.circuit_terminations.filter(
                circuit_id=circuit_id, term_side='A')[0]
            logging.debug('terminal A: {}'.format(ta))

            tz = self.netbox.circuits.circuit_terminations.filter(
                circuit_id=circuit_id, term_side='Z')[0]
            logging.debug('terminal Z: {}'.format(tz))
        except RequestError as e:
            logging.exception(e)
            return None, None

        ipa = self.get_terminal_a_ip(ta)
        logging.debug(
            'circuit {}: IP of terminal A: {}'.format(circuit_id, ipa))

        ipz = self.get_terminal_z_ip(tz)
        logging.debug(
            'circuit {}: IP of terminal Z: {}'.format(circuit_id, ipz))

        return ipa, ipz

    # Here return `primary_ip`, not real `terminal_a_ip`, prometheus will get metrics forom this IP
    def get_terminal_a_ip(self, ta):
        device = self.netbox.dcim.devices.get(ta.connected_endpoint.device.id)
        if hasattr(device, 'primary_ip'):
            return str(netaddr.IPNetwork(device.primary_ip.address).ip)
        else:
            return None

    def get_terminal_z_ip(self, tz):
        logging.debug('connected_endpoint device: {}'.format(
            tz.connected_endpoint.device.name))
        logging.debug('connected_endpoint interface: {}'.format(
            tz.connected_endpoint.name))
        try:
            ip = self.netbox.ipam.ip_addresses.filter(
                device_id=tz.connected_endpoint.device.id, interface=tz.connected_endpoint.name)
        except RequestError as e:
            logging.exception(e)
            return None

        return str(netaddr.IPNetwork(ip[0].address).ip)

    def discover_circuit(self):

        targets = []

        circuits = self.netbox.circuits.circuits.all()

        for circuit in itertools.chain(circuits):
            if circuit.custom_fields.get(self.args.custom_field):
                logging.debug('circuit: {}'.format(circuit.cid))

                ipa, ipz = self.get_circuit_ip(circuit.id)
                if not ipa or not ipz:
                    continue

                labels = {'__port__': str(self.args.port)}

                if getattr(circuit, 'cid', None):
                    labels['__meta_netbox_name'] = circuit.cid
                else:
                    labels['__meta_netbox_name'] = repr(circuit)

                # labels['__meta_netbox_address'] = ipa
                labels['__meta_netbox_target'] = ipz

                logging.debug(labels)

                try:
                    device_targets = json.loads(
                        circuit.custom_fields[self.args.custom_field])
                except ValueError as e:
                    logging.exception(e)
                    continue

                if not isinstance(device_targets, list):
                    device_targets = [device_targets]

                for target in device_targets:
                    target_labels = labels.copy()
                    target_labels.update(target)
                    targets.append({'targets': ['%s:%s' % (
                        ipa, target_labels['__port__'])], 'labels': target_labels})

        return targets


def main():
    format = "%(asctime)s %(filename)s [%(lineno)d][%(levelname)s] %(message)s"
    logging.basicConfig(level=logging.INFO, format=format)

    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', default=10000,
                        help='Default target port; Can be overridden using the __port__ label')
    parser.add_argument('-f', '--custom-field', default='prom_labels',
                        help='Netbox custom field to use to get the target labels')
    parser.add_argument('url', help='URL to Netbox')
    parser.add_argument('token', help='Authentication Token')
    parser.add_argument('output', help='Output file')

    parser.add_argument('-d', '--discovery', default='device',
                        help='Discovery type, default: device', choices=['device', 'circuit'])
    args = parser.parse_args()

    discovery = Discovery(args)

    discovery.run()


if __name__ == '__main__':
    main()
