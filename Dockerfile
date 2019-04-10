FROM ubuntu:bionic
MAINTAINER Antoine Millet <antoine.millet@enix.fr>

RUN apt update && apt install -y python3-pip
RUN pip3 install pynetbox netaddr
COPY netbox-prometheus-sd.py /bin/netbox-prometheus-sd
RUN chmod +x /bin/netbox-prometheus-sd
RUN mkdir /output

CMD while true; do (/bin/netbox-prometheus-sd "$NETBOX_URL" "$NETBOX_TOKEN" "/output/${OUTPUT_FILE-netbox.json}"; sleep $INTERVAL); done
