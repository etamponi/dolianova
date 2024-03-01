# WaterSystemController

## Installazione

1. Assicurati che git sia installato (`sudo apt install git`).
1. Assicurati che il file di configurazione `water_system_config.json` contenga
   la giusta configurazione dei pin.
2. Copia il file `dolianova` nella directory `/usr/local/bin/`.
3. Copia il file `dolianova.service` nella directory `/etc/systemd/system/`.
4. Esegui i seguenti comandi:
   ```
   sudo systemctl daemon-reload
   sudo systemctl enable dolianova.service
   sudo systemctl start dolianova.service
   ```
