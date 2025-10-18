# PHP Installer (GUI)

Instalador gráfico para Windows que descarga e instala versiones oficiales de PHP.

Este proyecto fue desarrollado sin fines de lucro como una contribución a la comunidad de desarrolladores y programadores.

## ¿Qué hace?

- Proporciona una interfaz gráfica (PyQt6) tipo asistente que guía al usuario por los pasos:
  1. Seleccionar la versión de PHP (se intenta obtener una lista de php.net automáticamente).
  2. Ver opciones de builds para Windows (si están disponibles en el índice de windows.php.net).
  3. Elegir la ruta de instalación y si añadir PHP al PATH del sistema.
  4. Mostrar progreso de descarga y un log durante la instalación.
  5. Registrar la instalación en el registro de Windows y crear un script `uninstall.bat`.

- Descarga el archivo (zip o tarball) desde los servidores oficiales.
- Extrae el contenido en la carpeta seleccionada o mueve el archivo si es un tarball.
- Opcionalmente añade la carpeta de instalación al `PATH` del sistema (usa `setx` en Windows).
- Crea un registro de desinstalación en el registro de Windows y un `uninstall.bat` en la carpeta de instalación.

## Requisitos

- Windows (diseñado para Windows; partes específicas usan `winreg` y `setx`).
- Python 3.8+
- Dependencias (incluidas en `requirements.txt`):
  - PyQt6
  - requests
  - pyinstaller (opcional, solo para crear el ejecutable)

Instalación de dependencias (recomendado dentro de un virtualenv):

## Instalador gráfico de PHP (Windows)

Este README dentro de `instalador/Carpeta` fue adaptado para describir lo que hay realmente en este repositorio y cómo ejecutar/compilar la pequeña aplicación GUI que descarga e instala PHP en Windows.

Resumen rápido
- El script principal (interfaz) está en: `Code/main.py` (PyQt6 + requests).
- Recursos (icono e imágenes) están en la carpeta `Code/assets`.
- Hay artefactos de build en `build/` y `dist/` (si ya generaste un exe).
- En la raíz del repositorio puede haber `php_installer.spec`, `php_installer.exe` y un `README.md` general.

Estructura relevante (ejemplo):

- php_installer.spec  (PyInstaller spec, opcional)
- php_installer.exe   (ejecutable generado)
- build/              (temporal de PyInstaller)
- dist/               (ejecutable generado por PyInstaller)
- Code/               (código fuente)
  - main.py           (entrypoint de la GUI)
  - php.ico           (icono usado para el exe)
  - requirements.txt  (dependencias del proyecto)
  - assets/           (imágenes y recursos empaquetables)

Requisitos

- Windows (la aplicación usa `winreg`, `setx` y rutas tipo Windows).
- Python 3.8+ (recomendado 3.8 — 3.11+ debería funcionar).
- Paquetes: PyQt6, requests. Si quieres crear el ejecutable, instala PyInstaller.

Instalar dependencias (PowerShell)

Primero crea y activa un virtualenv y luego instala requisitos. Dependiendo de dónde esté tu `requirements.txt`, usa la ruta adecuada. Ejemplos:

```powershell
cd <ruta-del-repo>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
# si tienes requirements en la raíz
if (Test-Path requirements.txt) { pip install -r requirements.txt } else { pip install -r Code\requirements.txt }
```

Ejecutar en modo desarrollo

Desde la raíz del repo (o desde `Code/`):

```powershell
# desde la raíz
python Code\main.py

# o, si estás dentro de Code/
cd Code
python main.py
```

Compilar a ejecutable con PyInstaller (Windows)

Si quieres generar un `.exe` sin consola y con recursos embebidos, ejecuta PyInstaller desde `Code/` para que las rutas relativas a `assets/` y `php.ico` funcionen fácilmente:

```powershell
cd Code
python -m PyInstaller --onefile --noconsole --icon=php.ico --add-data "assets;assets" --name php_installer main.py

# El exe resultante quedará en ../dist/php_installer.exe (o en dist/ si ejecutas desde Code/)
```

Notas sobre PyInstaller y recursos

- Cuando uses `--onefile`, PyInstaller extrae los recursos en tiempo de ejecución en una carpeta temporal accesible como `sys._MEIPASS` cuando `getattr(sys, 'frozen', False)` es True. `Code/main.py` ya incluye el patrón para resolver rutas según si está "frozen" o no.

Seguridad, permisos y límites

- Escribir en el registro (HKLM) o modificar variables de entorno a nivel máquina requiere permisos elevados (ejecutar como Administrador).
- `setx` modifica la variable de entorno del usuario; para que los cambios estén disponibles en sesiones ya abiertas puede requerirse reinicio o re-login.
- La descarga y extracción de binarios no valida firmas/checksums automáticamente. Si necesitas garantías, complementa con verificación de hashes.

Cómo contribuir

- Corrige localizaciones, mejora la detección de builds de Windows, añade verificación de integridad o soporte multiplataforma.
- Abre un issue o PR en el repositorio con cambios propuestos.

Si quieres, puedo:

- actualizar también el `README.md` de la raíz para que haga referencia a este sub-README;
- añadir un pequeño script `run.ps1` que active el venv e inicie la app;
- generar una guía paso-a-paso para crear el instalador y probar en un sistema Windows.

-- Fin del README adaptado
