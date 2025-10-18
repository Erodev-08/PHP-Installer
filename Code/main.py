"""
php_installer.py
Instalador GUI para descargar e instalar PHP (Windows-focused) usando PyQt6.
Requiere: PyQt6, requests
pip install PyQt6 requests
"""

import sys
import os
import re
import shutil
import zipfile
import subprocess
from urllib.parse import urljoin
from pathlib import Path
import winreg

import requests
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QFileDialog, QProgressBar,
    QMessageBox, QStackedWidget, QCheckBox, QLineEdit, QTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTranslator
from PyQt6.QtGui import QPixmap
from PyQt6.QtGui import QIcon

# ---------- Config ----------
PHP_DOWNLOADS_PAGE = "https://www.php.net/downloads.php"
WINDOWS_RELEASES_BASE = "https://windows.php.net/downloads/releases/"

# Regex para extraer posibles versiones (simple, para listar opciones)
VERSION_RE = re.compile(r"\b[1-9]\d?\.\d+(?:\.\d+)?\b")

# ---------- Worker Threads ----------
class FetchVersionsThread(QThread):
    done = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self):
        try:
            versions = set()
            # 1) Intentar leer la página principal de php.net/downloads.php
            r = requests.get(PHP_DOWNLOADS_PAGE, timeout=15)
            r.raise_for_status()
            versions.update(VERSION_RE.findall(r.text))

            # 2) Intentar leer el índice de windows.php.net/downloads/releases/ (listado)
            try:
                r2 = requests.get(WINDOWS_RELEASES_BASE, timeout=15)
                if r2.ok:
                    versions.update(VERSION_RE.findall(r2.text))
            except Exception:
                # no crítico; seguimos con lo encontrado en php.net
                pass

            # Ordenar versions semánticamente simple (split)
            def ver_key(v):
                parts = [int(x) for x in v.split(".")]
                while len(parts) < 3: parts.append(0)
                return parts
            sorted_versions = sorted(set(versions), key=ver_key, reverse=True)
            self.done.emit(sorted_versions)
        except Exception as e:
            self.error.emit(str(e))


