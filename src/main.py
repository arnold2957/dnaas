from gui import *
import argparse

__version__ = '1.0.26' 
OWNER = "arnold2957"
REPO = "dnaas"
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

        self.is_checking_for_update = False 
        self.updater = AutoUpdater(
            msg_queue=self.msg_queue,
            github_user=OWNER,
            github_repo=REPO,
            current_version=__version__
        )
        # self.schedule_periodic_update_check()
        self.check_queue()

    def run_in_thread(self, target_func, *args):
        thread = threading.Thread(target=target_func, args=args, daemon=True)
        thread.start()
    def schedule_periodic_update_check(self):
        # 如果当前没有在检查或下载，则启动一个新的检查
        if not self.is_checking_for_update:
            # print("调度器：正在启动一小时一次的后台更新检查...")
            self.is_checking_for_update = True  # 设置标志，防止重复
            self.run_in_thread(self.updater.check_for_updates)
            self.is_checking_for_update = False
        else:
            # print("调度器：上一个检查/下载任务尚未完成，跳过本次检查。")
            None
        self.after(3600000, self.schedule_periodic_update_check)

    def check_queue(self):
        """处理来自AutoUpdater和其他服务的消息"""
        try:
            message = self.msg_queue.get_nowait()
            command, value = message
            
            # --- 这是处理更新逻辑的核心部分 ---
            match command:
                case 'start_quest':
                    self.quest_setting = value                    
                    self.quest_setting._MSGQUEUE = self.msg_queue
                    self.quest_setting._FORCESTOPING = Event()
                    Farm = Factory()
                    self.quest_threading = Thread(target=Farm,args=(self.quest_setting,))
                    self.quest_threading.start()
                    logger.info(f'启动任务\"{self.quest_setting._FARM_TYPE+self.quest_setting._FARM_LVL}(额外设定={self.quest_setting._FARM_EXTRA})\"...')

                case 'stop_quest':
                    logger.info('停止任务...')
                    if hasattr(self, 'quest_threading') and self.quest_threading.is_alive():
                        if hasattr(self.quest_setting, '_FORCESTOPING'):
                            self.quest_setting._FORCESTOPING.set()
                
                case 'turn_to_7000G':
                    logger.info('开始要钱...')
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

                case 'update_available':
                    # 在面板上显示提示
                    update_data = value
                    version = update_data['version']
                    if self.main_window:
                        self.main_window.find_update.grid()
                        self.main_window.update_text.grid()
                        self.main_window.latest_version.set(version)
                        self.main_window.button_auto_download.grid()
                        self.main_window.button_manual_download.grid()
                        self.main_window.update_sep.grid()
                        self.main_window.save_config()
                        width, height = map(int, self.main_window.geometry().split('+')[0].split('x'))
                        self.main_window.geometry(f'{width}x{height+50}')

                        self.main_window.button_auto_download.config(command=lambda:self.run_in_thread(self.updater.download))          
                case 'download_started':
                    # 控制器决定创建并显示进度条窗口
                    if not hasattr(self, 'progress_window') or not self.progress_window.winfo_exists():
                        self.progress_window = Progressbar(self.main_window,title="下载中...",max_size = value)

                case 'progress':
                    # 控制器更新进度条UI
                    if hasattr(self, 'progress_window') and self.progress_window.winfo_exists():
                        self.progress_window.update_progress(value)
                        self.update()
                        None

                case 'download_complete':
                    # 控制器关闭进度条并显示成功信息
                    if hasattr(self, 'progress_window') and self.progress_window.winfo_exists():
                        self.progress_window.destroy()

                case 'error':
                    # 控制器处理错误显示
                    if hasattr(self, 'progress_window') and self.progress_window.winfo_exists():
                        self.progress_window.destroy()
                    messagebox.showerror("错误", value, parent=self.main_window)

                case 'restart_ready':
                    script_path = value
                    messagebox.showinfo(
                        "更新完成",
                        "新版本已准备就绪，应用程序即将重启！",
                        parent=self.main_window
                    )
                    
                    if sys.platform == "win32":
                        subprocess.Popen([script_path], shell=True)
                    else:
                        os.system(script_path)
                    
                    self.destroy()
                    
                case 'no_update_found':
                    # （可选）可以给个安静的提示，或什么都不做
                    print("UI: 未发现更新。")

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


    logger.info(f"二重螺旋自动刷怪 v{__version__} @德德Dellyla(B站)")

if __name__ == "__main__":
    main()