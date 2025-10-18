# PHP Installer (GUI)

Instalador gráfico para Windows que descarga e instala versiones oficiales de PHP.

Proyecto sin fines de lucro y de código abierto: el objetivo es apoyar a la comunidad. El código está disponible para uso, estudio y contribución; consulta la licencia del repositorio para más detalles.

## ¿Qué hace y cómo funciona?

Interfaz tipo asistente (PyQt6) que guía por estos pasos:
1. Seleccionar la versión de PHP (se intenta obtenerla automáticamente desde php.net).
2. Ver opciones de builds para Windows (si están disponibles en windows.php.net).
3. Elegir la carpeta de instalación y si añadir PHP al PATH.
4. Mostrar progreso de descarga y un log durante la instalación.
5. Registrar la instalación en Windows y crear un script `uninstall.bat`.

Bajo el capó:
- Descarga el ZIP oficial desde servidores de PHP.
- Extrae el contenido en la carpeta seleccionada.
- Opcionalmente añade la carpeta al PATH del usuario (usa `setx`).
- Crea entrada de desinstalación en el registro y un `uninstall.bat`.
- No realiza verificación de firmas/checksums por defecto.

## Requisitos

- Windows (usa `winreg`, `setx` y rutas de Windows).
- Python 3.8+.
- Dependencias (requirements.txt):
  - PyQt6
  - requests
  - pyinstaller (opcional, para crear el ejecutable)

## Estructura relevante

- php_installer.spec
- php_installer.exe
- build/
- dist/
- Code/
  - main.py
  - php.ico
  - requirements.txt
  - assets/

## Instalación de dependencias (PowerShell)

```powershell
cd <ruta-del-repo>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
if (Test-Path requirements.txt) { pip install -r requirements.txt } else { pip install -r Code\requirements.txt }
```

## Ejecutar en modo desarrollo

```powershell
# desde la raíz
python Code\main.py

# o dentro de Code/
cd Code
python main.py
```

## Compilar a ejecutable (PyInstaller)

```powershell
cd Code
python -m PyInstaller --onefile --noconsole --icon=php.ico --add-data "assets;assets" --name php_installer main.py
# El .exe quedará en ../dist/php_installer.exe
```

Notas:
- Con `--onefile`, los recursos se extraen en tiempo de ejecución vía `sys._MEIPASS` (ya manejado en `main.py`).
- Modificar PATH del sistema o escribir en HKLM requiere ejecutar como Administrador.
- Cambios en PATH pueden requerir reiniciar sesión para verse reflejados.

## Cómo contribuir

- Reporta issues, envía PRs y sugiere mejoras (detección de builds, verificación de integridad, etc.).
- Se agradecen traducciones, mejoras de UX y pruebas en distintas versiones de Windows.
- Si se desea, se puede:
  - actualizar el README de la raíz para enlazar a este;
  - añadir un `run.ps1` que active el venv e inicie la app;
  - documentar pruebas y creación del instalador paso a paso.
