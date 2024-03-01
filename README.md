# WaterSystemController

## Installazione

1. Assicurati che git sia installato (`sudo apt install git`).
2. Assicurati che il file di configurazione `water_system_config.json` contenga
   la giusta configurazione dei pin.
3. Copia il file `dolianova` nella directory `/usr/local/bin/`.
4. Copia il file `dolianova.service` nella directory `/etc/systemd/system/`.
5. Esegui i seguenti comandi:
   ```
   sudo systemctl daemon-reload
   sudo systemctl enable dolianova.service
   sudo systemctl start dolianova.service
   ```
