import sys
import threading
import time
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QListWidget,
    QListWidgetItem, QDialog, QVBoxLayout, QHBoxLayout, QWidget, QRadioButton,
    QButtonGroup, QLineEdit, QMessageBox, QSpinBox, QDoubleSpinBox, QGroupBox, QCheckBox
)
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor
from PyQt5.QtCore import Qt, QRect, QTimer, QPoint

import pygetwindow as gw
import pyautogui
from PIL import Image
import numpy as np

class SelectWindowDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Selecionar Tela")
        self.selected_window = None
        layout = QVBoxLayout()
        self.listWidget = QListWidget()
        self.populate_window_list()
        layout.addWidget(self.listWidget)
        button_layout = QHBoxLayout()
        select_button = QPushButton("Selecionar")
        select_button.clicked.connect(self.select_window)
        cancel_button = QPushButton("Cancelar")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(select_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def populate_window_list(self):
        windows = gw.getAllTitles()
        for title in windows:
            if title.strip():
                item = QListWidgetItem(title)
                self.listWidget.addItem(item)

    def select_window(self):
        selected_items = self.listWidget.selectedItems()
        if selected_items:
            self.selected_window = selected_items[0].text()
            self.accept()

class ImageLabel(QLabel):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setMouseTracking(True)
        self.drawing = False
        self.start_point = None
        self.end_point = None
        self.rect = QRect()
        self.rectangles = []
        self.position = None
        self.selecting_position = False
        self.selected_color = None
        self.selecting_color = False

    def mousePressEvent(self, event):
        if not self.main_window.window_selected:
            return
        if event.button() == Qt.LeftButton:
            if self.selecting_position or self.selecting_color:
                x = event.pos().x()
                y = event.pos().y()
                pixmap = self.pixmap()
                if pixmap:
                    image = pixmap.toImage()
                    color = QColor(image.pixel(x, y))
                    if self.selecting_color:
                        self.selected_color = (color.red(), color.green(), color.blue())
                        self.main_window.task_editor.update_color_preview(self.selected_color)
                        self.selecting_color = False
                    if self.selecting_position:
                        self.position = event.pos()
                        self.main_window.task_editor.update_position_preview(self.position)
                        self.selecting_position = False
                    self.update()
            else:
                self.drawing = True
                self.start_point = event.pos()
                self.rect = QRect()

    def mouseMoveEvent(self, event):
        if self.drawing:
            self.end_point = event.pos()
            self.rect = QRect(self.start_point, self.end_point)
            self.update()

    def mouseReleaseEvent(self, event):
        if self.drawing:
            self.drawing = False
            self.end_point = event.pos()
            self.rect = QRect(self.start_point, self.end_point)
            self.rectangles = [self.rect.normalized()]
            self.update()
            self.main_window.finish_selection_button.setEnabled(True)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        if self.rectangles:
            pen = QPen(Qt.red, 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(self.rectangles[-1])
        if self.position:
            pen = QPen(Qt.blue, 5, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawPoint(self.position)

class TaskItem(QWidget):
    def __init__(self, task, main_window):
        super().__init__()
        self.task = task
        self.main_window = main_window
        layout = QHBoxLayout()
        self.checkbox = QCheckBox()
        self.checkbox.stateChanged.connect(self.toggle_task)
        self.label = QLabel(task.name)
        self.edit_button = QPushButton("Editar")
        self.edit_button.clicked.connect(self.edit_task)
        layout.addWidget(self.checkbox)
        layout.addWidget(self.label)
        layout.addWidget(self.edit_button)
        self.setLayout(layout)

    def toggle_task(self, state):
        if state == Qt.Checked:
            print(f"Habilitando task: {self.label.text()}")
            self.task.start()
        else:
            print(f"Desabilitando task: {self.label.text()}")
            self.task.stop()

    def edit_task(self):
        self.main_window.task_editor.edit_task(self.task)

class Task:
    def __init__(self, name, condition_type, condition_value, position, action_type, frequency=None, duration=None, main_window=None):
        self.name = name
        self.condition_type = condition_type  # 'time' or 'color'
        self.condition_value = condition_value  # Interval in seconds or color tuple
        self.position = position  # (x, y)
        self.action_type = action_type  # 'click' or 'clicks'
        self.frequency = frequency  # For 'clicks' action
        self.duration = duration  # For 'clicks' action
        self.running = False
        self.thread = None
        self.main_window = main_window  # Referência ao MainWindow

    def start(self):
        if not self.running:
            self.running = True
            if self.condition_type == 'time':
                self.thread = threading.Thread(target=self.run_time_condition)
            elif self.condition_type == 'color':
                self.thread = threading.Thread(target=self.run_color_condition)
            self.thread.start()
            print(f"Task iniciada: {self}")
        else:
            print("Task já está em execução.")

    def stop(self):
        if self.running:
            self.running = False
            if self.thread is not None:
                self.thread.join()
            print(f"Task parada: {self}")
        else:
            print("Task já está parada.")

    def run_time_condition(self):
        while self.running:
            time.sleep(self.condition_value)
            self.perform_action()

    def run_color_condition(self):
        while self.running:
            screenshot = pyautogui.screenshot()
            pix = screenshot.getpixel(self.position)
            print(f"Cor detectada: {pix[:3]}, Cor escolhida: {self.condition_value}")  # Debug de cor
            if pix[:3] == self.condition_value:
                self.perform_action()
            time.sleep(0.1)  # Evita uso excessivo de CPU

    def perform_action(self):
        print(f"Executando ação: {self.action_type} na posição {self.position}")
        if self.main_window and self.main_window.selected_window:
            self.main_window.selected_window.activate()
            original_position = pyautogui.position()  # Armazena a posição atual do mouse
            if self.action_type == 'click':
                pyautogui.click(self.position)
            elif self.action_type == 'clicks':
                end_time = time.time() + self.duration
                interval = 1 / self.frequency
                while time.time() < end_time and self.running:
                    pyautogui.click(self.position)
                    time.sleep(interval)
            pyautogui.moveTo(original_position)  # Retorna o mouse à posição original
        else:
            print("Janela não selecionada ou inválida.")

    def __str__(self):
        return f"Task(name={self.name}, condition_type={self.condition_type}, action_type={self.action_type})"

class TaskEditorWidget(QWidget):
    def __init__(self, main_window, image_label=None):
        super().__init__()
        self.main_window = main_window
        self.image_label = image_label
        self.task = None  # Armazena a task sendo editada (None se for uma nova task)
        self.selected_color = None
        self.selected_position = None
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignTop)

        # Nome da Task
        self.task_name_input = QLineEdit()
        self.task_name_input.setPlaceholderText("Nome da Task")

        # Condição
        condition_group = QGroupBox("Condição")
        condition_layout = QVBoxLayout()

        self.condition_time_radio = QRadioButton("Tempo")
        self.condition_color_radio = QRadioButton("Cor")
        self.condition_time_radio.setChecked(True)
        self.condition_group = QButtonGroup()
        self.condition_group.addButton(self.condition_time_radio)
        self.condition_group.addButton(self.condition_color_radio)

        self.time_interval_spin = QDoubleSpinBox()
        self.time_interval_spin.setMinimum(0.1)
        self.time_interval_spin.setValue(1.0)
        self.time_interval_spin.setSuffix(" s")

        self.select_color_button = QPushButton("Selecionar Cor")
        self.select_color_button.setEnabled(False)
        self.select_color_button.clicked.connect(self.select_color)

        self.color_preview = QLabel()
        self.color_preview.setFixedSize(50, 50)
        self.color_preview.setStyleSheet("border: 1px solid black;")

        condition_layout.addWidget(self.condition_time_radio)
        condition_layout.addWidget(self.time_interval_spin)
        condition_layout.addWidget(self.condition_color_radio)
        condition_layout.addWidget(self.select_color_button)
        condition_layout.addWidget(self.color_preview)
        condition_group.setLayout(condition_layout)

        self.condition_time_radio.toggled.connect(self.update_condition_inputs)

        # Posição
        position_group = QGroupBox("Posição")
        position_layout = QVBoxLayout()
        self.select_position_button = QPushButton("Selecionar Posição")
        self.select_position_button.clicked.connect(self.select_position)

        self.position_preview = QLabel()
        self.position_preview.setFixedSize(50, 50)
        self.position_preview.setStyleSheet("border: 1px solid black;")

        position_layout.addWidget(self.select_position_button)
        position_layout.addWidget(self.position_preview)
        position_group.setLayout(position_layout)

        # Ação
        action_group = QGroupBox("Ação")
        action_layout = QVBoxLayout()

        self.action_click_radio = QRadioButton("Apenas um clique")
        self.action_clicks_radio = QRadioButton("Cliques em frequência X por Y segundos")
        self.action_click_radio.setChecked(True)
        self.action_group = QButtonGroup()
        self.action_group.addButton(self.action_click_radio)
        self.action_group.addButton(self.action_clicks_radio)

        self.frequency_spin = QSpinBox()
        self.frequency_spin.setMinimum(1)
        self.frequency_spin.setValue(1)
        self.frequency_spin.setSuffix(" cliques/s")
        self.frequency_spin.setEnabled(False)

        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setMinimum(0.1)
        self.duration_spin.setValue(1.0)
        self.duration_spin.setSuffix(" s")
        self.duration_spin.setEnabled(False)

        action_layout.addWidget(self.action_click_radio)
        action_layout.addWidget(self.action_clicks_radio)
        action_layout.addWidget(QLabel("Frequência:"))
        action_layout.addWidget(self.frequency_spin)
        action_layout.addWidget(QLabel("Duração:"))
        action_layout.addWidget(self.duration_spin)
        action_group.setLayout(action_layout)

        self.action_clicks_radio.toggled.connect(self.update_action_inputs)

        # Botões
        button_layout = QHBoxLayout()
        save_button = QPushButton("Salvar")
        save_button.clicked.connect(self.save_task)
        cancel_button = QPushButton("Cancelar")
        cancel_button.clicked.connect(self.cancel_task)
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)

        layout.addWidget(self.task_name_input)
        layout.addWidget(condition_group)
        layout.addWidget(position_group)
        layout.addWidget(action_group)
        layout.addLayout(button_layout)
        self.setLayout(layout)

        self.setVisible(False)  # Inicialmente oculto

    def update_condition_inputs(self):
        if self.condition_time_radio.isChecked():
            self.time_interval_spin.setEnabled(True)
            self.select_color_button.setEnabled(False)
        else:
            self.time_interval_spin.setEnabled(False)
            self.select_color_button.setEnabled(True)

    def update_action_inputs(self):
        if self.action_clicks_radio.isChecked():
            self.frequency_spin.setEnabled(True)
            self.duration_spin.setEnabled(True)
        else:
            self.frequency_spin.setEnabled(False)
            self.duration_spin.setEnabled(False)

    def select_position(self):
        if not self.main_window.window_selected:
            self.main_window.status_label.setText("Selecione uma janela primeiro.")
            return
        self.image_label.selecting_position = True
        self.main_window.status_label.setText("Clique na imagem para selecionar a posição.")

    def select_color(self):
        if not self.main_window.window_selected:
            self.main_window.status_label.setText("Selecione uma janela primeiro.")
            return
        self.image_label.selecting_color = True
        self.main_window.status_label.setText("Clique na imagem para selecionar a cor.")

    def update_color_preview(self, color):
        self.selected_color = color
        r, g, b = color
        self.color_preview.setStyleSheet(f"background-color: rgb({r}, {g}, {b}); border: 1px solid black;")
        self.main_window.status_label.setText("Cor selecionada.")

    def update_position_preview(self, position):
        self.selected_position = position
        x = position.x()
        y = position.y()
        pixmap = self.image_label.pixmap()
        if pixmap:
            cropped = pixmap.copy(x - 10, y - 10, 20, 20)
            scaled = cropped.scaled(50, 50)
            self.position_preview.setPixmap(scaled)
        self.main_window.status_label.setText("Posição selecionada.")

    def edit_task(self, task):
        # Carrega as informações da task a ser editada
        self.task = task
        self.task_name_input.setText(task.name)
        self.condition_time_radio.setChecked(task.condition_type == 'time')
        self.condition_color_radio.setChecked(task.condition_type == 'color')
        if task.condition_type == 'time':
            self.time_interval_spin.setValue(task.condition_value)
        else:
            self.update_color_preview(task.condition_value)
        self.selected_position = QPoint(task.position[0] - self.main_window.selected_window.left,
                                        task.position[1] - self.main_window.selected_window.top)
        self.update_position_preview(self.selected_position)
        self.action_click_radio.setChecked(task.action_type == 'click')
        self.action_clicks_radio.setChecked(task.action_type == 'clicks')
        if task.action_type == 'clicks':
            self.frequency_spin.setValue(task.frequency)
            self.duration_spin.setValue(task.duration)
        self.setVisible(True)

    def save_task(self):
        # Salva a task (ou cria uma nova)
        name = self.task_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Erro", "Nome da Task não pode estar vazio.")
            return

        condition_type = 'time' if self.condition_time_radio.isChecked() else 'color'
        condition_value = self.time_interval_spin.value() if condition_type == 'time' else self.selected_color
        position = (self.selected_position.x() + self.main_window.selected_window.left,
                    self.selected_position.y() + self.main_window.selected_window.top)

        action_type = 'click' if self.action_click_radio.isChecked() else 'clicks'
        frequency = self.frequency_spin.value() if action_type == 'clicks' else None
        duration = self.duration_spin.value() if action_type == 'clicks' else None

        if self.task:
            # Se estamos editando uma task existente, atualizamos os valores
            self.task.name = name
            self.task.condition_type = condition_type
            self.task.condition_value = condition_value
            self.task.position = position
            self.task.action_type = action_type
            self.task.frequency = frequency
            self.task.duration = duration
            self.main_window.status_label.setText("Task editada.")
        else:
            # Se estamos criando uma nova task, instanciamos e adicionamos à lista
            new_task = Task(name, condition_type, condition_value, position, action_type, frequency, duration, self.main_window)
            self.main_window.tasks.append(new_task)
            task_item = TaskItem(new_task, self.main_window)
            list_item = QListWidgetItem()
            list_item.setSizeHint(task_item.sizeHint())
            self.main_window.task_list_widget.addItem(list_item)
            self.main_window.task_list_widget.setItemWidget(list_item, task_item)
            self.main_window.status_label.setText("Task criada e adicionada à lista.")

        self.setVisible(False)
        self.task = None  # Limpa a referência à task para a próxima criação

    def cancel_task(self):
        self.setVisible(False)
        self.task = None  # Limpa a referência à task ao cancelar
        self.main_window.status_label.setText("Edição de task cancelada.")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Automatizar Jogadas")
        self.selected_window = None
        self.window_selected = False
        self.selected_area = None
        self.image_label = ImageLabel(self)
        self.tasks = []
        self.updating = False
        self.initUI()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_screenshot)

    def initUI(self):
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: red;")

        self.select_window_button = QPushButton("Selecionar Tela")
        self.select_window_button.clicked.connect(self.select_window)

        self.select_area_button = QPushButton("Selecionar Área")
        self.select_area_button.clicked.connect(self.select_area)
        self.select_area_button.setEnabled(False)

        self.finish_selection_button = QPushButton("Concluir Seleção")
        self.finish_selection_button.clicked.connect(self.finish_selection)
        self.finish_selection_button.setEnabled(False)

        self.create_task_button = QPushButton("Criar Task")
        self.create_task_button.clicked.connect(self.show_task_editor)
        self.create_task_button.setEnabled(False)

        self.update_sample_button = QPushButton("Atualizar Amostra")
        self.update_sample_button.clicked.connect(self.update_screenshot)
        self.update_sample_button.setEnabled(False)

        self.live_update_button = QPushButton("Iniciar Atualização Constante")
        self.live_update_button.clicked.connect(self.toggle_live_update)
        self.live_update_button.setEnabled(False)

        # Task Editor integrado
        self.task_editor = TaskEditorWidget(self, self.image_label)

        # Lista de Tasks
        self.task_list_widget = QListWidget()

        # Layouts
        main_layout = QHBoxLayout()
        left_layout = QVBoxLayout()
        left_layout.setAlignment(Qt.AlignTop)
        right_layout = QVBoxLayout()
        right_layout.setAlignment(Qt.AlignTop)

        # Adiciona os botões ao layout esquerdo
        left_layout.addWidget(self.select_window_button)
        left_layout.addWidget(self.select_area_button)
        left_layout.addWidget(self.finish_selection_button)
        left_layout.addWidget(self.create_task_button)
        left_layout.addWidget(self.update_sample_button)
        left_layout.addWidget(self.live_update_button)
        left_layout.addWidget(QLabel("Tasks:"))
        left_layout.addWidget(self.task_list_widget)
        left_layout.addWidget(self.status_label)
        left_layout.addWidget(self.task_editor)
        left_layout.addStretch()

        # Adiciona a imagem ao layout direito
        right_layout.addWidget(self.image_label)

        # Combina os layouts
        main_layout.addLayout(left_layout)
        main_layout.addLayout(right_layout)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # Desabilitar interações até que a janela seja selecionada
        self.image_label.setEnabled(False)

    def select_window(self):
        dialog = SelectWindowDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.selected_window_title = dialog.selected_window
            window = gw.getWindowsWithTitle(self.selected_window_title)
            if window:
                self.selected_window = window[0]
                self.window_selected = True
                self.selected_window.activate()
                self.update_screenshot()
                self.select_area_button.setEnabled(True)
                self.update_sample_button.setEnabled(True)
                self.live_update_button.setEnabled(True)
                self.status_label.setText(f"Janela selecionada: {self.selected_window_title}")
                self.image_label.setEnabled(True)
            else:
                self.status_label.setText("Erro ao selecionar a janela.")

    def update_screenshot(self):
        if self.selected_window:
            window = self.selected_window
            left, top, width, height = window.left, window.top, window.width, window.height
            screenshot = pyautogui.screenshot(region=(left, top, width, height))
            screenshot.save("window_screenshot.png")
            pixmap = QPixmap("window_screenshot.png")
            self.image_label.setPixmap(pixmap)
            self.image_label.setFixedSize(pixmap.size())

    def toggle_live_update(self):
        if not self.updating:
            self.timer.start(66)  # Aproximadamente 15 FPS
            self.updating = True
            self.live_update_button.setText("Parar Atualização Constante")
        else:
            self.timer.stop()
            self.updating = False
            self.live_update_button.setText("Iniciar Atualização Constante")

    def select_area(self):
        self.image_label.rectangles = []
        self.image_label.rect = QRect()
        self.image_label.update()
        self.finish_selection_button.setEnabled(True)
        self.status_label.setText("Desenhe uma área na imagem.")

    def finish_selection(self):
        if self.image_label.rectangles:
            selected_rect = self.image_label.rectangles[-1]
            x = selected_rect.left()
            y = selected_rect.top()
            width = selected_rect.width()
            height = selected_rect.height()
            window_x = x + self.selected_window.left
            window_y = y + self.selected_window.top
            window_width = width
            window_height = height
            self.selected_area = (window_x, window_y, window_width, window_height)
            self.create_task_button.setEnabled(True)
            self.status_label.setText("Área selecionada.")
        else:
            self.status_label.setText("Nenhuma área foi selecionada.")
        self.finish_selection_button.setEnabled(False)

    def show_task_editor(self):
        if not self.window_selected:
            self.status_label.setText("Selecione uma janela primeiro.")
            return
        self.task_editor.setVisible(True)
        self.status_label.setText("Configure a task e clique em 'Salvar'.")

    def closeEvent(self, event):
        for task in self.tasks:
            task.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWin = MainWindow()
    mainWin.show()
    sys.exit(app.exec_())
