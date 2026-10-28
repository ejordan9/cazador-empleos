# 🎯 Cazador de Empleos Multiplataforma

> Bot inteligente de monitoreo de vacantes que rastrea automáticamente **LinkedIn, Indeed, Get on Board, CompuTrabajo y Canales de Telegram**, filtra por tus especialidades técnicas y modalidad deseada (100% Remoto, Freelance, Por Horas o Tiempo Completo), y te envía las mejores oportunidades en tiempo real a tu chat de **Telegram**.

---

## ✨ Características Principales

- 🌐 **Multiplataforma sin cuentas pagas**: Rastrea ofertas públicas en LinkedIn, Indeed, Get on Board, CompuTrabajo y Telegram sin requerir credenciales de usuario ni cuentas premium.
- 🎯 **Scoring inteligente por Keywords**: Evalúa cada oferta calculando coincidencias con tus herramientas y descarta palabras excluidas (ej. call center, ventas en frío, etc.).
- 💼 **Filtro de Contratación (Freelance / Tiempo Completo)**:
  - ¿Buscas proyectos adicionales por horas o freelance? Activa `only_freelance_or_part_time: true` y el sistema descartará automáticamente empleos corporativos de 40-48h semanales en nómina.
  - Distingue entre `💼 Freelance`, `⏱️ Part-time`, `⏳ Por horas` y `📁 Por proyecto`.
- 🌍 **Filtro de Modalidad y Ubicación**:
  - Acepta ofertas 100% remotas de cualquier país.
  - Si una oferta es presencial o híbrida, solo la acepta si está en tu ciudad configurada.
- 🗣️ **Filtro de Idioma**: Filtra ofertas redactadas en español (o el idioma que configures).
- 📱 **Notificaciones limpias en Telegram**: Mensajes agrupados con enlaces directos, distintivos de modalidad, salarios y formato Markdown.
- 🧠 **Anti-repetición (`seen_store`)**: Almacena las vacantes ya notificadas para que nunca recibas ofertas duplicadas.

---

## 🚀 Inicio Rápido (Guía Paso a Paso)

### 1. Clonar e Instalar Dependencias

```bash
# 1. Clona el repositorio o descarga la carpeta
git clone https://github.com/tu-usuario/cazador-empleos.git
cd cazador-empleos

# 2. Crea un entorno virtual de Python (versión 3.10 o superior)
python3 -m venv env
source env/bin/activate  # En Windows: env\Scripts\activate

# 3. Instala las librerías necesarias
pip install -r requirements.txt
```

---

### 2. Configurar el Bot de Telegram (Gratis, toma 2 minutos)

