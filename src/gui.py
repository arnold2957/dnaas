import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import os
import logging
from script import *
from utils import *
import i18n

############################################
class ConfigPanelApp(tk.Toplevel):
    def __init__(self, master_controller, version, msg_queue):
        self.URL = "https://space.bilibili.com/8843896"
        self.TITLE = i18n.get_text("title_format", version)
        self.INTRODUCTION = i18n.get_text("intro_format", self.URL)

        RegisterQueueHandler()
        StartLogListener()

        super().__init__(master_controller)
        self.controller = master_controller
        self.msg_queue = msg_queue
        self.geometry('550x688')
        
        self.title(self.TITLE)

        self.adb_active = False

        # 关闭时退出整个程序
        self.protocol("WM_DELETE_WINDOW", self.controller.destroy)

        # --- 任务状态 ---
        self.quest_active = False

        # --- ttk Style ---
        #
        self.style = ttk.Style()
        self.style.configure("custom.TCheckbutton")
        self.style.map("Custom.TCheckbutton",
            foreground=[("disabled selected", "#8CB7DF"),("disabled", "#A0A0A0"), ("selected", "#196FBF")])
        self.style.configure("BoldFont.TCheckbutton", font=("微软雅黑", 9,"bold"))
        self.style.configure("LargeFont.TCheckbutton", font=("微软雅黑", 12,"bold"))

        # --- UI 变量 ---
        self.config = LoadConfigFromFile()
        for attr_name, var_type, var_config_name, var_default_value in CONFIG_VAR_LIST:
            if issubclass(var_type, tk.Variable):
                val = self.config.get(var_config_name,var_default_value)
                # Translate logic values to English for UI
                if var_config_name in ["_FARM_TYPE", "_FARM_LVL", "_FARM_EXTRA"]:
                    val = i18n.to_english(val)
                setattr(self, attr_name, var_type(value = val))
            else:
                setattr(self, attr_name, var_type(self.config.get(var_config_name,var_default_value)))
          
        self.create_widgets()        

        logger.info("**********************************")
        logger.info(f"Version: {version}")
        logger.info(self.INTRODUCTION, extra={"summary": True})
        logger.info("**********************************")

    def save_config(self):

        emu_path = self.emu_path_var.get()
        emu_path = emu_path.replace("HD-Adb.exe", "HD-Player.exe")
        self.emu_path_var.set(emu_path)

        for attr_name, var_type, var_config_name, _ in CONFIG_VAR_LIST:
            if issubclass(var_type, tk.Variable):
                val = getattr(self, attr_name).get()
                # Translate UI English values back to Chinese for Config
                if var_config_name in ["_FARM_TYPE", "_FARM_LVL", "_FARM_EXTRA"]:
                    val = i18n.to_chinese(val)
                self.config[var_config_name] = val
        
        SaveConfigToFile(self.config)

    def create_widgets(self):
        scrolled_text_formatter = logging.Formatter('%(message)s')
        self.log_display = scrolledtext.ScrolledText(self, wrap=tk.WORD, state=tk.DISABLED, bg='#ffffff',bd=2,relief=tk.FLAT, width = 34, height = 30)
        self.log_display.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.scrolled_text_handler = ScrolledTextHandler(self.log_display)
        self.scrolled_text_handler.setLevel(logging.INFO)
        self.scrolled_text_handler.setFormatter(scrolled_text_formatter)
        logger.addHandler(self.scrolled_text_handler)

        self.summary_log_display = scrolledtext.ScrolledText(self, wrap=tk.WORD, state=tk.DISABLED, bg="#C6DBF4",bd=2, width = 34, )
        self.summary_log_display.grid(row=1, column=1, pady=5)
        self.summary_text_handler = ScrolledTextHandler(self.summary_log_display)
        self.summary_text_handler.setLevel(logging.INFO)
        self.summary_text_handler.setFormatter(scrolled_text_formatter)
        self.summary_text_handler.addFilter(SummaryLogFilter())
        original_emit = self.summary_text_handler.emit
        def new_emit(record):
            self.summary_log_display.configure(state='normal')
            self.summary_log_display.delete(1.0, tk.END)
            self.summary_log_display.configure(state='disabled')
            original_emit(record)
        self.summary_text_handler.emit = new_emit
        logger.addHandler(self.summary_text_handler)

        self.main_frame = ttk.Frame(self, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        def checkcommand():
            self.save_config()

        #设定adb
        row_counter = 0
        frame_row = ttk.Frame(self.main_frame)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=5)  # 首行框架
        self.adb_status_label = ttk.Label(frame_row)
        self.adb_status_label.grid(row=0, column=0,)
        # 隐藏的Entry用于存储变量
        adb_entry = ttk.Entry(frame_row, textvariable=self.emu_path_var)
        adb_entry.grid_remove()
        def selectADB_PATH():
            path = filedialog.askopenfilename(
                title=i18n.get_text("select_adb_file"),
                filetypes=[("Executable", "*.exe"), ("All files", "*.*")]
            )
            if path:
                self.emu_path_var.set(path)
                self.save_config()
        # 浏览按钮
        self.adb_path_change_button = ttk.Button(
            frame_row,
            text=i18n.get_text("change"),
            command=selectADB_PATH,
            width = 5,
        )
        self.adb_path_change_button.grid(row=0,column=1)
        # 初始化标签状态
        def update_adb_status(*args):
            if self.emu_path_var.get():
                self.adb_status_label.config(text=i18n.get_text("emulator_set"), foreground="green")
            else:
                self.adb_status_label.config(text=i18n.get_text("emulator_not_set"), foreground="red")
        
        self.emu_path_var.trace_add("write", lambda *args: update_adb_status())
        update_adb_status()  # 初始调用
        ttk.Label(frame_row, text=i18n.get_text("port")).grid(row=0, column=2, sticky=tk.W, pady=5)
        vcmd_non_neg = self.register(lambda x: ((x=="")or(x.isdigit())))
        vcmd_float = self.register(lambda x: ((x=="")or(x.replace('.','',1).isdigit())))
        self.adb_port_entry = ttk.Entry(frame_row,
                                        textvariable=self.adb_port_var,
                                        validate="key",
                                        validatecommand=(vcmd_non_neg, '%P'),
                                        width=5)
        self.adb_port_entry.grid(row=0, column=3)
        self.button_save_adb_port = ttk.Button(
            frame_row,
            text=i18n.get_text("save"),
            command = self.save_config,
            width=5
            )
        self.button_save_adb_port.grid(row=0, column=4)

        # 分割线.
        row_counter += 1
        ttk.Separator(self.main_frame, orient='horizontal').grid(row=row_counter, column=0, columnspan=3, sticky='ew', pady=10)

        # 地下城目标
        def UpdateLvlCombo(*args):
            farm_type_cn = i18n.to_chinese(self.farm_type_var.get())
            if farm_type_cn in DUNGEON_TARGETS.keys():
                lvl_keys = list(DUNGEON_TARGETS[farm_type_cn].keys())
                self.farm_target_lvl_combo['values'] = [i18n.to_english(k) for k in lvl_keys]
                
                current_lvl_en = self.farm_lvl_var.get()
                if self.farm_target_lvl_combo['values'] and (current_lvl_en not in self.farm_target_lvl_combo['values']):
                    self.farm_lvl_var.set(self.farm_target_lvl_combo['values'][0])

        row_counter += 1
        frame_row = ttk.Frame(self.main_frame)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=5)  # 第二行框架
        ttk.Label(frame_row, text=i18n.get_text("dungeon_target")).grid(row=0, column=0, sticky=tk.W, pady=5)
        
        target_values = [i18n.to_english(k) for k in DUNGEON_TARGETS.keys()]
        self.farm_target_combo = ttk.Combobox(frame_row, textvariable=self.farm_type_var, values=target_values, state="readonly")
        self.farm_target_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)
        self.farm_target_combo.bind("<<ComboboxSelected>>", lambda e: self.save_config())
        self.farm_type_var.trace('w', UpdateLvlCombo)

        row_counter += 1
        frame_row = ttk.Frame(self.main_frame)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=5)  # 第二行框架
        ttk.Label(frame_row, text=i18n.get_text("level")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.farm_target_lvl_combo = ttk.Combobox(frame_row, textvariable=self.farm_lvl_var, state="readonly", width=7)
        self.farm_target_lvl_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)
        self.farm_target_lvl_combo.bind("<<ComboboxSelected>>", lambda e: self.save_config())
        UpdateLvlCombo()
        ttk.Label(frame_row, text=i18n.get_text("extra_params")).grid(row=0, column=2, sticky=tk.W, pady=5)
        
        extra_values = [i18n.to_english(k) for k in DUNGEON_EXTRA]
        self.farm_target_extra_combo = ttk.Combobox(frame_row, textvariable=self.farm_extra_var,values=extra_values, state="readonly", width=7)
        self.farm_target_extra_combo.grid(row=0, column=3, sticky=(tk.W, tk.E), pady=5)
        self.farm_target_extra_combo.bind("<<ComboboxSelected>>", lambda e: self.save_config())

        # 分割线.
        row_counter += 1
        ttk.Separator(self.main_frame, orient='horizontal').grid(row=row_counter, column=0, columnspan=3, sticky='ew', pady=10)

        # 超时设置
        row_counter += 1
        frame_row = ttk.Frame(self.main_frame)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=5)
        ttk.Label(frame_row, text=i18n.get_text("timeout_check")).grid(row=0, column=1, sticky=tk.W, pady=5)
        self.restart_intervel_entry = ttk.Entry(frame_row,
                                             textvariable=self.restart_intervel_var,
                                             validate="key",
                                             validatecommand=(vcmd_non_neg, '%P'),
                                             width=5)
        self.restart_intervel_entry.grid(row=0, column=2)
        self.button_save_restart_intervel = ttk.Button(
            frame_row,
            text=i18n.get_text("save"),
            command = self.save_config,
            width=4
            )
        self.button_save_restart_intervel.grid(row=0, column=3)

        # 自定义轮数
        row_counter += 1
        frame_row = ttk.Frame(self.main_frame)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=5)

        self.round_custom_check = ttk.Checkbutton(
            frame_row,
            variable=self.round_custom_var,
            text=i18n.get_text("use_custom_rounds"),
            command=checkcommand,
            style="Custom.TCheckbutton"
            )
        self.round_custom_check.grid(row=0, column=0)
        ttk.Label(frame_row, text=i18n.get_text("rounds")).grid(row=0, column=1, sticky=tk.W, pady=5)
        self.round_custom_time_entry = ttk.Entry(frame_row,
                                             textvariable=self.round_custom_time_var,
                                             validate="key",
                                             validatecommand=(vcmd_non_neg, '%P'),
                                             width=5)
        self.round_custom_time_entry.grid(row=0, column=2)
        self.button_save_round_custom = ttk.Button(
            frame_row,
            text=i18n.get_text("save"),
            command = self.save_config,
            width=4
            )
        self.button_save_round_custom.grid(row=0, column=3)

        # 绿书
        row_counter += 1
        frame_row = ttk.Frame(self.main_frame)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=5)

        self.use_green_book_check = ttk.Checkbutton(
            frame_row,
            variable=self.green_book_var,
            text=i18n.get_text("use_green_book"),
            command=checkcommand,
            style="Custom.TCheckbutton"
            )
        self.use_green_book_check.grid(row=0, column=0)

        self.use_green_book_final_check = ttk.Checkbutton(
            frame_row,
            variable=self.green_book_final_var,
            text=i18n.get_text("use_green_book_final"),
            command=checkcommand,
            style="Custom.TCheckbutton"
            )
        self.use_green_book_final_check.grid(row=0, column=1)


        # 分割线.
        row_counter += 1
        ttk.Separator(self.main_frame, orient='horizontal').grid(row=row_counter, column=0, columnspan=3, sticky='ew', pady=10)

        # 重置后上猪
        row_counter += 1
        frame_row = ttk.Frame(self.main_frame)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=5)

        self.cast_Q_once_check = ttk.Checkbutton(
            frame_row,
            variable=self.cast_Q_once_var,
            text=i18n.get_text("cast_q_once"),
            command=checkcommand,
            style="Custom.TCheckbutton"
            )
        self.cast_Q_once_check.grid(row=0, column=0)

        # 自动放Q技能
        row_counter += 1
        frame_row = ttk.Frame(self.main_frame)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=5)

        self.cast_Q_check = ttk.Checkbutton(
            frame_row,
            variable=self.cast_q_var,
            text=i18n.get_text("auto_cast_q"),
            command=checkcommand,
            style="Custom.TCheckbutton"
            )
        self.cast_Q_check.grid(row=0, column=0)
        ttk.Label(frame_row, text=i18n.get_text("interval_s")).grid(row=0, column=1, sticky=tk.W, pady=5)
        self.cast_Q_intervel_entry = ttk.Entry(frame_row,
                                             textvariable=self.cast_Q_intervel_var,
                                             validate="key",
                                             validatecommand=(vcmd_non_neg, '%P'),
                                             width=5)
        self.cast_Q_intervel_entry.grid(row=0, column=2)
        self.button_save_cast_Q_intervel = ttk.Button(
            frame_row,
            text=i18n.get_text("save"),
            command = self.save_config,
            width=4
            )
        self.button_save_cast_Q_intervel.grid(row=0, column=3)

        # 自动放E技能
        row_counter += 1
        frame_row = ttk.Frame(self.main_frame)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=5)

        self.cast_E_check = ttk.Checkbutton(
            frame_row,
            variable=self.cast_e_var,
            text=i18n.get_text("auto_cast_e"),
            command=checkcommand,
            style="Custom.TCheckbutton"
            )
        self.cast_E_check.grid(row=0, column=0)
        ttk.Label(frame_row, text=i18n.get_text("interval_s")).grid(row=0, column=1, sticky=tk.W, pady=5)
        self.cast_intervel_entry = ttk.Entry(frame_row,
                                             textvariable=self.cast_intervel_var,
                                             validate="key",
                                             validatecommand=(vcmd_non_neg, '%P'),
                                             width=5)
        self.cast_intervel_entry.grid(row=0, column=2)
        self.button_save_cast_intervel = ttk.Button(
            frame_row,
            text=i18n.get_text("save"),
            command = self.save_config,
            width=4
            )
        self.button_save_cast_intervel.grid(row=0, column=3)

        # Movement Sensitivity Settings
        row_counter += 1
        ttk.Separator(self.main_frame, orient='horizontal').grid(row=row_counter, column=0, columnspan=3, sticky='ew', pady=10)
        
        row_counter += 1
        frame_row = ttk.Frame(self.main_frame)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=5)
        ttk.Label(frame_row, text=i18n.get_text("movement_sensitivity"), font=("微软雅黑", 9, "bold")).grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=5)
        
        row_counter += 1
        frame_row = ttk.Frame(self.main_frame)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=2)
        ttk.Label(frame_row, text=i18n.get_text("movement_left") + " (default: 1.02)").grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        self.movement_left_mult_entry = ttk.Entry(frame_row,
                                             textvariable=self.movement_left_mult_var,
                                             validate="key",
                                             validatecommand=(vcmd_float, '%P'),
                                             width=8)
        self.movement_left_mult_entry.grid(row=0, column=1, padx=5)
        ttk.Label(frame_row, text=i18n.get_text("movement_right") + " (default: 1.02)").grid(row=0, column=2, sticky=tk.W, pady=2, padx=5)
        self.movement_right_mult_entry = ttk.Entry(frame_row,
                                             textvariable=self.movement_right_mult_var,
                                             validate="key",
                                             validatecommand=(vcmd_float, '%P'),
                                             width=8)
        self.movement_right_mult_entry.grid(row=0, column=3, padx=5)
        self.button_save_movement = ttk.Button(
            frame_row,
            text=i18n.get_text("save"),
            command = self.save_config,
            width=4
            )
        self.button_save_movement.grid(row=0, column=4, padx=5)
        
        row_counter += 1
        frame_row = ttk.Frame(self.main_frame)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=2)
        ttk.Label(frame_row, text=i18n.get_text("movement_forward") + " (default: 1.05)").grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        self.movement_forward_mult_entry = ttk.Entry(frame_row,
                                             textvariable=self.movement_forward_mult_var,
                                             validate="key",
                                             validatecommand=(vcmd_float, '%P'),
                                             width=8)
        self.movement_forward_mult_entry.grid(row=0, column=1, padx=5)
        ttk.Label(frame_row, text=i18n.get_text("movement_back") + " (default: 1.033)").grid(row=0, column=2, sticky=tk.W, pady=2, padx=5)
        self.movement_back_mult_entry = ttk.Entry(frame_row,
                                             textvariable=self.movement_back_mult_var,
                                             validate="key",
                                             validatecommand=(vcmd_float, '%P'),
                                             width=8)
        self.movement_back_mult_entry.grid(row=0, column=3, padx=5)
        
        # E技能内部计时器
        row_counter += 1
        frame_row = ttk.Frame(self.main_frame)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=5)

        self.cast_E_print_check = ttk.Checkbutton(
            frame_row,
            variable=self.cast_e_print_var,
            text=i18n.get_text("print_timers"),
            command=checkcommand,
            style="Custom.TCheckbutton"
            )
        self.cast_E_print_check.grid(row=0, column=0)

        # 分割线
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        start_frame = ttk.Frame(self)
        start_frame.grid(row=1, column=0, sticky="nsew")
        start_frame.columnconfigure(0, weight=1)
        start_frame.rowconfigure(1, weight=1)

        ttk.Separator(start_frame, orient='horizontal').grid(row=0, column=0, columnspan=3, sticky="ew", padx=10)

        button_frame = ttk.Frame(start_frame)
        button_frame.grid(row=1, column=0, columnspan=3, pady=5, sticky="nsew")
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        button_frame.columnconfigure(2, weight=1)

        label1 = ttk.Label(button_frame, text="",  anchor='center')
        label1.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)

        label3 = ttk.Label(button_frame, text="",  anchor='center')
        label3.grid(row=0, column=2, sticky='nsew', padx=5, pady=5)

        s = ttk.Style()
        s.configure('start.TButton', font=('微软雅黑', 15), padding = (0,5))
        def btn_command():
            self.save_config()
            self.toggle_start_stop()
        self.start_stop_btn = ttk.Button(
            button_frame,
            text=i18n.get_text("start_script"),
            command=btn_command,
            style='start.TButton',
        )
        self.start_stop_btn.grid(row=0, column=1, sticky='nsew', padx=5, pady= 26)


        # 分割线（移除更新相关UI）

    def set_controls_state(self, state):
        self.button_and_entry = [
            self.adb_path_change_button,
            self.adb_port_entry,
            self.button_save_adb_port,
            self.cast_E_check,
            self.cast_intervel_entry,
            self.button_save_cast_intervel,
            self.restart_intervel_entry,
            self.button_save_restart_intervel,
            self.use_green_book_check,
            self.use_green_book_final_check,
            self.round_custom_check,
            self.round_custom_time_entry,
            self.button_save_round_custom,
            self.cast_Q_check,
            self.cast_Q_intervel_entry,
            self.button_save_cast_Q_intervel,
            self.cast_E_print_check,
            self.farm_target_extra_combo,
            self.farm_target_combo,
            self.farm_target_lvl_combo,
            self.cast_Q_once_check
            ]

        if state == tk.DISABLED:
            self.farm_target_combo.configure(state="disabled")
            for widget in self.button_and_entry:
                widget.configure(state="disabled")
        else:
            self.farm_target_combo.configure(state="readonly")
            for widget in self.button_and_entry:
                widget.configure(state="normal")

    def toggle_start_stop(self):
        if not self.quest_active:
            self.start_stop_btn.config(text=i18n.get_text("stop_script"))
            self.set_controls_state(tk.DISABLED)
            setting = FarmConfig()
            config = LoadConfigFromFile()
            for attr_name, var_type, var_config_name, var_default_value in CONFIG_VAR_LIST:
                setattr(setting, var_config_name, config[var_config_name])
            setting._FINISHINGCALLBACK = self.finishingcallback
            self.msg_queue.put(('start_quest', setting))
            self.quest_active = True
        else:
            self.msg_queue.put(('stop_quest', None))

    def finishingcallback(self):
        logger.info(i18n.get_text("stopped"))
        self.start_stop_btn.config(text=i18n.get_text("start_script"))
        self.set_controls_state(tk.NORMAL)
        self.quest_active = False
