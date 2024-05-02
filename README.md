# Sistema potabilizzazione acqua di Bruncu

## Installazione

1. Esegui:
   ```
   git clone https://github.com/etamponi/dolianova.git
   sudo dolianova/install.sh
   ```

2. Assicurati che il file di configurazione `/opt/dolianova/water_system_config.json`
   contenga la giusta configurazione dei pin e dei timing.

3. Esegui `sudo systemctl start dolianova.service`

## Monitoraggio

Per vedere lo stato del servizio:
```
journalctl -u dolianova -f
```

## Reset del sistema

Per resettare lo stato del sistema (in modo che ricominci "daccapo"):
```
sudo systemctl stop dolianova
sudo rm /opt/dolianova/water_system_state.json
sudo systemctl start dolianova
```