1. Abre Telegram y busca a [@BotFather](https://t.me/BotFather).
2. Envía el comando `/newbot`, dale un nombre (ej. *Mi Cazador de Empleos*) y un usuario (ej. *mi_empleos_bot*).
3. BotFather te responderá con un token (ej. `123456789:ABCdefGhIJKlmNoPQRstuVWXyz`).
4. Abre Telegram y busca a [@userinfobot](https://t.me/userinfobot), presiona **Start** y copia tu ID numérico (ej. `987654321`).
5. **Inicia una conversación con tu nuevo bot**: Búscalo en Telegram y presiona **Start** / **Iniciar** (para que tenga permiso de enviarte mensajes).
6. Crea tu archivo `.env` en la raíz del proyecto copiando el ejemplo:
   ```bash
   cp .env.example .env
   ```
7. Abre `.env` y coloca tu token y chat ID:
   ```env
   TELEGRAM_BOT_TOKEN="123456789:ABCdefGhIJKlmNoPQRstuVWXyz"
   TELEGRAM_CHAT_ID="987654321"
   ```

---

### 3. Configurar tus Búsquedas (`config.yaml`)

Copia la plantilla de configuración:
```bash
cp config.example.yaml config.yaml
```

Edita `config.yaml` con tus preferencias:
- **`profile.keywords`**: Lista de tecnologías, roles o herramientas que dominas (ej. `"python"`, `"react"`, `"meta ads"`, `"data analyst"`).
- **`profile.exclude`**: Términos que NO te interesan (ej. `"call center"`, `"practicante"`).
- **`filters.only_freelance_or_part_time`**:
  - `false`: Si buscas cualquier tipo de empleo (tiempo completo, nómina fija, etc.).
  - `true`: Si ya tienes trabajo fijo y solo quieres proyectos freelance, por horas o part-time.
- **`filters.allowed_locations_presencial_hibrido`**: Ciudades donde aceptarías ofertas presenciales o híbridas (ej. `["bogota", "bogotá"]`, `["medellin"]`, `["ciudad de mexico"]`).

---

### 4. Ejecutar el Scraper

```bash
python run.py
```

El script imprimirá en la terminal el progreso de cada portal, mostrará las vacantes que hicieron *match* y enviará automáticamente a tu Telegram las nuevas ofertas.

---

## ⏰ Automatización (Para que corra solo)

### Opción A: Con `systemd` (Linux / Servidores / Raspberry Pi)
En la carpeta `systemd/` incluimos plantillas listas para usar:

```bash
# 1. Copia los archivos a la carpeta de servicios de usuario
mkdir -p ~/.config/systemd/user
cp systemd/cazador-empleos.* ~/.config/systemd/user/

# 2. Edita cazador-empleos.service y pon la ruta absoluta de tu carpeta y de tu python:
# WorkingDirectory=/home/usuario/cazador-empleos
# ExecStart=/home/usuario/cazador-empleos/env/bin/python run.py

# 3. Activa el temporizador (corre 3 veces al día: 8am, 12pm, 5pm de lunes a viernes)
systemctl --user daemon-reload
systemctl --user enable --now cazador-empleos.timer
```

### Opción B: Con `cron` (Linux / macOS)
Abre tu crontab con `crontab -e` y agrega una línea para que corra de lunes a viernes a las 8:00 AM y 2:00 PM:
```cron
0 8,14 * * 1-5 cd /ruta/a/cazador-empleos && ./env/bin/python run.py >> /tmp/cazador.log 2>&1
```

---

## 🤖 Información Técnica y Arquitectura (Para Asistentes de IA y Desarrolladores)

> Si estás usando un modelo de lenguaje (ChatGPT, Claude, Cursor, Copilot) para ayudarte a adaptar este código, esta sección resume la arquitectura del proyecto para que la IA entienda todo el flujo sin ambigüedades.

### Diagrama del Pipeline

```
[Fuentes: LinkedIn / Indeed / GetOnBrd / Computrabajo / Telegram]
                           │
                           ▼
                  Opportunity (Model)
                           │
                           ▼
                 score(opp, keywords)  ──>  ¿score >= min_score?
                           │
                           ▼
                  is_spanish(text)     ──>  ¿Idioma español?
                           │
                           ▼
            is_location_allowed(opp)   ──>  ¿Remoto o Ciudad permitida?
                           │
                           ▼
        is_freelance_or_part_time(opp) ──>  ¿Cumple régimen horario?
                           │
                           ▼
                SeenStore.filter_new()  ──>  ¿No fue notificada antes?
                           │
                           ▼
            notify_new_opportunities()  ──>  Telegram Bot API
```

### Mapa de Archivos

- **`run.py`**: Orquestador principal. Carga `config.yaml`, instancia los colectores habilitados, itera vacantes, aplica los filtros secuencialmente y notifica.
- **`src/models.py`**: Dataclass `Opportunity` con los atributos normalizados (`fuente`, `empresa`, `rol`, `url`, `tipo`, `modalidad`, `ubicacion`, `presupuesto`, `descripcion`, `score`, `tags`).
- **`src/scoring.py`**: Algoritmo de puntuación por densidad de palabras clave y rechazo por lista negra.
- **`src/language_filter.py`**: Detección heurística de idioma para validar español.
- **`src/location_filter.py`**: Reglas de geolocalización. Las ofertas remotas pasan siempre; las presenciales/híbridas requieren coincidencia con las ciudades autorizadas.
- **`src/contract_filter.py`**: Clasificador avanzado con expresiones regulares. Detecta *freelance, contractor, prestación de servicios, por horas, banco de horas, part-time y por proyecto*. Descarta ofertas corporativas de tiempo completo o dedicación exclusiva si el modo freelance está activo.
- **`src/notifier.py`**: Cliente de Telegram directo usando `requests`. Lee credenciales de `.env` o variables de entorno y construye tandas de mensajes espaciados.
- **`src/seen_store.py`**: Almacén JSON persistente (`state/seen.json`) para deduplicación entre corridas.
- **`src/collectors/`**:
  - `getonbrd.py`: Scraper HTTP de Get on Board con soporte para filtros de categoría.
  - `jobspy_source.py`: Colector de LinkedIn usando `python-jobspy` (endpoints públicos de búsqueda de invitados).
  - `indeed.py`: Colector de Indeed usando `python-jobspy`.
  - `computrabajo.py`: Scraper para portales de CompuTrabajo en Latinoamérica.
  - `telegram_channel.py`: Lector de canales públicos de Telegram vía scraping web público (`t.me/s/...`) sin necesidad de cuenta.
  - `torre.py`: Colector para Torre AI (opcional).

### Pruebas Unitarias

Para verificar la integridad de todos los filtros:
```bash
python -m unittest discover tests
```

---

## 📄 Licencia

Distribuido bajo la licencia MIT. Uso libre para fines personales, comunitarios o comerciales. ¡Éxito en la cacería de oportunidades! 🚀
