import sys
import os
import shutil
import numpy as np
from PIL import Image
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QFileDialog, QProgressBar, QTextEdit, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

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
        self.resize(800, 650)
        self.folder_path = ""
        self.model_path = ""
        self.output_path = ""
        self.worker = None

        self.init_ui()
        self.apply_style()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(30, 30, 30, 30)

        selection_frame = QFrame()
        selection_layout = QVBoxLayout(selection_frame)
        
        # Modelo
        model_row = QHBoxLayout()
        self.lbl_model = QLabel("Modelo: Nenhum arquivo selecionado")
        btn_model = QPushButton("Selecionar Modelo")
        btn_model.clicked.connect(self.select_model)
        model_row.addWidget(self.lbl_model, 1)
        model_row.addWidget(btn_model)
        selection_layout.addLayout(model_row)

        # Entrada
        input_row = QHBoxLayout()
        self.lbl_folder = QLabel("Origem: Nenhuma pasta selecionada")
        btn_folder = QPushButton("Pasta de Origem")
        btn_folder.clicked.connect(self.select_folder)
        input_row.addWidget(self.lbl_folder, 1)
        input_row.addWidget(btn_folder)
        selection_layout.addLayout(input_row)

        # Saida
        output_row = QHBoxLayout()
        self.lbl_output = QLabel("Destino: Nenhuma pasta selecionada")
        btn_output = QPushButton("Pasta de Destino")
        btn_output.clicked.connect(self.select_output)
        output_row.addWidget(self.lbl_output, 1)
        output_row.addWidget(btn_output)
        selection_layout.addLayout(output_row)

        main_layout.addWidget(selection_frame)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        main_layout.addWidget(self.progress_bar)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("Logs de processamento...")
        main_layout.addWidget(self.log_output)

        # Botoes de Controle
        control_layout = QHBoxLayout()
        
        self.btn_start = QPushButton("INICIAR")
        self.btn_start.setObjectName("btn_start")
        self.btn_start.setFixedHeight(45)
        self.btn_start.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.btn_start.clicked.connect(self.start_classification)
        
        self.btn_stop = QPushButton("PARAR")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setFixedHeight(45)
        self.btn_stop.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_classification)
        
        control_layout.addWidget(self.btn_start, 2)
        control_layout.addWidget(self.btn_stop, 1)
        main_layout.addLayout(control_layout)

    def apply_style(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #0F0F0F; }
            QWidget { color: #FFFFFF; font-family: 'Segoe UI'; }
            QFrame { background-color: #1A1A1A; border-radius: 6px; padding: 10px; }
            QLabel { font-size: 12px; color: #BBBBBB; }
            QPushButton { 
                background-color: #2D2D2D; 
                border: 1px solid #3D3D3D; 
                padding: 8px; 
                border-radius: 4px; 
                min-width: 120px;
            }
            QPushButton:hover { background-color: #3D3D3D; border-color: #019DEA; }
            QPushButton#btn_start { background-color: #019DEA; border: none; }
            QPushButton#btn_start:hover { background-color: #0186C4; }
            QPushButton#btn_stop { background-color: #C40101; border: none; }
            QPushButton#btn_stop:hover { background-color: #A30101; }
            QPushButton:disabled { background-color: #222222; color: #444444; }
            QProgressBar { background-color: #1A1A1A; border-radius: 5px; }
            QProgressBar::chunk { background-color: #019DEA; border-radius: 5px; }
            QTextEdit { 
                background-color: #1A1A1A; 
                color: #A0A0A0; 
                border: 1px solid #2D2D2D; 
                border-radius: 6px; 
                font-family: 'Consolas'; 
                font-size: 11px; 
            }
        """)

    def select_model(self):
        file, _ = QFileDialog.getOpenFileName(self, "Selecionar Modelo", "", "Keras Model (*.keras *.h5)")
        if file:
            self.model_path = file
            self.lbl_model.setText(f"Modelo: {os.path.basename(file)}")

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Origem")
        if folder:
            self.folder_path = folder
            self.lbl_folder.setText(f"Origem: {os.path.basename(folder)}")

    def select_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Destino")
        if folder:
            self.output_path = folder
            self.lbl_output.setText(f"Destino: {os.path.basename(folder)}")

    def start_classification(self):
        if not all([self.model_path, self.folder_path, self.output_path]):
            self.log_output.append("Erro: Selecione modelo, pasta de origem e pasta de destino.")
            return

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)
        self.log_output.clear()
        self.log_output.append("Iniciando processamento...")

        self.worker = ClassifierWorker(self.folder_path, self.model_path, self.output_path)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.status.connect(lambda s: self.log_output.append(s))
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def stop_classification(self):
        if self.worker:
            self.worker.stop()
            self.btn_stop.setEnabled(False)

    def on_finished(self):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
