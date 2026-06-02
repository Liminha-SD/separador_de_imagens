import sys
import os
import shutil
import numpy as np
from PIL import Image
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QProgressBar, QTextEdit,
    QGroupBox, QFrame, QStatusBar
)
from PySide6.QtCore import Qt, QThread, Signal

from dark_theme import apply_theme, set_default_font, COLORS


class ClassifierWorker(QThread):
    progress = Signal(int)
    status = Signal(str)
    finished = Signal()

    def __init__(self, folder_path, model_path, output_path):
        super().__init__()
        self.folder_path = folder_path
        self.model_path = model_path
        self.output_path = output_path
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            import tensorflow as tf
            self.status.emit("Carregando o modelo do TensorFlow...")
            model = tf.keras.models.load_model(self.model_path)

            input_shape = model.input_shape[1:3]
            if None in input_shape:
                input_shape = (224, 224)

            img_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.webp')
            files = [f for f in os.listdir(self.folder_path) if f.lower().endswith(img_extensions)]

            if not files:
                self.status.emit("Nenhuma imagem encontrada na pasta de origem.")
                return

            # Criar apenas a pasta 'boas' no destino
            good_dir = os.path.join(self.output_path, "boas")
            os.makedirs(good_dir, exist_ok=True)

            total = len(files)
            for i, filename in enumerate(files):
                if not self._is_running:
                    self.status.emit("\nProcesso interrompido pelo usuario.")
                    break

                img_path = os.path.join(self.folder_path, filename)

                try:
                    img = Image.open(img_path).convert('RGB')
                    img = img.resize((input_shape[1], input_shape[0]))
                    img_array = np.array(img) / 255.0
                    img_array = np.expand_dims(img_array, axis=0)

                    prediction = model.predict(img_array, verbose=0)
                    is_good = prediction[0][0] > 0.5

                    if is_good:
                        shutil.copy2(img_path, os.path.join(good_dir, filename))
                        self.status.emit(f"[COPIADA] {filename} -> BOA")
                    else:
                        self.status.emit(f"[IGNORADA] {filename} -> RUIM")

                    self.progress.emit(int(((i + 1) / total) * 100))
                except Exception as img_err:
                    self.status.emit(f"[ERRO] Falha ao processar {filename}: {str(img_err)}")

            if self._is_running:
                self.status.emit("\nProcessamento concluido com sucesso!")
        except Exception as e:
            self.status.emit(f"\nERRO CRITICO: {str(e)}")
        finally:
            self.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Image Sorter")
        self.resize(820, 700)
        self.folder_path = ""
        self.model_path = ""
        self.output_path = ""
        self.worker = None

        self.init_ui()
        apply_theme(self)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(30, 24, 30, 24)

        # --- Cabecalho ---
        header = QVBoxLayout()
        header.setSpacing(2)
        title = QLabel("AI Image Sorter")
        title.setObjectName("title")
        subtitle = QLabel(
            "Selecione um modelo treinado e as pastas de origem e destino. "
            "As imagens classificadas como boas serao copiadas para a subpasta \"boas\"."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        header.addWidget(title)
        header.addWidget(subtitle)
        main_layout.addLayout(header)

        separator = QFrame()
        separator.setObjectName("separator")
        separator.setFrameShape(QFrame.HLine)
        main_layout.addWidget(separator)

        # --- Configuracao (passos numerados) ---
        config_group = QGroupBox("Configuracao")
        config_layout = QVBoxLayout(config_group)
        config_layout.setSpacing(12)
        config_layout.setContentsMargins(16, 18, 16, 16)

        self.lbl_model = QLabel("Nenhum arquivo selecionado")
        self.lbl_folder = QLabel("Nenhuma pasta selecionada")
        self.lbl_output = QLabel("Nenhuma pasta selecionada")

        config_layout.addLayout(self._build_step_row(
            "1", "Modelo (.keras / .h5)", self.lbl_model,
            "Selecionar", self.select_model,
            "Arquivo do modelo treinado que decide se a imagem e boa ou ruim."
        ))
        config_layout.addLayout(self._build_step_row(
            "2", "Pasta de origem", self.lbl_folder,
            "Escolher pasta", self.select_folder,
            "Pasta que contem as imagens a serem classificadas."
        ))
        config_layout.addLayout(self._build_step_row(
            "3", "Pasta de destino", self.lbl_output,
            "Escolher pasta", self.select_output,
            "Onde a subpasta \"boas\" sera criada com as imagens aprovadas."
        ))

        main_layout.addWidget(config_group)

        # --- Progresso ---
        progress_group = QGroupBox("Progresso")
        progress_layout = QVBoxLayout(progress_group)
        progress_layout.setContentsMargins(16, 18, 16, 16)
        progress_layout.setSpacing(10)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        progress_layout.addWidget(self.progress_bar)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("Os logs de processamento aparecerao aqui...")
        progress_layout.addWidget(self.log_output)

        main_layout.addWidget(progress_group, 1)

        # --- Botoes de Controle ---
        control_layout = QHBoxLayout()
        control_layout.setSpacing(12)

        self.btn_start = QPushButton("Iniciar classificacao")
        self.btn_start.setFixedHeight(46)
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setToolTip("Comeca a classificar as imagens da pasta de origem.")
        self.btn_start.clicked.connect(self.start_classification)

        self.btn_stop = QPushButton("Parar")
        self.btn_stop.setObjectName("danger")
        self.btn_stop.setFixedHeight(46)
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.setToolTip("Interrompe o processamento em andamento.")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_classification)

        control_layout.addWidget(self.btn_start, 2)
        control_layout.addWidget(self.btn_stop, 1)
        main_layout.addLayout(control_layout)

        # --- Barra de status ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Pronto. Complete os 3 passos para iniciar.")

    def _build_step_row(self, number, label_text, value_label, button_text, on_click, tooltip):
        """Monta uma linha de passo: [n] Titulo / valor selecionado / botao."""
        row = QHBoxLayout()
        row.setSpacing(12)

        badge = QLabel(number)
        badge.setObjectName("stepBadge")
        badge.setFixedSize(26, 26)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background-color: {COLORS['accent']}; color: white; "
            f"border-radius: 13px; font-weight: bold;"
        )

        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        caption = QLabel(label_text)
        caption.setStyleSheet("font-weight: bold; background: transparent;")
        value_label.setObjectName("subtitle")
        value_label.setToolTip(tooltip)
        text_col.addWidget(caption)
        text_col.addWidget(value_label)

        button = QPushButton(button_text)
        button.setObjectName("secondary")
        button.setCursor(Qt.PointingHandCursor)
        button.setMinimumWidth(130)
        button.setToolTip(tooltip)
        button.clicked.connect(on_click)

        row.addWidget(badge)
        row.addLayout(text_col, 1)
        row.addWidget(button)
        return row

    def _mark_selected(self, label, text):
        """Marca o valor como selecionado destacando-o com a cor de destaque."""
        label.setText(text)
        label.setStyleSheet(f"color: {COLORS['accent']}; background: transparent;")

    def select_model(self):
        file, _ = QFileDialog.getOpenFileName(self, "Selecionar Modelo", "", "Keras Model (*.keras *.h5)")
        if file:
            self.model_path = file
            self._mark_selected(self.lbl_model, os.path.basename(file))
            self._update_ready_status()

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Origem")
        if folder:
            self.folder_path = folder
            self._mark_selected(self.lbl_folder, folder)
            self._update_ready_status()

    def select_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Destino")
        if folder:
            self.output_path = folder
            self._mark_selected(self.lbl_output, folder)
            self._update_ready_status()

    def _update_ready_status(self):
        missing = []
        if not self.model_path:
            missing.append("modelo")
        if not self.folder_path:
            missing.append("origem")
        if not self.output_path:
            missing.append("destino")
        if missing:
            self.status_bar.showMessage("Falta selecionar: " + ", ".join(missing) + ".")
        else:
            self.status_bar.showMessage("Tudo pronto. Clique em \"Iniciar classificacao\".")

    def start_classification(self):
        if not all([self.model_path, self.folder_path, self.output_path]):
            self.log_output.append("Erro: Selecione modelo, pasta de origem e pasta de destino.")
            self._update_ready_status()
            return

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)
        self.log_output.clear()
        self.log_output.append("Iniciando processamento...")
        self.status_bar.showMessage("Processando...")

        self.worker = ClassifierWorker(self.folder_path, self.model_path, self.output_path)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.status.connect(lambda s: self.log_output.append(s))
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def stop_classification(self):
        if self.worker:
            self.worker.stop()
            self.btn_stop.setEnabled(False)
            self.status_bar.showMessage("Interrompendo...")

    def on_finished(self):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.status_bar.showMessage("Concluido.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    set_default_font(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