class DownloadAndInstallThread(QThread):
    progress = pyqtSignal(int)            # porcentaje
    log = pyqtSignal(str)
    finished_success = pyqtSignal(str)
    finished_error = pyqtSignal(str)

    def __init__(self, download_url: str, target_dir: str, add_to_path: bool):
        super().__init__()
        self.download_url = download_url
        self.target_dir = target_dir
        self.add_to_path = add_to_path

    def run(self):
        try:
            self.log.emit(f"Verificando conectividad con {self.download_url}")
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Validar conectividad antes de descargar
                    resp = requests.head(self.download_url, timeout=30)
                    resp.raise_for_status()
                    self.log.emit("Conexión exitosa. Iniciando descarga...")
                    break
                except requests.exceptions.RequestException as e:
                    if attempt < max_retries - 1:
                        self.log.emit(f"Intento {attempt + 1} fallido: {e}. Reintentando...")
                    else:
                        self.log.emit("No se pudo establecer conexión con el servidor principal.")
                        self.log.emit("Intentando servidor alternativo...")
                        self.download_url = f"https://www.php.net/distributions/php-{self.download_url.split('-')[1]}.tar.gz"
                        self.log.emit(f"Nuevo URL: {self.download_url}")

            # Descargar archivo
            self.log.emit(f"Descargando {self.download_url}")
            for attempt in range(max_retries):
                try:
                    resp = requests.get(self.download_url, stream=True, timeout=60)
                    resp.raise_for_status()
                    break
                except requests.exceptions.RequestException as e:
                    if attempt < max_retries - 1:
                        self.log.emit(f"Intento {attempt + 1} fallido: {e}. Reintentando...")
                    else:
                        self.log.emit("No se pudo descargar el archivo.")
                        self.finished_error.emit(f"Error de descarga: {e}. Por favor, descarga manualmente desde {self.download_url}")
                        return

            total = resp.headers.get("Content-Length")
            if total is None:
                total = 0
            else:
                total = int(total)

            fname = self.download_url.rstrip("/").split("/")[-1]
            tmp_path = Path.cwd() / fname
            # Descargar con chunks y actualizar progreso
            downloaded = 0
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            self.progress.emit(int(downloaded * 100 / total))

            self.progress.emit(100)
            self.log.emit("Descarga completa. Extrayendo...")

            # Si es zip: extraer
            if zipfile.is_zipfile(tmp_path):
                with zipfile.ZipFile(tmp_path, "r") as zf:
                    target_path = Path(self.target_dir).expanduser().resolve()
                    target_path.mkdir(parents=True, exist_ok=True)
                    zf.extractall(target_path)
                    installed_path = str(target_path)
                    self.log.emit(f"Extraído en {installed_path}")
            else:
                # si no es zip - solo mover el archivo (ej. tar.gz)
                target_path = Path(self.target_dir).expanduser().resolve()
                target_path.mkdir(parents=True, exist_ok=True)
                shutil.move(str(tmp_path), str(target_path / fname))
                installed_path = str(target_path)
                self.log.emit(f"Archivo guardado en {installed_path}")

            # Borrar archivo temporal si aún existe
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    self.log.emit("No se pudo eliminar el archivo temporal.")

            # Añadir a PATH si el usuario lo pidió
            if self.add_to_path:
                try:
                    self.log.emit("Añadiendo PHP al PATH...")
                    subprocess.run(["setx", "PATH", f"%PATH%;{installed_path}"], check=True)
                except subprocess.CalledProcessError as e:
                    self.log.emit(f"Error al añadir al PATH: {e}")
                except Exception as e:
                    self.log.emit(f"Error inesperado al añadir al PATH: {e}")

            self.finished_success.emit(installed_path)
        except Exception as e:
            self.finished_error.emit(str(e))


# ---------- UI ----------
class WizardPage(QWidget):
    def __init__(self, layout=None):
        super().__init__()
        if layout is None:
            layout = QVBoxLayout()
        self.setLayout(layout)

