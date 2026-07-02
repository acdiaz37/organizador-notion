# Guía: Múltiples bots en el VPS

## VPS actual

- **IP:** 79.143.89.8
- **Usuario para bots:** `deportibot`
- **Llave SSH:** `~/.ssh/default.pem`
- **Sistema:** Ubuntu (clouding.io)
- **Recursos:** 0.5 vcores, 1 GB RAM, 15 GB SSD, 1 GB swap

## Regla de oro

Cada bot vive en su **propia carpeta** con su **propio entorno virtual**, su **propia base de datos**, su **propio `.env`** y sus **propios cronjobs**.

No se comparten `.venv`, ni `.env`, ni bases de datos entre bots.

## Estructura recomendada

```
/home/deportibot/
├── deportibot/              # Bot actual (DeportiBot)
│   ├── .env
│   ├── .venv/
│   ├── data/
│   ├── logs/
│   ├── agents/
│   ├── scripts/
│   └── requirements.txt
│
└── otrobot/                 # Nuevo bot
    ├── .env
    ├── .venv/
    ├── data/
    ├── logs/
    ├── main.py
    └── requirements.txt
```

## Pasos para agregar un nuevo bot

### 1. Conectarse al VPS

```bash
ssh -i ~/.ssh/default.pem deportibot@79.143.89.8
```

### 2. Crear carpeta del nuevo bot

```bash
cd /home/deportibot
mkdir otrobot
cd otrobot
```

### 3. Subir archivos del bot

Desde tu PC:

```bash
rsync -avz -e "ssh -i ~/.ssh/default.pem" \
  --exclude='.venv' --exclude='__pycache__' --exclude='.git' \
  --exclude='.env' /ruta/del/nuevo/bot/ \
  deportibot@79.143.89.8:/home/deportibot/otrobot/
```

Luego subir el `.env` por separado:

```bash
scp -i ~/.ssh/default.pem /ruta/del/nuevo/bot/.env \
  deportibot@79.143.89.8:/home/deportibot/otrobot/.env
```

### 4. Proteger el `.env`

Dentro del VPS:

```bash
cd /home/deportibot/otrobot
chmod 600 .env
```

### 5. Crear entorno virtual propio

```bash
cd /home/deportibot/otrobot
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 6. Probar ejecución manual

```bash
cd /home/deportibot/otrobot
source .venv/bin/activate
python3 main.py
```

### 7. Automatizar con cron

Ver crontab actual:

```bash
crontab -l
```

Agregar tareas propias del nuevo bot:

```bash
crontab -e
```

Ejemplo:

```cron
# Nuevo bot - otrobot
0 10 * * * cd /home/deportibot/otrobot && source .venv/bin/activate && python3 main.py >> logs/otrobot.log 2>&1
```

## Conexión para un agente de IA

Si un asistente de IA (como Kimi Code) va a administrar el VPS, debe usar:

```bash
ssh -i /home/adrian/.ssh/default.pem deportibot@79.143.89.8
```

### Comandos útiles para el agente

```bash
# Ver espacio en disco
df -h

# Ver uso de RAM
free -h

# Ver procesos activos
htop

# Ver logs de DeportiBot
tail -f /home/deportibot/deportibot/logs/run_daily.log

# Ver cronjobs del usuario
crontab -l
```

### Reglas para el agente

1. Nunca modificar el `.env` de un bot sin confirmación del usuario.
2. Nunca compartir tokens, contraseñas ni llaves privadas.
3. Siempre verificar espacio en disco antes de instalar dependencias grandes.
4. Si se instala un nuevo bot, debe tener su propio `.venv` y no compartirlo.
5. Probar manualmente antes de agregar al cron.

## Límites del VPS

| Recurso | Disponible | Observación |
|---------|------------|-------------|
| RAM | 1 GB | Justo. Si un segundo bot usa Playwright/navegador, puede fallar. |
| Swap | 1 GB | Salva de quedarse sin RAM, pero es lento. |
| CPU | 0.5 vcores | Procesos lentos, pero funcionan. |
| SSD | 8.3 GB libres | Suficiente para varios bots pequeños. |

### Recomendación

- Si el nuevo bot es **simple** (APIs, mensajes, lectura de datos): **sí cabe**.
- Si el nuevo bot usa **Playwright/Chromium**: evaluar aumentar RAM a 2 GB o usar otro VPS.

## Verificación rápida

Para confirmar que dos bots están separados:

```bash
ls -la /home/deportibot/
```

Deberías ver carpetas distintas, cada una con su propio `.venv` y `.env`.
