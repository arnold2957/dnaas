import tkinter as tk
from tkinter import ttk, scrolledtext
import json
import os
import logging
import logging.handlers
import sys
import cv2
import time
import multiprocessing
import numpy as np

# 基础模块包括:
# LOGGER. 将输入写入到logger.txt文件中.
# CONFIG. 保存和写入设置.
# CHANGES LOG. 弹窗展示更新文档.
# TOOLTIP. 鼠标悬停时的提示.

############################################
THREE_DAYS_AGO = time.time() - 3 * 24 * 60 * 60
LOGS_FOLDER_NAME = "logs"
os.makedirs(LOGS_FOLDER_NAME, exist_ok=True)
for filename in os.listdir(LOGS_FOLDER_NAME):
    file_path = os.path.join(LOGS_FOLDER_NAME, filename)
    
    # 获取最后修改时间
    creation_time = os.path.getmtime(file_path)
    
    # 如果文件创建时间早于3天前，则删除
    if creation_time < THREE_DAYS_AGO:
        os.remove(file_path)
############################################
LOG_FILE_PREFIX = LOGS_FOLDER_NAME + "/log"
logger = logging.getLogger('WvDASLogger')
#===========================================
def setup_file_handler():
    """设置文件处理器"""
    os.makedirs(LOGS_FOLDER_NAME, exist_ok=True)
    current_time = time.strftime("%y%m%d-%H%M%S")
    log_file_path = f"{LOG_FILE_PREFIX}_{current_time}.txt"
    
    file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    return file_handler

log_queue = multiprocessing.Queue(-1)
queue_listener = logging.handlers.QueueListener(log_queue, setup_file_handler())

def StartLogListener():
    queue_listener.start()
#===========================================
class LoggerStream:
    """自定义流，将输出重定向到logger"""
    def __init__(self, logger, log_level):
        self.logger = logger
        self.log_level = log_level
        self.buffer = ''  # 用于累积不完整的行
    
    def write(self, message):
        # 累积消息直到遇到换行符
        self.buffer += message
        while '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\n', 1)
            if line:  # 跳过空行
                self.logger.log(self.log_level, line)
    
    def flush(self):
        # 处理缓冲区中剩余的内容
        if self.buffer:
            self.logger.log(self.log_level, self.buffer)
            self.buffer = ''

def RegisterQueueHandler():
    """配置QueueHandler，将日志发送到队列"""
    # 保持原有的stdout/stderr重定向
    sys.stdout = LoggerStream(logger, logging.DEBUG)
    sys.stderr = LoggerStream(logger, logging.ERROR)
    
    # 创建QueueHandler并连接到全局队列
    queue_handler = logging.handlers.QueueHandler(log_queue)
    queue_handler.setLevel(logging.DEBUG)
    
    logger.setLevel(logging.DEBUG)
    logger.addHandler(queue_handler)
    logger.propagate = False

def RegisterConsoleHandler():
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__

    logger.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

class ScrolledTextHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.text_widget.config(state=tk.DISABLED)

    def emit(self, record):
        msg = self.format(record)
        try:
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.see(tk.END)
            self.text_widget.config(state=tk.DISABLED)
        except Exception:
            self.handleError(record)
class SummaryLogFilter(logging.Filter):
    def filter(self, record):
        if hasattr(record, 'summary') and record.summary:
            return True
            
        return False
############################################
def ResourcePath(relative_path):
    """ 获取资源的绝对路径，适用于开发环境和 PyInstaller 打包环境 """
    try:
        # PyInstaller 创建一个临时文件夹并将路径存储在 _MEIPASS 中
        base_path = sys._MEIPASS
    except Exception:
        # 未打包状态 (开发环境)
        # 假设 script.py 位于 C:\Users\Arnold\Desktop\andsimscripts\src\
        # 并且 resources 位于 C:\Users\Arnold\Desktop\andsimscripts\resources\
        # 我们需要从 script.py 的目录 (src) 回到上一级 (andsimscripts)
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        # 如果你的 script.py 和 resources 文件夹都在项目根目录，则 base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)
def LoadJson(path):
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                return loaded_config
        else:
            return {}   
    except json.JSONDecodeError:
        logger.error(f"错误: 无法解析 {path}。将使用默认配置。")
        return {}
    except Exception as e:
        logger.error(f"错误: 加载配置时发生错误: {e}。将使用默认配置。")
        return {}
