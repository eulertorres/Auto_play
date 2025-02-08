import sys
import threading
import time
import os
import json
import random
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QListWidget,
    QListWidgetItem, QDialog, QVBoxLayout, QHBoxLayout, QWidget, QRadioButton,
    QButtonGroup, QLineEdit, QMessageBox, QSpinBox, QDoubleSpinBox, QGroupBox, QCheckBox, QFileDialog
)
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QIcon, QMouseEvent
from PyQt5.QtCore import Qt, QRect, QTimer, QPoint, pyqtSignal, QObject

import pygetwindow as gw
import pyautogui
from playsound import playsound

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
        self.selecting_sequence_positions = False
        self.sequence_positions = []
        self.color_position = None

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
                        self.color_position = event.pos()  # Armazena a posição
                        self.main_window.task_editor.update_color_preview(self.selected_color, self.color_position)
                        self.selecting_color = False
                    if self.selecting_position:
                        self.position = event.pos()
                        self.main_window.task_editor.update_position_preview(self.position)
                        self.selecting_position = False
                    self.update()
            elif self.selecting_sequence_positions:
                position = event.pos()
                self.sequence_positions.append(position)
                self.main_window.task_editor.update_sequence_preview()
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
        if self.sequence_positions:
            pen = QPen(Qt.green, 5, Qt.SolidLine)
            painter.setPen(pen)
            for idx, pos in enumerate(self.sequence_positions):
                painter.drawPoint(pos)
                painter.drawText(pos + QPoint(5, -5), str(idx + 1))

class TaskItem(QWidget):
    def __init__(self, task, main_window):
        super().__init__()
        self.task = task
        self.main_window = main_window
        self.list_item = None  # Referência ao QListWidgetItem
        layout = QHBoxLayout()
        self.checkbox = QCheckBox()
        self.checkbox.stateChanged.connect(self.toggle_task)
        self.label = QLabel(task.name)
        self.edit_button = QPushButton("Editar")
        self.edit_button.clicked.connect(self.edit_task)
        self.delete_button = QPushButton("Excluir")
        self.delete_button.clicked.connect(self.delete_task)
        layout.addWidget(self.checkbox)
        layout.addWidget(self.label)
        layout.addWidget(self.edit_button)
        layout.addWidget(self.delete_button)
        self.setLayout(layout)
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
        self.update_task_name()

    def delete_task(self):
        self.task.stop()
        self.main_window.tasks.remove(self.task)
        self.main_window.task_list_widget.takeItem(self.main_window.task_list_widget.row(self.list_item))
        self.main_window.status_label.setText(f"Task '{self.task.name}' excluída.")

    def update_task_name(self):
        self.label.setText(self.task.name)

class Task:
    def __init__(self, name, condition_type, condition_value, condition_position, action_type, action_position=None, frequency=None, duration=None, sequence=None, delay=None, main_window=None):
        self.name = name
        self.condition_type = condition_type
        self.condition_value = condition_value
        self.condition_position = condition_position  # Position to check the color
        self.action_type = action_type
        self.action_position = action_position  # Position to click (can be None)
        self.sequence = sequence
        self.delay = delay
        self.frequency = frequency
        self.duration = duration
        self.running = False
        self.thread = None
        self.main_window = main_window

    def start(self):
        if not self.running:
            self.running = True
            if self.condition_type == 'time':
                self.thread = threading.Thread(target=self.run_time_condition)
            elif self.condition_type == 'color':
                self.thread = threading.Thread(target=self.run_color_condition)
            self.thread.start()
            print(f"Task started: {self}")
        else:
            print("Task is already running.")

    def stop(self):
        if self.running:
            self.running = False
            if self.thread is not None:
                self.thread.join()
            print(f"Task stopped: {self}")
        else:
            print("Task is already stopped.")

    def run_time_condition(self):
        while self.running:
            time.sleep(self.condition_value)
            self.perform_action()

    def run_color_condition(self):
        while self.running:
            if self.condition_position is None:
                print("Posição de verificação da cor não definida.")
                break
            # Ajuste para considerar a área selecionada
            if self.main_window.selected_area:
                region = self.main_window.selected_area  # (x, y, width, height)
                screenshot = pyautogui.screenshot(region=region)
                x, y = self.condition_position
                adjusted_x = x - region[0]
                adjusted_y = y - region[1]
                pix = screenshot.getpixel((adjusted_x, adjusted_y))
            else:
                screenshot = pyautogui.screenshot()
                pix = screenshot.getpixel(self.condition_position)
            #print(f"cor atual {pix[:3]}. Cor condicao {self.condition_value}")
            if pix[:3] == self.condition_value:
                #print("Acionando ação por cor")
                self.perform_action()
            time.sleep(0.1)

    def perform_action(self):
        #print("entrei")
        if self.main_window and self.main_window.selected_window:
            #print("entreiiiiiiii")
            self.main_window.selected_window.activate()
            original_position = pyautogui.position()
            if self.action_type == 'click':
                #print(f"cliquei em {self.action_position}")
                pyautogui.click(self.action_position)
            elif self.action_type == 'clicks':
                end_time = time.time() + self.duration
                interval = 1 / self.frequency
                while time.time() < end_time and self.running:
                    pyautogui.click(self.action_position)
                    time.sleep(interval)
            elif self.action_type == 'sequence':
                for pos in self.sequence:
                    if not self.running:
                        break
                    pyautogui.click(pos)
                    time.sleep(self.delay)
            pyautogui.moveTo(original_position)
        else:
            print("Window not selected or invalid.")

    def __str__(self):
        return f"Task(name={self.name}, condition_type={self.condition_type}, action_type={self.action_type})"

