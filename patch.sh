#!/usr/bin/env sh
set -e
cd $(dirname "$0")

DRIVER_DIR="/usr/lib/python3/dist-packages/provisioningserver/drivers/power"
sudo patch -d ${DRIVER_DIR} -p5 < hs300.patch
sudo cp hs300.py ${DRIVER_DIR}/
sudo service maas-regiond restart && sudo service maas-rackd restart