def LoadImage(path):
    try:
        # 尝试读取图片
        img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
        # 手动抛出异常
            raise ValueError(f"[OpenCV 错误] 图片加载失败，路径可能不存在或图片损坏: {path}")
    except Exception as e:
        logger.error(f"加载图片失败: {str(e)}")
        return None
    return img
############################################
CONFIG_FILE = 'config.json'
def SaveConfigToFile(config_data):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
        logger.info("配置已保存。")
        return True
    except Exception as e:
        logger.error(f"保存配置时发生错误: {e}")
        return False
def LoadConfigFromFile(config_file_path = CONFIG_FILE):
    if config_file_path == None:
        config_file_path = CONFIG_FILE
    return LoadJson((config_file_path))
def SetOneVarInConfig(var, value):
    data = LoadConfigFromFile()
    data[var] = value
    SaveConfigToFile(data)
###########################################
QUEST_FILE = 'resources/quest/quest.json'
def BuildQuestReflection():
    try:
        data = LoadJson(ResourcePath(QUEST_FILE))
        
        quest_reflect_map = {}
        seen_names = set()
        
        # 遍历所有任务代号
        for quest_code, quest_info in data.items():
            # 获取本地化任务名称
            quest_name = quest_info["questName"]
            
            # 检查名称是否重复
            if quest_name in seen_names:
                raise ValueError(f"Duplicate questName found: '{quest_name}'")
            
            # 添加到映射表和已见集合
            quest_reflect_map[quest_name] = quest_code
            seen_names.add(quest_name)
        
        return quest_reflect_map
    
    except KeyError as e:
        raise KeyError(f"不存在'questName'属性: {e}.")
    except json.JSONDecodeError as e:
        logger.info(f"Error at line {e.lineno}, column {e.colno}: {e.msg}")
        logger.info(f"Problematic text: {e.doc[e.pos-30:e.pos+30]}")  # 显示错误上下文
        exit()
    except FileNotFoundError as e:
        raise FileNotFoundError(f"{e}")
###########################################
IMAGE_FOLDER = fr'resources/images/'
def LoadTemplateImage(shortPathOfTarget):
    logger.debug(f"加载{shortPathOfTarget}")
    pathOfTarget = ResourcePath(os.path.join(IMAGE_FOLDER + f"{shortPathOfTarget}.png"))
    return LoadImage(pathOfTarget)
###########################################
class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip_window:
            return
            
        # 获取widget的位置和尺寸
        widget_x = self.widget.winfo_rootx()
        widget_y = self.widget.winfo_rooty()
        widget_width = self.widget.winfo_width()
        widget_height = self.widget.winfo_height()
        
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)  # 移除窗口装饰
        self.tooltip_window.attributes("-alpha", 0.95)  # 设置透明度
        
        # 创建标签显示文本
        label = ttk.Label(
            self.tooltip_window, 
            text=self.text, 
            background="#ffffe0", 
            relief="solid", 
            borderwidth=1,
            padding=(8, 4),
            font=("Arial", 10),
            justify="left",
            wraplength=300  # 自动换行宽度
        )
        label.pack()
        
        # 计算最佳显示位置（默认在widget下方）
        x = widget_x + widget_width + 2
        y = widget_y + widget_height//2
        
        # 设置最终位置并显示
        self.tooltip_window.wm_geometry(f"+{int(x)}+{int(y)}")
        self.tooltip_window.deiconify()

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None