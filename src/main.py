from gui import *
import argparse
import queue
import threading
import i18n

__version__ = '1.1.1' 
# 
class AppController(tk.Tk):
    def __init__(self, headless, config_path):
        super().__init__()
        self.withdraw()
        self.msg_queue = queue.Queue()
        self.main_window = None
        if not headless:
            if not self.main_window:
                self.main_window = ConfigPanelApp(self,
                                                  __version__,
                                                  self.msg_queue)
                
        else:
            HeadlessActive(config_path,
                           self.msg_queue)
            
        self.quest_threading = None
        self.quest_setting = None

        self.check_queue()

    def run_in_thread(self, target_func, *args):
        thread = threading.Thread(target=target_func, args=args, daemon=True)
        thread.start()

    def check_queue(self):
        """处理来自后台任务的消息"""
        try:
            message = self.msg_queue.get_nowait()
            command, value = message
            
            match command:
                case 'start_quest':
                    self.quest_setting = value                    
                    self.quest_setting._MSGQUEUE = self.msg_queue
                    self.quest_setting._FORCESTOPING = Event()
                    Farm = Factory()
                    self.quest_threading = Thread(target=Farm,args=(self.quest_setting,))
                    self.quest_threading.start()
                    
                    task_name = i18n.to_english(self.quest_setting._FARM_TYPE) + i18n.to_english(self.quest_setting._FARM_LVL)
                    extra = i18n.to_english(self.quest_setting._FARM_EXTRA)
                    logger.info(i18n.get_text("starting_task", task_name, extra))

                case 'stop_quest':
                    logger.info(i18n.get_text("stopping_task"))
                    if hasattr(self, 'quest_threading') and self.quest_threading.is_alive():
                        if hasattr(self.quest_setting, '_FORCESTOPING'):
                            self.quest_setting._FORCESTOPING.set()
                
                case 'turn_to_7000G':
                    logger.info(i18n.get_text("starting_money"))
                    self.quest_setting._FARMTARGET = "7000G"
                    self.quest_setting._COUNTERDUNG = 0
                    while 1:
                        if not self.quest_threading.is_alive():
                            Farm = Factory()
                            self.quest_threading = Thread(target=Farm,args=(self.quest_setting,))
                            self.quest_threading.start()
                            break
                    if self.main_window:
                        self.main_window.turn_to_7000G()

        except queue.Empty:
            pass
        finally:
            # 持续监听
            self.after(100, self.check_queue)

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='WvDAS命令行参数')
    
    # 添加-headless标志参数
    parser.add_argument(
        '-headless', 
        '--headless', 
        action='store_true',  # 检测到参数即标记为True
        help='以无头模式运行程序'
    )
    
    # 添加可选的config_path参数
    parser.add_argument(
        '-config', 
        '--config', 
        type=str,  # 自动转换为字符串
        default=None,  # 默认值设为None
        help='配置文件路径 (例如: c:/config.json)'
    )
    
    return parser.parse_args()

def main():
    args = parse_args()

    controller = AppController(args.headless, args.config)
    controller.mainloop()

def HeadlessActive(config_path,msg_queue):
    RegisterConsoleHandler()
    RegisterQueueHandler()
    StartLogListener()

    setting = FarmConfig()
    config = LoadConfigFromFile(config_path)
    for _, _, var_config_name, _ in CONFIG_VAR_LIST:
        setattr(setting, var_config_name, config[var_config_name])
    msg_queue.put(('start_quest', setting))


    logger.info(i18n.get_text("title_format", __version__))

if __name__ == "__main__":
    main()