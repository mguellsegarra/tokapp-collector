# Notes sobre el protocol de TokApp

El collector es basa en el protocol observat al client Android 5.0.0, paquet
`com.MultiExpo.pulpiandroid`. No fa servir l'API documentada del panell de centres.
Aquestes notes descriuen la base de la implementació; no certifiquen el
funcionament actual del servei.

## Peticions

Les peticions són formularis HTTP POST a `https://app.tokapp.net/?`, amb les
capçaleres `PLATAFORMA: android`, `VERSION: 5.0.0` i `APPNAME: tokapp`.
Després del login s'hi afegeix `SESSION`, amb la clau retornada pel servidor.
El collector comprova els certificats TLS amb la configuració estàndard de Python.

| Operació | Endpoint | Camps |
| --- | --- | --- |
| Login | `c=Login&a=Login` | `username`, `passwordHash`, `get_perfil=1` |
| Missatges pendents | `c=Chat&a=gm` | `idc=0`, `idg=0`, `esc=0`, `ui` |
| Confirmació de recepció | `c=Chat&a=SetMensajesRecibidos` | `ids`, separats per comes |

`passwordHash` és el MD5 de la contrasenya en hexadecimal. Forma part del protocol
existent; el collector no desa aquest hash ni la sessió en fitxers de dades.
La resposta de login inclou `sessionKey` i `login`, l'identificador d'usuari.

La resposta de sincronització conté `getmensajes`. Els camps que es llegeixen són:

- Identificació: `id`, `id_contacto`, `id_grupo`.
- Contingut: `mensaje`, `momento`, `nombreRemitente` o `nombre_remitente`.
- Metadades: `tipo_adjunto`, `url_adjunto`, `miniatura`, `ubicacion`, `evento`.

El JSON original queda al registre del missatge. Pot contenir més dades que les
que el collector interpreta.

## Recepció, lectura i historial

La confirmació de recepció i la marca de lectura són operacions separades.
El collector només implementa la primera, desactivada per defecte. No crida
`SetMensajesLeidos` ni envia res a altres usuaris de TokApp.

`gm` és una sincronització de missatges pendents, no una API d'historial complet.
L'aplicació del mòbil pot consumir els missatges abans que el collector els
consulti. No es pot prometre que totes dues instàncies rebin sempre el mateix.

## Push i artefactes

El client Android utilitza Firebase Cloud Messaging. El collector fa polling;
no registra un altre token de push ni modifica la configuració de notificacions
del compte.

Els APKs, el codi descompilat i les captures utilitzats durant l'anàlisi queden
fora del projecte distribuïble. No són necessaris per executar-lo i no s'han
d'incloure en una publicació.