class TaskEditorWidget(QWidget):
    def __init__(self, main_window, image_label=None):
        super().__init__()
        self.main_window = main_window
        self.image_label = image_label
        self.task = None
        self.selected_color = None
        self.selected_position = None
        self.color_position = None  # Position where the color was selected
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
        self.action_sequence_radio = QRadioButton("Sequência de Cliques")
        self.action_group = QButtonGroup()
        self.action_group.addButton(self.action_click_radio)
        self.action_group.addButton(self.action_clicks_radio)
        self.action_group.addButton(self.action_sequence_radio)

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

        # Widgets para a sequência
        self.select_sequence_button = QPushButton("Selecionar Sequência de Posições")
        self.select_sequence_button.setEnabled(False)
        self.select_sequence_button.clicked.connect(self.select_sequence_positions)

        self.finish_sequence_button = QPushButton("Concluir Seleção de Sequência")
        self.finish_sequence_button.setEnabled(False)
        self.finish_sequence_button.clicked.connect(self.finish_sequence_selection)

        self.sequence_positions_list = QListWidget()
        self.sequence_positions_list.setFixedHeight(100)
        self.sequence_delay_spin = QDoubleSpinBox()
        self.sequence_delay_spin.setMinimum(0.1)
        self.sequence_delay_spin.setValue(0.5)
        self.sequence_delay_spin.setSuffix(" s")
        self.sequence_delay_spin.setEnabled(False)

        action_layout.addWidget(self.action_click_radio)
        action_layout.addWidget(self.action_clicks_radio)
        action_layout.addWidget(QLabel("Frequência:"))
        action_layout.addWidget(self.frequency_spin)
        action_layout.addWidget(QLabel("Duração:"))
        action_layout.addWidget(self.duration_spin)
        action_layout.addWidget(self.action_sequence_radio)
        action_layout.addWidget(self.select_sequence_button)
        action_layout.addWidget(self.finish_sequence_button)
        action_layout.addWidget(QLabel("Posições da Sequência:"))
        action_layout.addWidget(self.sequence_positions_list)
        action_layout.addWidget(QLabel("Delay entre cliques:"))
        action_layout.addWidget(self.sequence_delay_spin)
        action_group.setLayout(action_layout)

        self.action_clicks_radio.toggled.connect(self.update_action_inputs)
        self.action_sequence_radio.toggled.connect(self.update_action_inputs)

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
            self.select_sequence_button.setEnabled(False)
            self.finish_sequence_button.setEnabled(False)
            self.sequence_positions_list.setEnabled(False)
            self.sequence_delay_spin.setEnabled(False)
            self.select_position_button.setEnabled(True)
        elif self.action_sequence_radio.isChecked():
            self.frequency_spin.setEnabled(False)
            self.duration_spin.setEnabled(False)
            self.select_sequence_button.setEnabled(True)
            self.finish_sequence_button.setEnabled(True)
            self.sequence_positions_list.setEnabled(True)
            self.sequence_delay_spin.setEnabled(True)
            self.select_position_button.setEnabled(False)
        else:
            self.frequency_spin.setEnabled(False)
            self.duration_spin.setEnabled(False)
            self.select_sequence_button.setEnabled(False)
            self.finish_sequence_button.setEnabled(False)
            self.sequence_positions_list.setEnabled(False)
            self.sequence_delay_spin.setEnabled(False)
            self.select_position_button.setEnabled(True)

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

    def select_sequence_positions(self):
        if not self.main_window.window_selected:
            self.main_window.status_label.setText("Selecione uma janela primeiro.")
            return
        self.image_label.selecting_sequence_positions = True
        self.image_label.sequence_positions = []
        self.sequence_positions_list.clear()
        self.main_window.status_label.setText("Clique na imagem para selecionar posições da sequência.")

    def finish_sequence_selection(self):
        self.image_label.selecting_sequence_positions = False
        self.update_sequence_preview()
        self.main_window.status_label.setText("Seleção de sequência concluída.")

    def update_sequence_preview(self):
        self.sequence_positions_list.clear()
        for idx, pos in enumerate(self.image_label.sequence_positions):
            item = QListWidgetItem(f"{idx + 1}: ({pos.x()}, {pos.y()})")
            self.sequence_positions_list.addItem(item)

    def update_color_preview(self, color, position):
        self.selected_color = color
        self.color_position = position
        r, g, b = color
        self.color_preview.setStyleSheet(f"background-color: rgb({r}, {g}, {b}); border: 1px solid black;")
        self.main_window.status_label.setText("Color selected.")

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
            if task.condition_value and task.condition_position:
                # Ajuste das posições considerando o deslocamento
                offset_x, offset_y = self.main_window.get_image_offset()
                self.update_color_preview(
                    task.condition_value,
                    QPoint(
                        task.condition_position[0] - self.main_window.selected_window.left - offset_x,
                        task.condition_position[1] - self.main_window.selected_window.top - offset_y
                    )
                )
        if task.action_type == 'sequence':
            self.action_sequence_radio.setChecked(True)
            self.sequence_delay_spin.setValue(task.delay)
            self.image_label.sequence_positions = []
            offset_x, offset_y = self.main_window.get_image_offset()
            for pos in task.sequence:
                adjusted_pos = QPoint(
                    pos[0] - self.main_window.selected_window.left - offset_x,
                    pos[1] - self.main_window.selected_window.top - offset_y
                )
                self.image_label.sequence_positions.append(adjusted_pos)
            self.update_sequence_preview()
        else:
            if task.action_position is not None:
                offset_x, offset_y = self.main_window.get_image_offset()
                self.selected_position = QPoint(
                    task.action_position[0] - self.main_window.selected_window.left - offset_x,
                    task.action_position[1] - self.main_window.selected_window.top - offset_y
                )
                self.update_position_preview(self.selected_position)
            else:
                self.selected_position = None
                self.position_preview.clear()
            self.action_click_radio.setChecked(task.action_type == 'click')
            self.action_clicks_radio.setChecked(task.action_type == 'clicks')
            if task.action_type == 'clicks':
                self.frequency_spin.setValue(task.frequency)
                self.duration_spin.setValue(task.duration)
        self.setVisible(True)

    def save_task(self):
        name = self.task_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Erro", "Nome da Task não pode estar vazio.")
            return

        condition_type = 'time' if self.condition_time_radio.isChecked() else 'color'
        if condition_type == 'time':
            condition_value = self.time_interval_spin.value()
            condition_position = None
        else:
            if self.selected_color is None or self.color_position is None:
                QMessageBox.warning(self, "Erro", "Por favor, selecione a cor e a posição.")
                return
            condition_value = self.selected_color
            # Ajustar a posição considerando o offset da área selecionada
            offset_x, offset_y = self.main_window.get_image_offset()
            condition_position = (
                self.color_position.x() + self.main_window.selected_window.left + offset_x,
                self.color_position.y() + self.main_window.selected_window.top + offset_y
            )

        # Ajustar a posição para ações que não são sequência
        if self.action_sequence_radio.isChecked():
            action_type = 'sequence'
            action_position = None
            if not self.image_label.sequence_positions:
                QMessageBox.warning(self, "Erro", "Por favor, selecione as posições da sequência.")
                return
            sequence = []
            offset_x, offset_y = self.main_window.get_image_offset()
            for pos in self.image_label.sequence_positions:
                window_pos = (
                    pos.x() + self.main_window.selected_window.left + offset_x,
                    pos.y() + self.main_window.selected_window.top + offset_y
                )
                sequence.append(window_pos)
            delay = self.sequence_delay_spin.value()
        else:
            if self.selected_position is None:
                QMessageBox.warning(self, "Erro", "Por favor, selecione uma posição.")
                return
            action_type = 'click' if self.action_click_radio.isChecked() else 'clicks'
            offset_x, offset_y = self.main_window.get_image_offset()
            action_position = (
                self.selected_position.x() + self.main_window.selected_window.left + offset_x,
                self.selected_position.y() + self.main_window.selected_window.top + offset_y
            )
            sequence = None
            delay = None

        frequency = self.frequency_spin.value() if self.action_clicks_radio.isChecked() else None
        duration = self.duration_spin.value() if self.action_clicks_radio.isChecked() else None

        # Criar ou atualizar a task
        if self.task:
            self.task.name = name
            self.task.condition_type = condition_type
            self.task.condition_value = condition_value
            self.task.condition_position = condition_position
            self.task.action_type = action_type
            self.task.action_position = action_position
            self.task.frequency = frequency
            self.task.duration = duration
            self.task.sequence = sequence
            self.task.delay = delay
            self.main_window.status_label.setText("Task editada.")
        else:
            new_task = Task(
                name, condition_type, condition_value, condition_position,
                action_type, action_position, frequency, duration, sequence, delay, self.main_window
            )
            self.main_window.tasks.append(new_task)
            task_item = TaskItem(new_task, self.main_window)
            list_item = QListWidgetItem()
            list_item.setSizeHint(task_item.sizeHint())
            self.main_window.task_list_widget.addItem(list_item)
            self.main_window.task_list_widget.setItemWidget(list_item, task_item)
            task_item.list_item = list_item
            self.main_window.status_label.setText("Task criada e adicionada à lista.")

        self.reset_fields()

    def reset_fields(self):
        self.setVisible(False)
        self.task = None
        self.image_label.sequence_positions = []
        self.sequence_positions_list.clear()
        self.selected_position = None
        self.position_preview.clear()
        self.selected_color = None
        self.color_preview.setStyleSheet("border: 1px solid black;")
        self.color_position = None
        
    def cancel_task(self):
        self.setVisible(False)
        self.task = None  # Limpa a referência à task ao cancelar
        self.main_window.status_label.setText("Edição de task cancelada.")
        # Limpa as posições da sequência ao cancelar
        self.image_label.sequence_positions = []
        self.sequence_positions_list.clear()
        self.selected_position = None
        self.position_preview.clear()
        self.selected_color = None
        self.color_preview.setStyleSheet("border: 1px solid black;")

