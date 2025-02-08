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