class PHPInstaller(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Setup Installer PHP")
        icon_path = os.path.join(os.path.dirname(__file__), "php.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.resize(700, 480)

        central = QWidget()
        main_layout = QVBoxLayout()
        central.setLayout(main_layout)
        self.setCentralWidget(central)

        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack)

        # pages
        self.page_welcome()
        self.page_select_version()
        self.page_select_build()
        self.page_choose_path()
        self.page_progress()
        self.page_finish()

        # bottom buttons
        btn_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_back = QPushButton("Anterior")
        self.btn_next = QPushButton("Siguiente")

        btn_layout.addWidget(self.btn_cancel)
        
        btn_layout.addStretch()
        
        main_layout.addLayout(btn_layout)
        btn_layout.addWidget(self.btn_back)
        btn_layout.addWidget(self.btn_next)
        self.btn_cancel.clicked.connect(self.on_cancel)
        self.btn_back.clicked.connect(self.go_back)
        self.btn_next.clicked.connect(self.go_next)

        # estado
        self.current_index = 0
        self.update_buttons()

        # Cargar versiones en background
        self.fetch_thread = FetchVersionsThread()
        self.fetch_thread.done.connect(self.on_versions_fetched)
        self.fetch_thread.error.connect(self.on_fetch_error)
        self.fetch_thread.start()

        # placeholders
        self.selected_version = None
        self.selected_build_url = None

    # Page 0: Welcome
    def page_welcome(self):
        w = WizardPage(QVBoxLayout())
        h_layout = QHBoxLayout()

        # Layout horizontal para imagen a la izquierda y texto a la derecha
        img_path = os.path.join(os.path.dirname(__file__), "assets/php_installer.png")
        if os.path.exists(img_path):
            img_label = QLabel()
            pixmap = QPixmap(img_path)
            pixmap = pixmap.scaledToHeight(100, Qt.TransformationMode.SmoothTransformation)
            img_label.setPixmap(pixmap)
            img_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            h_layout.addWidget(img_label)

        # Texto a la derecha
        text_layout = QVBoxLayout()
        text_layout.addWidget(QLabel("<h2>Instalador de PHP</h2>"))

        text_layout.addWidget(QLabel("Este asistente te permitirá descargar versiones oficiales de PHP, instalarla en una carpeta y añadir php al PATH."))

        text_layout.addStretch()
        h_layout.addLayout(text_layout)

        w.layout().addLayout(h_layout)
        w.layout().addStretch()
        self.stack.addWidget(w)

    # Page 1: Select version (populated by fetch)
    def page_select_version(self):
        w = WizardPage(QVBoxLayout())
        w.layout().addWidget(QLabel("<b>1) Selecciona la versión de PHP</b>"))
        self.version_combo = QComboBox()
        self.version_combo.addItem("Cargando versiones...")
        w.layout().addWidget(self.version_combo)
        self.version_manual = QLineEdit()
        w.layout().addStretch()
        self.stack.addWidget(w)

    # Page 2: Build selection
    def page_select_build(self):
        w = WizardPage(QVBoxLayout())
        w.layout().addWidget(QLabel("<b>2) Opciones de build</b>"))

        # Texto informativo
        info_label = QLabel("Si hay builds Windows disponibles, se listarán abajo. Selecciona la arquitectura y tipo de build preferido.")
        info_label.setWordWrap(True)
        w.layout().addWidget(info_label)

        # Builds encontrados
        self.build_text = QTextEdit()
        self.build_text.setReadOnly(True)
        self.build_text.setFixedHeight(120)
        w.layout().addWidget(self.build_text)

        # Opciones de arquitectura y tipo
        options_group = QWidget()
        options_layout = QHBoxLayout()
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_group.setLayout(options_layout)

        arch_group = QWidget()
        arch_layout = QVBoxLayout()
        arch_layout.setContentsMargins(0, 0, 0, 0)
        arch_group.setLayout(arch_layout)
        arch_layout.addWidget(QLabel("Arquitectura:"))
        self.cb_x64 = QCheckBox("x64")
        self.cb_x86 = QCheckBox("x86")
        arch_layout.addWidget(self.cb_x64)
        arch_layout.addWidget(self.cb_x86)

        type_group = QWidget()
        type_layout = QVBoxLayout()
        type_layout.setContentsMargins(0, 0, 0, 0)
        type_group.setLayout(type_layout)
        type_layout.addWidget(QLabel("Tipo de build:"))
        self.cb_ts = QCheckBox("Thread Safe (TS)")
        self.cb_nts = QCheckBox("Non Thread Safe (NTS)")
        type_layout.addWidget(self.cb_ts)
        type_layout.addWidget(self.cb_nts)

        options_layout.addWidget(arch_group)
        options_layout.addSpacing(30)
        options_layout.addWidget(type_group)
        options_layout.addStretch()

        w.layout().addWidget(options_group)
        w.layout().addStretch()
        self.stack.addWidget(w)

    # Page 3: Choose install path & Path option
    def page_choose_path(self):
        w = WizardPage(QVBoxLayout())
        w.layout().addWidget(QLabel("<b>3) Ruta de instalación</b>"))

        # Layout para la ruta y el botón
        path_group = QWidget()
        path_layout = QHBoxLayout()
        path_layout.setContentsMargins(0, 0, 0, 0)
        self.path_line = QLineEdit(str(Path.home() / "php"))
        btn_browse = QPushButton("Examinar...")
        btn_browse.setFixedWidth(100)
        btn_browse.clicked.connect(self.browse_folder)
        path_layout.addWidget(self.path_line)
        path_layout.addWidget(btn_browse)
        path_group.setLayout(path_layout)
        w.layout().addWidget(path_group)

        # Espaciado vertical
        w.layout().addSpacing(15)

        # Checkbox para añadir al PATH
        self.chk_add_path = QCheckBox("Añadir PHP al PATH del sistema (recomendado en Windows)")
        self.chk_add_path.setChecked(True)
        w.layout().addWidget(self.chk_add_path)

        w.layout().addStretch()
        self.stack.addWidget(w)

    # Page 4: Progress
    def page_progress(self):
        w = WizardPage(QVBoxLayout())
        w.layout().addWidget(QLabel("<b>4) Instalando...</b>"))

        # Layout horizontal para barra de progreso y porcentaje
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        w.layout().addWidget(self.progress_bar)

        # Caja de log expandible
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(120)
        self.log_box.setMaximumHeight(220)
        w.layout().addWidget(self.log_box)

        w.layout().addStretch()
        self.stack.addWidget(w)

        # Actualizar formato de la barra de progreso
        self.progress_bar.valueChanged.connect(
            lambda v: self.progress_bar.setFormat(f"{v}%")
        )

    # Page 5: Finish
    def page_finish(self):
        w = WizardPage(QVBoxLayout())
        w.layout().addSpacing(30)
        title = QLabel("<h2>¡Instalación completada!</h2>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        w.layout().addWidget(title)

        w.layout().addSpacing(15)
        self.finish_label = QLabel("")
        self.finish_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.finish_label.setWordWrap(True)
        w.layout().addWidget(self.finish_label)

        w.layout().addSpacing(20)
        info = QLabel("Puedes cerrar el instalador o abrir una nueva terminal para usar PHP.")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setWordWrap(True)
        w.layout().addWidget(info)

        w.layout().addStretch()
        self.stack.addWidget(w)

    def browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Selecciona carpeta de instalación", str(Path.home()))
        if path:
            self.path_line.setText(path)

    def on_cancel(self):
        """Handle Cancel button: ask for confirmation. If an installation is in progress, show a stronger warning and attempt to stop the thread if confirmed."""
        # If currently on the progress page (installation running), warn user
        installing_index = 4  # index of the progress/installation page in the stack
        if getattr(self, 'download_thread', None) is not None and self.current_index == installing_index:
            reply = QMessageBox.question(
                self,
                "Cancelar instalación",
                "Hay una instalación en curso. Cancelar puede dejar una instalación incompleta. ¿Deseas continuar y cancelar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    # Try to stop the thread if possible. terminate() is forceful; prefer request to quit if implemented.
                    if hasattr(self.download_thread, 'terminate'):
                        self.download_thread.terminate()
                    if hasattr(self.download_thread, 'wait'):
                        self.download_thread.wait(2000)
                except Exception:
                    pass
                self.close()
        else:
            reply = QMessageBox.question(
                self,
                "Confirmación",
                "¿Estás seguro que deseas cancelar el asistente?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.close()

    def update_buttons(self):
        self.stack.setCurrentIndex(self.current_index)
        self.btn_back.setEnabled(self.current_index > 0 and self.current_index < self.stack.count()-1)
        self.btn_next.setEnabled(self.current_index < self.stack.count()-1)
        self.btn_cancel.setEnabled(True)

    def go_back(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.update_buttons()

    def go_next(self):
        # validar y avanzar
        if self.current_index == 0:
            self.current_index += 1
        elif self.current_index == 1:
            # elegir versión
            manual = self.version_manual.text().strip()
            if manual:
                version = manual
            else:
                version = self.version_combo.currentText().strip()
                if not version or version.startswith("Cargando"):
                    QMessageBox.warning(self, "Error", "Selecciona una versión válida.")
                    return
            self.selected_version = version
            # poblar información de builds
            self.populate_build_info(version)
            self.current_index += 1
        elif self.current_index == 2:
            # build options chosen
            try:
                url = self.find_selected_build_url()
                if not url:
                    QMessageBox.warning(self, "Error", "No se pudo determinar el build seleccionado.")
                    return
                self.selected_build_url = url
            except Exception as e:
                QMessageBox.warning(self, "Error", f"No se pudo determinar el build: {e}")
                return
            self.current_index += 1
        elif self.current_index == 3:
            # confirm path and start download/install
            target_dir = self.path_line.text().strip()
            if not target_dir:
                QMessageBox.warning(self, "Error", "Selecciona una ruta de instalación.")
                return
            add_to_path = self.chk_add_path.isChecked()
            download_url = self.selected_build_url
            if not download_url:
                fallback = f"https://www.php.net/distributions/php-{self.selected_version}.tar.gz"
                download_url = fallback

            self.download_thread = DownloadAndInstallThread(download_url, target_dir, add_to_path)
            self.download_thread.progress.connect(self.on_progress)
            self.download_thread.log.connect(self.on_log)
            self.download_thread.finished_success.connect(self.on_finished_success)
            self.download_thread.finished_error.connect(self.on_finished_error)

            self.btn_back.setEnabled(False)
            self.btn_next.setEnabled(False)
            self.btn_cancel.setEnabled(True)
            self.download_thread.start()
            self.current_index += 1
        self.update_buttons()

    def closeEvent(self, event):
        # During installation (progress page) we block closing unless user confirms
        installing_index = 4
        if self.current_index == installing_index:  # During installation
            reply = QMessageBox.question(
                self, "Confirmación", "¿Estás seguro que deseas cancelar la instalación?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def on_versions_fetched(self, versions):
        self.version_combo.clear()
        if not versions:
            self.version_combo.addItem("No se encontraron versiones automáticamente")
            return
        for v in versions:
            self.version_combo.addItem(v)

    def on_fetch_error(self, err):
        self.version_combo.clear()
        self.version_combo.addItem("Error al obtener versiones (usa entrada manual)")
        QMessageBox.warning(self, "Error al obtener versiones", err)

    def populate_build_info(self, version):
        # intenta listar builds disponibles en windows.php.net para esa versión
        try:
            r = requests.get(WINDOWS_RELEASES_BASE, timeout=12)
            if r.ok:
                text = r.text
                matches = re.findall(rf"(php-[\d\.]+[^\s\"']*{re.escape(version)}[^\s\"']*\.(?:zip|msi|tar\.gz))", text, flags=re.IGNORECASE)
                # matches puede estar vacío; mejor buscar por filenames que contengan la versión
                filenames = [m for m in re.findall(r'([^\n\r<>"]+\.(?:zip|msi|tar\.gz))', text) if version in m]
                filenames = filenames[:50]
                info = ""
                if filenames:
                    info += "Builds encontrados en windows.php.net:\n\n"
                    for f in filenames:
                        info += f"- {f}\n"
                    info += "\nEl instalador intentará descargar uno de estos builds si coinciden con la arquitectura seleccionada."
                else:
                    info = "No se encontraron builds precompilados para Windows en el índice. Se usará el tarball fuente si está disponible en php.net."
                self.build_text.setPlainText(info)
            else:
                self.build_text.setPlainText("No se pudo consultar windows.php.net (red). Se usará tarball fuente como fallback.")
        except Exception as e:
            self.build_text.setPlainText("Error al consultar builds: " + str(e))

    def find_selected_build_url(self):
        # Formar candidate filenames a partir de selección
        version = self.selected_version
        want_x64 = self.cb_x64.isChecked()
        want_x86 = self.cb_x86.isChecked()
        want_ts = self.cb_ts.isChecked()
        want_nts = self.cb_nts.isChecked()

        # si ninguna arquitectura seleccionada, seleccionar x64 por defecto
        if not (want_x64 or want_x86):
            want_x64 = True

        # buscar en el índice de windows.php.net
        r = requests.get(WINDOWS_RELEASES_BASE, timeout=12)
        if not r.ok:
            return None
        text = r.text
        # construir orden de preferencia de sufijos típicos en windows builds:
        # ejemplos: php-8.4.13-Win32-vs17-x64.zip
        candidates = []
        archs = []
        if want_x64:
            archs.append("x64")
        if want_x86:
            archs.append("x86")
        ts_list = []
        if want_ts:
            ts_list.append("")  # puede no aparecer explícito
            ts_list.append("-ts")
        if want_nts:
            ts_list.append("-nts")

        # también buscar variantes con vs17, vs16, vc15, etc.
        toolsets = ["-vs17-", "-vs16-", "-vc15-", "-VC15-", "-vs18-"]
        for arch in archs:
            for ts in ts_list:
                for tool in toolsets:
                    # intentar varias construcciones de nombre
                    candidate = f"php-{version}{ts}{tool}{arch}.zip"
                    candidates.append(candidate)
                    # some names use Win32 vs Win64 or Win32 in name:
                    candidate2 = f"php-{version}{ts}-Win32{tool}{arch}.zip"
                    candidates.append(candidate2)
        # también examinar archives listing for exact filename matches
        for cand in candidates:
            if cand in text:
                # construir URL
                url = urljoin(WINDOWS_RELEASES_BASE, cand)
                return url
        # si no encontró, intentar buscar cualquier archivo en listado que contenga la versión
        matches = re.findall(r'([^\s"<>]+'+re.escape(version)+r'[^\s"<>]*\.(?:zip|msi|tar\.gz))', text, flags=re.IGNORECASE)
        if matches:
            # preferir zip
            for m in matches:
                if m.lower().endswith(".zip"):
                    return urljoin(WINDOWS_RELEASES_BASE, m)
            return urljoin(WINDOWS_RELEASES_BASE, matches[0])
        return None

    def on_progress(self, pct):
        self.progress_bar.setValue(pct)

    def on_log(self, text):
        self.log_box.append(text)

    def create_uninstaller(self, installed_path):
        try:
            uninstall_script = os.path.join(installed_path, "uninstall.bat")
            with open(uninstall_script, "w") as f:
                f.write("@echo off\n")
                f.write(f"rmdir /S /Q \"{installed_path}\"\n")
                f.write("reg delete \"HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\PHPInstaller\" /f\n")
                f.write("echo PHP uninstalled successfully.\n")
                f.write("pause\n")
            print("Uninstaller created successfully.")
        except Exception as e:
            print(f"Failed to create uninstaller: {e}")

    def register_installation(self, installed_path):
        try:
            uninstall_key = r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\PHPInstaller"
            with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, uninstall_key) as key:
                winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "PHP Installer")
                winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f"{installed_path}\\uninstall.bat")
                winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, installed_path)
                winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "PHP Installer Team")
                winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, "1.0.0")
                winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, 1024)
            print("Installation registered successfully.")
        except Exception as e:
            print(f"Failed to register installation: {e}")

    def on_finished_success(self, installed_path):
        self.log_box.append("Instalación finalizada: " + installed_path)
        self.finish_label.setText(f"Instalación completada en: {installed_path}")
        QMessageBox.information(self, "Éxito", "PHP instalado correctamente.")

        # Register installation and create uninstaller
        self.register_installation(installed_path)
        self.create_uninstaller(installed_path)

        self.current_index = self.stack.count()-1
        self.update_buttons()

    def on_finished_error(self, err):
        self.log_box.append("ERROR: " + err)
        QMessageBox.critical(self, "Error", "Error durante la instalación: " + err)
        # permitir reintentar
        self.btn_next.setEnabled(True)
        self.btn_back.setEnabled(True)


def main():
    app = QApplication(sys.argv)
    win = PHPInstaller()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