class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Set program icon
        script_dir = os.path.dirname(os.path.realpath(__file__))
        icon_path = os.path.join(script_dir, 'resources', 'gato.png')
        self.setWindowIcon(QIcon(icon_path))
        self.setWindowTitle("Chico player")
        self.selected_window = None
        self.window_selected = False
        self.selected_area = None
        self.image_label = ImageLabel(self)
        self.tasks = []
        self.updating = False

        self.task_editor = TaskEditorWidget(self, self.image_label)
        self.initUI()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_screenshot)

        # Audio playback timer
        self.audio_timer = QTimer()
        self.audio_timer.timeout.connect(self.play_random_audio)
        self.schedule_next_audio()

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

        # Buttons to start and stop all tasks
        self.start_all_button = QPushButton("Iniciar Todas as Tasks")
        self.start_all_button.clicked.connect(self.start_all_tasks)
        self.start_all_button.setEnabled(False)

        self.stop_all_button = QPushButton("Parar Todas as Tasks")
        self.stop_all_button.clicked.connect(self.stop_all_tasks)
        self.stop_all_button.setEnabled(False)

        # Buttons to save and load profiles
        self.save_profile_button = QPushButton("Salvar Perfil")
        self.save_profile_button.clicked.connect(self.save_profile)
        self.load_profile_button = QPushButton("Carregar Perfil")
        self.load_profile_button.clicked.connect(self.load_profile)

        # Task Editor
        self.task_editor = TaskEditorWidget(self, self.image_label)
        self.task_editor.setVisible(False)

        # Task list
        self.task_list_widget = QListWidget()

        # Layouts
        main_layout = QHBoxLayout()
        left_layout = QVBoxLayout()
        center_layout = QVBoxLayout()
        right_layout = QVBoxLayout()

        # Left column layout
        left_layout.setAlignment(Qt.AlignTop)
        left_layout.addWidget(self.select_window_button)
        left_layout.addWidget(self.select_area_button)
        left_layout.addWidget(self.finish_selection_button)
        left_layout.addWidget(self.create_task_button)
        left_layout.addWidget(self.update_sample_button)
        left_layout.addWidget(self.live_update_button)
        left_layout.addWidget(self.start_all_button)
        left_layout.addWidget(self.stop_all_button)
        left_layout.addWidget(self.save_profile_button)
        left_layout.addWidget(self.load_profile_button)
        left_layout.addWidget(QLabel("Tasks:"))
        left_layout.addWidget(self.task_list_widget)
        left_layout.addWidget(self.status_label)
        left_layout.addStretch()

        # Center column layout
        center_layout.setAlignment(Qt.AlignTop)
        center_layout.addWidget(self.image_label)

        # Right column layout
        right_layout.setAlignment(Qt.AlignTop)
        right_layout.addWidget(self.task_editor)

        # Combine layouts
        main_layout.addLayout(left_layout)
        main_layout.addLayout(center_layout)
        main_layout.addLayout(right_layout)

        # Header with title and image
        header_layout = QHBoxLayout()
        header_layout.setAlignment(Qt.AlignCenter)
        title_label = QLabel("Chico player")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        # Load the image
        image_path = os.path.join(os.path.dirname(__file__), 'resources', 'gato.png')
        image_label = ClickableLabel()
        image_label.setCursor(Qt.PointingHandCursor)
        image_label.clicked.connect(self.play_meow_sound)
        pixmap = QPixmap(image_path)
        pixmap = pixmap.scaledToHeight(50, Qt.SmoothTransformation)
        image_label.setPixmap(pixmap)
        header_layout.addWidget(title_label)
        header_layout.addWidget(image_label)

        # Main layout
        overall_layout = QVBoxLayout()
        overall_layout.addLayout(header_layout)
        overall_layout.addLayout(main_layout)

        container = QWidget()
        container.setLayout(overall_layout)
        self.setCentralWidget(container)

        self.image_label.setEnabled(False)

    def get_image_offset(self):
        if self.selected_area:
            area_x, area_y, _, _ = self.selected_area
            offset_x = area_x - self.selected_window.left
            offset_y = area_y - self.selected_window.top
            return offset_x, offset_y
        else:
            return 0, 0

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
                self.status_label.setText(f"Window selected: {self.selected_window_title}")
                self.image_label.setEnabled(True)
                self.start_all_button.setEnabled(True)
                self.stop_all_button.setEnabled(True)
            else:
                self.status_label.setText("Error selecting window.")

    def update_screenshot(self):
        if self.selected_window:
            window = self.selected_window
            if self.selected_area:
                region = self.selected_area  # (x, y, width, height)
            else:
                region = (window.left, window.top, window.width, window.height)
            screenshot = pyautogui.screenshot(region=region)
            screenshot.save("window_screenshot.png")
            pixmap = QPixmap("window_screenshot.png")
            self.image_label.setPixmap(pixmap)
            self.image_label.setFixedSize(pixmap.size())

    def toggle_live_update(self):
        if not self.updating:
            self.timer.start(66)
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
        self.status_label.setText("Draw an area on the image.")

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
            self.status_label.setText("Area selected.")
            self.update_screenshot()
        else:
            self.status_label.setText("No area was selected.")
        self.finish_selection_button.setEnabled(False)

    def show_task_editor(self):
        if not self.window_selected:
            self.status_label.setText("Please select a window first.")
            return
        self.task_editor.setVisible(True)
        self.status_label.setText("Configure the task and click 'Save'.")

    def closeEvent(self, event):
        for task in self.tasks:
            task.stop()
        self.save_tasks()
        event.accept()

    def save_tasks(self, file_path='tasks.json'):
        tasks_data = []
        for task in self.tasks:
            # Converte a cor de condição para uma tupla, se necessário
            condition_value = task.condition_value
            if isinstance(condition_value, list):
                condition_value = tuple(condition_value)  # Converte lista para tupla

            tasks_data.append({
                'name': task.name,
                'condition_type': task.condition_type,
                'condition_value': condition_value,
                'condition_position': task.condition_position,
                'action_type': task.action_type,
                'action_position': task.action_position,
                'frequency': task.frequency,
                'duration': task.duration,
                'sequence': task.sequence,
                'delay': task.delay
            })
        data = {
            'tasks': tasks_data,
            'selected_area': self.selected_area
        }
        with open(file_path, 'w') as file:
            json.dump(data, file, indent=4)

    def load_tasks(self, file_path='tasks.json'):
        try:
            with open(file_path, 'r') as file:
                data = json.load(file)
                tasks_data = data.get('tasks', [])
                self.selected_area = data.get('selected_area')
                self.update_screenshot()
                for task_data in tasks_data:
                    # Converte a cor de condição para uma tupla, se estiver em formato de lista
                    condition_value = task_data['condition_value']
                    if isinstance(condition_value, list):
                        condition_value = tuple(condition_value)

                    task = Task(
                        task_data['name'],
                        task_data['condition_type'],
                        condition_value,
                        tuple(task_data['condition_position']) if task_data['condition_position'] else None,
                        task_data['action_type'],
                        tuple(task_data['action_position']) if task_data['action_position'] else None,
                        task_data.get('frequency'),
                        task_data.get('duration'),
                        task_data.get('sequence'),
                        task_data.get('delay'),
                        self
                    )
                    self.tasks.append(task)
                    task_item = TaskItem(task, self)
                    list_item = QListWidgetItem()
                    list_item.setSizeHint(task_item.sizeHint())
                    self.task_list_widget.addItem(list_item)
                    self.task_list_widget.setItemWidget(list_item, task_item)
                    task_item.list_item = list_item
                self.create_task_button.setEnabled(True)
                self.start_all_button.setEnabled(True)
                self.stop_all_button.setEnabled(True)
        except FileNotFoundError:
            pass

    def save_profile(self):
        profiles_dir = os.path.join(os.path.dirname(__file__), 'profiles')
        if not os.path.exists(profiles_dir):
            os.makedirs(profiles_dir)
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_path, _ = QFileDialog.getSaveFileName(self, "Salvar Perfil", profiles_dir, "JSON Files (*.json)", options=options)
        if file_path:
            if not file_path.endswith('.json'):
                file_path += '.json'  # Ensure the .json extension is added
            self.save_tasks(file_path)
            self.status_label.setText(f"Perfil salvo em {file_path}")

    def load_profile(self):
        profiles_dir = os.path.join(os.path.dirname(__file__), 'profiles')
        if not os.path.exists(profiles_dir):
            os.makedirs(profiles_dir)
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_path, _ = QFileDialog.getOpenFileName(self, "Carregar Perfil", profiles_dir, "JSON Files (*.json)", options=options)
        if file_path:
            # Stop all tasks before loading new ones
            self.stop_all_tasks()
            self.tasks = []
            self.task_list_widget.clear()
            self.load_tasks(file_path)
            self.status_label.setText(f"Perfil carregado de {file_path}")

    def start_all_tasks(self):
        for i in range(self.task_list_widget.count()):
            item = self.task_list_widget.item(i)
            task_item = self.task_list_widget.itemWidget(item)
            if not task_item.checkbox.isChecked():
                task_item.checkbox.setChecked(True)

    def stop_all_tasks(self):
        for i in range(self.task_list_widget.count()):
            item = self.task_list_widget.item(i)
            task_item = self.task_list_widget.itemWidget(item)
            if task_item.checkbox.isChecked():
                task_item.checkbox.setChecked(False)

    def schedule_next_audio(self):
        # Schedule the next audio playback
        interval = random.randint(1800, 7200) * 1000  # Random between 30 min and 2 hours in milliseconds
        self.audio_timer.start(interval)

    def play_random_audio(self):
        # Play the audio 1 or 2 times randomly
        times = random.randint(1, 2)
        script_dir = os.path.dirname(os.path.realpath(__file__))
        audio_path = os.path.join(script_dir, 'resources', 'meow.mp3')
        for _ in range(times):
            playsound(audio_path)
            time.sleep(0.5)  # Slight delay between plays
        self.schedule_next_audio()
        
    def play_meow_sound(self):
        script_dir = os.path.dirname(os.path.realpath(__file__))
        audio_path = os.path.join(script_dir, 'resources', 'meow.mp3')
        threading.Thread(target=playsound, args=(audio_path,), daemon=True).start()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWin = MainWindow()
    mainWin.show()
    sys.exit(app.exec_())
