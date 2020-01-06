FROM alpine

RUN apk add --no-cache python3
RUN pip3 install --no-cache --upgrade pip
RUN pip3 install --no-cache --upgrade pynetbox netaddr

COPY netbox-prometheus-sd.py /bin/netbox-prometheus-sd
RUN chmod +x /bin/netbox-prometheus-sd
RUN mkdir /output

CMD while true; do (/bin/netbox-prometheus-sd "$NETBOX_URL" "$NETBOX_TOKEN" "/output/${OUTPUT_FILE-netbox.json}" -d "${DISCOVERY_TYPE-device}" -f "${CUSTOM_FIELD-prom_labels}" -p "${PORT-10000}}"; sleep "$INTERVAL"); done
