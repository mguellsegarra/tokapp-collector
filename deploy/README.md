# Execució contínua

Instal·la el projecte en un directori persistent amb la seva `.venv`, `.env` i
configuració local. Valida primer `doctor` i un cicle `once`, tal com explica el
[README](../README.md). Executa només una instància per compte i directori de dades.

No copiïs `.git`, captures, APKs ni sortides d'anàlisi al servidor. Transfereix les
credencials per un canal privat i restringeix els permisos de `.env`, les regles
locals i les còpies de seguretat. Les dades escolars es desen sense xifrar.

## PM2

La configuració `ecosystem.config.js` resol el directori del projecte a partir de
la ubicació del mateix fitxer. Requereix PM2 instal·lat i una `.venv` amb el
collector a l'arrel del projecte.

```bash
pm2 start ecosystem.config.js
pm2 status tokapp-collector
pm2 logs tokapp-collector --lines 50
```

Si vols conservar la llista de processos per als reinicis, executa `pm2 save`.
La recuperació després de reiniciar la màquina requereix que PM2 ja tingui el seu
servei d'arrencada configurat. Consulta `pm2 startup` per a la teva plataforma.

## systemd d'usuari

La unitat `systemd/tokapp-collector.service` fa servir aquests directoris:

| Element | Ubicació |
| --- | --- |
| Projecte i entorn virtual | `~/apps/tokapp-collector` |
| Fitxer d'entorn | `~/.config/tokapp-collector/env` |
| Regles personals | `~/.config/tokapp-collector/rules.json` |
| Dades persistents | `~/.local/share/tokapp-collector` |

Prepara els directoris i copia les plantilles:

```bash
mkdir -p ~/.config/tokapp-collector ~/.local/share/tokapp-collector
mkdir -p ~/.config/systemd/user
cp .env.example ~/.config/tokapp-collector/env
cp config/rules.json ~/.config/tokapp-collector/rules.json
cp deploy/systemd/tokapp-collector.service ~/.config/systemd/user/
chmod 700 ~/.config/tokapp-collector ~/.local/share/tokapp-collector
chmod 600 ~/.config/tokapp-collector/env ~/.config/tokapp-collector/rules.json
```

Edita el fitxer d'entorn amb les credencials i les rutes absolutes de `DATA_DIR` i
`RULES_PATH`. Substitueix el teu directori personal en aquest exemple; systemd no
expandeix `$HOME` dins d'`EnvironmentFile`:

```dotenv
DATA_DIR=/home/usuari/.local/share/tokapp-collector
RULES_PATH=/home/usuari/.config/tokapp-collector/rules.json
```

Posa el projecte a `~/apps/tokapp-collector` o adapta `WorkingDirectory` i
`ExecStart` de la unitat. Després:

```bash
systemctl --user daemon-reload
systemctl --user enable --now tokapp-collector
systemctl --user status tokapp-collector
journalctl --user -u tokapp-collector -n 50
```

L'arrencada sense una sessió oberta depèn de la configuració del gestor d'usuari
systemd de la màquina. No iniciïs també el procés amb PM2.
