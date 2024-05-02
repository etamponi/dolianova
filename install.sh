#!/bin/bash
set -e

sudo echo "Root access obtained"

# Remove old installation if it exists
rm -rf /opt/dolianova

cd /opt/
git clone https://github.com/etamponi/dolianova.git
cd dolianova
# Create virtual environment
python3 -m venv .venv
# Install required packages
source .venv/bin/activate
pip install -r requirements.txt
# Install RPi.GPIO and lgpio only on the Raspberry Pi
if [ -f /proc/device-tree/model ]; then
  if grep -q "Raspberry Pi" /proc/device-tree/model; then
    pip install RPi.GPIO lgpio
  fi
fi
deactivate

sudo cp dolianova /usr/local/bin
sudo cp dolianova.service /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable dolianova.service
sudo systemctl start dolianova.service
