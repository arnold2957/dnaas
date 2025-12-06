from ppadb.client import Client as AdbClient
from win10toast import ToastNotifier
from scipy.optimize import curve_fit
from scipy.signal import find_peaks
from enum import Enum
from datetime import datetime
import os
import subprocess
from utils import *
import random
from threading import Thread,Event
from pathlib import Path
import numpy as np
import copy
import math

DUNGEON_TARGETS = {
    "角色经验": {"50":5},
    "角色材料": {"10":1, "30":3, "60":6},
    "武器突破": {"60":5, "70":6},
    "皎皎币":   {"60":3,"70":4},
    "夜航手册": {"30":2, "40":3,"50":4,"55":5, "60":6,"65":7,"70":8},
    "魔之楔(不是夜航手册!)": {"40":1, "60": 2, "80":3, "100":4},
    "mod强化": {"60":4, "60(测试)":4},
    "开密函": {"驱离":0, "探险无尽":0, "半自动无巧手":0},
    "钓鱼": {"悠闲":0},
    "迷津": {"测试":0}
    }
DUNGEON_EXTRA = ["无关心","1","2","3","4","5","6","7","8","9"]

####################################
CONFIG_VAR_LIST = [
            #var_name,                      type,          config_name,                  default_value
            ["farm_type_var",               tk.StringVar,  "_FARM_TYPE",                 "皎皎币"],
            ["farm_lvl_var",                tk.StringVar,  "_FARM_LVL",                  "60"],
            ["farm_extra_var",              tk.StringVar,  "_FARM_EXTRA",                "无关心"],
            ["emu_path_var",                tk.StringVar,  "_EMUPATH",                   ""],
            ["adb_port_var",                tk.StringVar,  "_ADBPORT",                   16384],
            ["last_version",                tk.StringVar,  "LAST_VERSION",               ""],
            ["latest_version",              tk.StringVar,  "LATEST_VERSION",             None],

            ["cast_e_var",                  tk.BooleanVar, "_CAST_E_ABILITY",            True],
            ["cast_intervel_var",           tk.IntVar,     "_CAST_E_INTERVAL",           7],
            ["restart_intervel_var",        tk.IntVar,     "_RESTART_INTERVAL",          2000],
            ["green_book_var",              tk.BooleanVar, "_GREEN_BOOK",                False],
            ["green_book_final_var",        tk.BooleanVar, "_GREEN_BOOK_FINAL",          False],
            ["round_custom_var",            tk.BooleanVar, "_ROUND_CUSTOM_ACTIVE",       False],
            ["round_custom_time_var",       tk.IntVar,     "_ROUND_CUSTOM_TIME",         3],
            ["cast_q_var",                  tk.BooleanVar, "_CAST_Q_ABILITY",            False],
            ["cast_Q_intervel_var",         tk.IntVar,     "_CAST_Q_INTERVAL",           25],
            ["cast_e_print_var",            tk.BooleanVar, "_CAST_E_PRINT",              False],
            ["cast_Q_once_var",             tk.BooleanVar, "_CAST_Q_ONCE",              False]
            ]

class FarmConfig:
    for attr_name, var_type, var_config_name, var_default_value in CONFIG_VAR_LIST:
        locals()[var_config_name] = var_default_value
    def __init__(self):
        #### 面板配置其他
        self._FORCESTOPING = None
        self._FINISHINGCALLBACK = None
        self._MSGQUEUE = None
        #### 底层接口
        self._ADBDEVICE = None
    def __getattr__(self, name):
        # 当访问不存在的属性时，抛出AttributeError
        raise AttributeError(f"FarmConfig对象没有属性'{name}'")
class RuntimeContext:
    #### 统计信息
    _LAPTIME = 0
    _TOTAL_TIME = 0
    _START_TIME = time.time()
    _GAME_COUNTER = 0
    _IN_GAME_COUNTER = 1
    #### 肉鸽
    _ROUGE_new_battle_reset = False
    _ROUGE_battle_finished = False
    _ROUGE_finish_counter = 0
    _ROUGE_tick_counter = 0
    #### 其他临时参数
    _MAXRETRYLIMIT = 20
    _CASTED_Q = False
    _GAME_PREPARE = False
    _CRASHCOUNTER = 0
class FarmQuest:
    _DUNGWAITTIMEOUT = 0
    _TARGETINFOLIST = None
    _SPECIALDIALOGOPTION = None
    _SPECIALFORCESTOPINGSYMBOL = None
    _SPELLSEQUENCE = None
    _TYPE = None
    def __getattr__(self, name):
        # 当访问不存在的属性时，抛出AttributeError
        raise AttributeError(f"FarmQuest对象没有属性'{name}'")

##################################################################
def KillAdb(setting : FarmConfig):
    adb_path = GetADBPath(setting)
    try:
        logger.info(f"正在检查并关闭adb...")
        # Windows 系统使用 taskkill 命令
        if os.name == 'nt':
            subprocess.run(
                f"taskkill /f /im adb.exe",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False  # 不检查命令是否成功（进程可能不存在）
            )
            time.sleep(1)
            subprocess.run(
                f"taskkill /f /im HD-Adb.exe",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False  # 不检查命令是否成功（进程可能不存在）
            )
        else:
            subprocess.run(
                f"pkill -f {adb_path}",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
        logger.info(f"已尝试终止adb")
    except Exception as e:
        logger.error(f"终止模拟器进程时出错: {str(e)}")

def KillEmulator(setting : FarmConfig):
    emulator_name = os.path.basename(setting._EMUPATH)
    emulator_SVC = "MuMuVMMSVC.exe"
    try:
        logger.info(f"正在检查并关闭已运行的模拟器实例{emulator_name}...")
        # Windows 系统使用 taskkill 命令
        if os.name == 'nt':
            subprocess.run(
                f"taskkill /f /im {emulator_name}",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False  # 不检查命令是否成功（进程可能不存在）
            )
            time.sleep(1)
            subprocess.run(
                f"taskkill /f /im {emulator_SVC}",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False  # 不检查命令是否成功（进程可能不存在）
            )
            time.sleep(1)

        # Unix/Linux 系统使用 pkill 命令
        else:
            subprocess.run(
                f"pkill -f {emulator_name}",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
            subprocess.run(
                f"pkill -f {emulator_headless}",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
        logger.info(f"已尝试终止模拟器进程: {emulator_name}")
    except Exception as e:
        logger.error(f"终止模拟器进程时出错: {str(e)}")
def StartEmulator(setting):
    hd_player_path = setting._EMUPATH
    if not os.path.exists(hd_player_path):
        logger.error(f"模拟器启动程序不存在: {hd_player_path}")
        return False

    try:
        logger.info(f"启动模拟器: {hd_player_path}")
        subprocess.Popen(
            hd_player_path,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=os.path.dirname(hd_player_path))
    except Exception as e:
        logger.error(f"启动模拟器失败: {str(e)}")
        return False

    logger.info("等待模拟器启动...")
    time.sleep(15)
def GetADBPath(setting):
    adb_path = setting._EMUPATH
    adb_path = adb_path.replace("HD-Player.exe", "HD-Adb.exe") # 蓝叠
    adb_path = adb_path.replace("MuMuPlayer.exe", "adb.exe") # mumu
    adb_path = adb_path.replace("MuMuNxDevice.exe", "adb.exe") # mumu
    if not os.path.exists(adb_path):
        logger.error(f"adb程序序不存在: {adb_path}")
        return None

    return adb_path

def CMDLine(cmd):
    logger.debug(f"cmd line: {cmd}")
    return subprocess.run(cmd,shell=True, capture_output=True, text=True, timeout=10,encoding='utf-8')

def CheckRestartConnectADB(setting: FarmConfig):
    MAXRETRIES = 20

    adb_path = GetADBPath(setting)

    for attempt in range(MAXRETRIES):
        logger.info(f"-----------------------\n开始尝试连接adb. 次数:{attempt + 1}/{MAXRETRIES}...")

        if attempt == 3:
            logger.info(f"失败次数过多, 尝试关闭adb.")
            KillAdb(setting)

            # 我们不起手就关, 但是如果2次链接还是尝试失败, 那就触发一次强制重启.

        try:
            logger.info("检查adb服务...")
            result = CMDLine(f"\"{adb_path}\" devices")
            logger.debug(f"adb链接返回(输出信息):{result.stdout}")
            logger.debug(f"adb链接返回(错误信息):{result.stderr}")

            if ("daemon not running" in result.stderr) or ("offline" in result.stdout):
                logger.info("adb服务未启动!\n启动adb服务...")
                CMDLine(f"\"{adb_path}\" kill-server")
                CMDLine(f"\"{adb_path}\" start-server")
                time.sleep(2)

            logger.debug(f"尝试连接到adb...")
            result = CMDLine(f"\"{adb_path}\" connect 127.0.0.1:{setting._ADBPORT}")
            logger.debug(f"adb链接返回(输出信息):{result.stdout}")
            logger.debug(f"adb链接返回(错误信息):{result.stderr}")

            if result.returncode == 0 and ("connected" in result.stdout or "already" in result.stdout):
                logger.info("成功连接到模拟器")
                break
            if ("refused" in result.stderr) or ("cannot connect" in result.stdout):
                logger.info("模拟器未运行，尝试启动...")
                StartEmulator(setting)
                logger.info("模拟器(应该)启动完毕.")
                logger.info("尝试连接到模拟器...")
                result = CMDLine(f"\"{adb_path}\" connect 127.0.0.1:{setting._ADBPORT}")
                if result.returncode == 0 and ("connected" in result.stdout or "already" in result.stdout):
                    logger.info("成功连接到模拟器")
                    break
                logger.info("无法连接. 检查adb端口.")

            logger.info(f"连接失败: {result.stderr.strip()}")
            time.sleep(2)
            # KillEmulator(setting)
            KillAdb(setting)
            time.sleep(2)
        except Exception as e:
            logger.error(f"重启ADB服务时出错: {e}")
            time.sleep(2)
            # KillEmulator(setting)
            KillAdb(setting)
            time.sleep(2)
            return None
    else:
        logger.info("达到最大重试次数，连接失败")
        return None

    try:
        client = AdbClient(host="127.0.0.1", port=5037)
        devices = client.devices()

        # 查找匹配的设备
        target_device = f"127.0.0.1:{setting._ADBPORT}"
        for device in devices:
            if device.serial == target_device:
                logger.info(f"成功获取设备对象: {device.serial}")
                return device
    except Exception as e:
        logger.error(f"获取ADB设备时出错: {e}")

    return None
##################################################################
def CalculRoIAverRGB(screenshot, roi=None):
    if roi is None or len(roi) == 0:
        if len(screenshot.shape) == 3:  # 彩色图像
            avg_b = np.mean(screenshot[:, :, 0])
            avg_g = np.mean(screenshot[:, :, 1])
            avg_r = np.mean(screenshot[:, :, 2])
            return (avg_r, avg_g, avg_b)
        else:  # 灰度图像
            avg = np.mean(screenshot)
            return (avg, avg, avg)

    img_height, img_width = screenshot.shape[:2]
    roi_copy = roi.copy()

    roi1_rect = roi_copy.pop(0)
    x1, y1, w1, h1 = roi1_rect

    # 计算第一个ROI区域在图像范围内的边界
    roi1_y_start = max(0, y1)
    roi1_y_end = min(img_height, y1 + h1)
    roi1_x_start = max(0, x1)
    roi1_x_end = min(img_width, x1 + w1)

    # 创建基础掩码（只包含第一个ROI区域）
    final_mask = np.zeros((img_height, img_width), dtype=bool)
    if roi1_x_start < roi1_x_end and roi1_y_start < roi1_y_end:
        final_mask[roi1_y_start:roi1_y_end, roi1_x_start:roi1_x_end] = True

    # 从第一个ROI区域中排除后续的ROI区域
    for roi2_rect in roi_copy:
        x2, y2, w2, h2 = roi2_rect

        # 计算排除区域在图像范围内的边界
        roi2_y_start = max(0, y2)
        roi2_y_end = min(img_height, y2 + h2)
        roi2_x_start = max(0, x2)
        roi2_x_end = min(img_width, x2 + w2)

        # 创建排除区域的掩码
        if roi2_x_start < roi2_x_end and roi2_y_start < roi2_y_end:
            exclude_mask = np.zeros((img_height, img_width), dtype=bool)
            exclude_mask[roi2_y_start:roi2_y_end, roi2_x_start:roi2_x_end] = True

            # 从基础掩码中排除这个区域
            final_mask = final_mask & ~exclude_mask

    # 检查是否有有效的净区域
    if not np.any(final_mask):
        return (0, 0, 0)

    # 计算净区域的平均RGB值
    if len(screenshot.shape) == 3:  # 彩色图像
        roi_pixels = screenshot[final_mask]
        avg_b = np.mean(roi_pixels[:, 0])
        avg_g = np.mean(roi_pixels[:, 1])
        avg_r = np.mean(roi_pixels[:, 2])
        return (avg_r, avg_g, avg_b)
    else:  # 灰度图像
        roi_pixels = screenshot[final_mask]
        avg = np.mean(roi_pixels)
        return (avg, avg, avg)

def CutRoI(screenshot,roi):
    if roi is None:
        return screenshot

    img_height, img_width = screenshot.shape[:2]
    roi_copy = roi.copy()
    roi1_rect = roi_copy.pop(0)  # 第一个矩形 (x, y, width, height)

    x1, y1, w1, h1 = roi1_rect

    roi1_y_start_clipped = max(0, y1)
    roi1_y_end_clipped = min(img_height, y1 + h1)
    roi1_x_start_clipped = max(0, x1)
    roi1_x_end_clipped = min(img_width, x1 + w1)

    pixels_not_in_roi1_mask = np.ones((img_height, img_width), dtype=bool)
    if roi1_x_start_clipped < roi1_x_end_clipped and roi1_y_start_clipped < roi1_y_end_clipped:
        pixels_not_in_roi1_mask[roi1_y_start_clipped:roi1_y_end_clipped, roi1_x_start_clipped:roi1_x_end_clipped] = False

    screenshot[pixels_not_in_roi1_mask] = 255

    if (roi is not []):
        for roi2_rect in roi_copy:
            x2, y2, w2, h2 = roi2_rect

            roi2_y_start_clipped = max(0, y2)
            roi2_y_end_clipped = min(img_height, y2 + h2)
            roi2_x_start_clipped = max(0, x2)
            roi2_x_end_clipped = min(img_width, x2 + w2)

            if roi2_x_start_clipped < roi2_x_end_clipped and roi2_y_start_clipped < roi2_y_end_clipped:
                pixels_in_roi2_mask_for_current_op = np.zeros((img_height, img_width), dtype=bool)
                pixels_in_roi2_mask_for_current_op[roi2_y_start_clipped:roi2_y_end_clipped, roi2_x_start_clipped:roi2_x_end_clipped] = True

                # 将位于 roi2 中的像素设置为0
                # (如果这些像素之前因为不在roi1中已经被设为0，则此操作无额外效果)
                screenshot[pixels_in_roi2_mask_for_current_op] = 0

    # cv2.imwrite(f'CutRoI_{time.time()}.png', screenshot)
    return screenshot
##################################################################

def Factory():
    toaster = ToastNotifier()
    setting =  None
    quest = None
    runtimeContext = None
    def LoadQuest(farmtarget):
        # 构建文件路径
        jsondict = LoadJson(ResourcePath(QUEST_FILE))
        if setting._FARMTARGET in jsondict:
            data = jsondict[setting._FARMTARGET]
        else:
            logger.error("任务列表已更新.请重新手动选择地下城任务.")
            return


        # 创建 Quest 实例并填充属性
        quest = FarmQuest()
        for key, value in data.items():
            if key == '_TARGETINFOLIST':
                setattr(quest, key, [TargetInfo(*args) for args in value])
            elif hasattr(FarmQuest, key):
                setattr(quest, key, value)
            elif key in ["type","questName","questId",'extraConfig']:
                pass
            else:
                logger.info(f"'{key}'并不存在于FarmQuest中.")

        if 'extraConfig' in data and isinstance(data['extraConfig'], dict):
            for key, value in data['extraConfig'].items():
                if hasattr(setting, key):
                    setattr(setting, key, value)
                else:
                    logger.info(f"Warning: Config has no attribute '{key}' to override")
        return quest
    ##################################################################
    def ResetADBDevice():
        nonlocal setting # 修改device
        if device := CheckRestartConnectADB(setting):
            setting._ADBDEVICE = device
            logger.info("ADB服务成功启动，设备已连接.")
    def DeviceShell(cmdStr):
        logger.debug(f"DeviceShell {cmdStr}")

        while True:
            exception = None
            result = None
            completed = Event()

            def adb_command_thread():
                nonlocal exception, result
                try:
                    result = setting._ADBDEVICE.shell(cmdStr, timeout=5)
                except Exception as e:
                    exception = e
                finally:
                    completed.set()

            thread = Thread(target=adb_command_thread)
            thread.daemon = True
            thread.start()

            try:
                if not completed.wait(timeout=7):
                    # 线程超时未完成
                    logger.warning(f"ADB命令执行超时: {cmdStr}")
                    raise TimeoutError(f"ADB命令在{7}秒内未完成")

                if exception is not None:
                    raise exception

                return result
            except (TimeoutError, RuntimeError, ConnectionResetError, cv2.error) as e:
                logger.warning(f"ADB操作失败 ({type(e).__name__}): {e}")
                logger.info("尝试重启ADB服务...")

                ResetADBDevice()
                time.sleep(1)

                continue
            except Exception as e:
                # 非预期异常直接抛出
                logger.error(f"非预期的ADB异常: {type(e).__name__}: {e}")
                raise

    def Sleep(t=1):
        time.sleep(t)
    def ScreenShot():
        while True:
            try:
                # logger.debug('ScreenShot')
                screenshot = setting._ADBDEVICE.screencap()
                screenshot_np = np.frombuffer(screenshot, dtype=np.uint8)

                if screenshot_np.size == 0:
                    logger.error("截图数据为空！")
                    raise RuntimeError("截图数据为空")

                image = cv2.imdecode(screenshot_np, cv2.IMREAD_COLOR)

                if image is None:
                    logger.error("OpenCV解码失败：图像数据损坏")
                    raise RuntimeError("图像解码失败")

                if image.shape != (900, 1600, 3):  # OpenCV格式为(高, 宽, 通道)
                    logger.error(f"截图尺寸异常! 当前{image.shape}, 应为(1600,900). 请检查并修改模拟器分辨率!")
                    Sleep(5)
                    raise ValueError("截图尺寸异常")

                #cv2.imwrite('screen.png', image)
                return image
            except Exception as e:
                logger.debug(f"{e}")
                if isinstance(e, (AttributeError,RuntimeError, ConnectionResetError, cv2.error)):
                    logger.info("adb重启中...")
                    ResetADBDevice()
    def CheckIf(screenImage, shortPathOfTarget, roi = None, outputMatchResult = False):
        template = LoadTemplateImage(shortPathOfTarget)
        if outputMatchResult:
            t = time.time()
            cv2.imwrite(f"DUBUG_beforeRoI_{t}.png", screenImage)
        screenshot = screenImage.copy()
        threshold = 0.80
        pos = None
        search_area = CutRoI(screenshot, roi)
        try:
            result = cv2.matchTemplate(search_area, template, cv2.TM_CCOEFF_NORMED)
        except Exception as e:
                logger.error(f"{e}")
                logger.info(f"{e}")
                if isinstance(e, (cv2.error)):
                    logger.info(f"cv2异常.")
                    # timestamp = datetime.now().strftime("cv2_%Y%m%d_%H%M%S")  # 格式：20230825_153045
                    # file_path = os.path.join(LOGS_FOLDER_NAME, f"{timestamp}.png")
                    # cv2.imwrite(file_path, ScreenShot())
                    return None

        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if outputMatchResult:
            cv2.imwrite(f"DEBUG_origin_{t}.png", screenshot)
            cv2.rectangle(screenshot, max_loc, (max_loc[0] + template.shape[1], max_loc[1] + template.shape[0]), (0, 255, 0), 2)
            cv2.imwrite(f"DEBUG_matched_{t}.png", screenshot)

        logger.debug(f"搜索到疑似{shortPathOfTarget}, 匹配程度:{max_val*100:.2f}%")
        if max_val < threshold:
            logger.debug("匹配程度不足阈值.")
            return None
        if max_val<=0.9:
            logger.debug(f"警告: {shortPathOfTarget}的匹配程度超过了{threshold*100:.0f}%但不足90%")
        logger.debug(f"{shortPathOfTarget}匹配成功!")
        pos=[max_loc[0] + template.shape[1]//2, max_loc[1] + template.shape[0]//2]
        return pos
    def CheckIf_MultiRect(screenImage, shortPathOfTarget):
        template = LoadTemplateImage(shortPathOfTarget)
        screenshot = screenImage
        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)

        threshold = 0.8
        ys, xs = np.where(result >= threshold)
        h, w = template.shape[:2]
        rectangles = list([])

        for (x, y) in zip(xs, ys):
            rectangles.append([x, y, w, h])
            rectangles.append([x, y, w, h]) # 复制两次, 这样groupRectangles可以保留那些单独的矩形.
        rectangles, _ = cv2.groupRectangles(rectangles, groupThreshold=1, eps=0.5)
        pos_list = []
        for rect in rectangles:
            x, y, rw, rh = rect
            center_x = x + rw // 2
            center_y = y + rh // 2
            pos_list.append([center_x, center_y])
            # cv2.rectangle(screenshot, (x, y), (x + w, y + h), (0, 255, 0), 2)
        # cv2.imwrite("Matched_Result.png", screenshot)
        return pos_list
    def CheckIf_FocusCursor(screenImage, shortPathOfTarget):
        template = LoadTemplateImage(shortPathOfTarget)
        screenshot = screenImage
        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)

        threshold = 0.80
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        logger.debug(f"搜索到疑似{shortPathOfTarget}, 匹配程度:{max_val*100:.2f}%")
        if max_val >= threshold:
            if max_val<=0.9:
                logger.debug(f"警告: {shortPathOfTarget}的匹配程度超过了80%但不足90%")

            cropped = screenshot[max_loc[1]:max_loc[1]+template.shape[0], max_loc[0]:max_loc[0]+template.shape[1]]
            SIZE = 15 # size of cursor 光标就是这么大
            left = (template.shape[1] - SIZE) // 2
            right =  left+ SIZE
            top = (template.shape[0] - SIZE) // 2
            bottom =  top + SIZE
            midimg_scn = cropped[top:bottom, left:right]
            miding_ptn = template[top:bottom, left:right]
            # cv2.imwrite("miding_scn.png", midimg_scn)
            # cv2.imwrite("miding_ptn.png", miding_ptn)
            gray1 = cv2.cvtColor(midimg_scn, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(miding_ptn, cv2.COLOR_BGR2GRAY)
            mean_diff = cv2.absdiff(gray1, gray2).mean()/255
            logger.debug(f"中心匹配检查:{mean_diff:.2f}")

            if mean_diff<0.2:
                return True
        return False
    def Press(pos):
        if pos!=None:
            DeviceShell(f"input tap {pos[0]} {pos[1]}")
            return True
        return False
    def PressReturn():
        DeviceShell('input keyevent KEYCODE_BACK')
    def WrapImage(image,r,g,b):
        scn_b = image * np.array([b, g, r])
        return np.clip(scn_b, 0, 255).astype(np.uint8)
    def AddImportantInfo(str):
        nonlocal runtimeContext
        if runtimeContext._IMPORTANTINFO == "":
            runtimeContext._IMPORTANTINFO = "👆向上滑动查看重要信息👆\n"
        time_str = datetime.now().strftime("%Y%m%d-%H%M%S")
        runtimeContext._IMPORTANTINFO = f"{time_str} {str}\n{runtimeContext._IMPORTANTINFO}"
    def SaveDebugImage(extraName = None):
        if extraName:
            cv2.imwrite(f"DEBUG_{extraName}_{time.time()}.png", ScreenShot())
        else:
            cv2.imwrite(f"DEBUG_{time.time()}.png", ScreenShot())
    ##################################################################
    def FindCoordsOrElseExecuteFallbackAndWait(targetPattern, fallback,waitTime):
        # fallback可以是坐标[x,y]或者字符串. 当为字符串的时候, 视为图片地址
        while True:
            for _ in range(runtimeContext._MAXRETRYLIMIT):
                if setting._FORCESTOPING.is_set():
                    return None
                scn = ScreenShot()
                if isinstance(targetPattern, (list, tuple)):
                    for pattern in targetPattern:
                        p = CheckIf(scn,pattern)
                        if p:
                            return p
                else:
                    pos = CheckIf(scn,targetPattern)
                    if pos:
                        return pos # FindCoords
                # OrElse
                def pressTarget(target):
                    if target.lower() == 'return':
                        PressReturn()
                    elif target.startswith("input swipe"):
                        DeviceShell(target)
                    else:
                        Press(CheckIf(scn, target))
                if fallback: # Execute
                    if isinstance(fallback, (list, tuple)):
                        if (len(fallback) == 2) and all(isinstance(x, (int, float)) for x in fallback):
                            Press(fallback)
                        else:
                            for p in fallback:
                                if isinstance(p, str):
                                    pressTarget(p)
                                elif isinstance(p, (list, tuple)) and len(p) == 2:
                                    t = time.time()
                                    Press(p)
                                    if (waittime:=(time.time()-t)) < 0.1:
                                        Sleep(0.1-waittime)
                                else:
                                    logger.debug(f"错误: 非法的目标{p}.")
                                    setting._FORCESTOPING.set()
                                    return None
                    else:
                        if isinstance(fallback, str):
                            pressTarget(fallback)
                        else:
                            logger.debug("错误: 非法的目标.")
                            setting._FORCESTOPING.set()
                            return None
                Sleep(waitTime) # and wait

            logger.info(f"{runtimeContext._MAXRETRYLIMIT}次截图依旧没有找到目标{targetPattern}, 疑似卡死. 重启游戏.")
            Sleep()
            restartGame()
            return None # restartGame会抛出异常 所以直接返回none就行了
    def FromAToBByC(A,B,C, verify_time=2, wait_time = 1):
        scn = ScreenShot()
        if CheckIf(scn, B):
            return True

        if A():
            Sleep(verify_time) 

            scn = ScreenShot()
            if not A():
                logger.debug("二次验证未通过, 跳过")
                return False # ABORTED_UNSTABLE_A
        
            FindCoordsOrElseExecuteFallbackAndWait(B, C, wait_time)
            
            return False # ERROR_TIMEOUT_WAITING_B
        return False # ERROR_NOT_IN_START_STATE
    def BasicStateList(always_do_before, check_list, normal_quit, always_do_after, alarm_list):
        counter = 0
        while True:
            always_do_before()

            for checkif, thendo in check_list:
                findsth = False
                if checkif():
                    thendo()
                    findsth = True
                    break

            if normal_quit():
                return

            if findsth:
                counter = 0
                continue

            counter+=1
            for checkcounter, alarm in alarm_list:
                if counter >= checkcounter:
                    if alarm():
                        return
            always_do_after()
    def restartGame(skipScreenShot = False):
        nonlocal runtimeContext
        runtimeContext._GAME_PREPARE = False
        runtimeContext._MAXRETRYLIMIT = min(50, runtimeContext._MAXRETRYLIMIT + 5) # 每次重启后都会增加5次尝试次数, 以避免不同电脑导致的反复重启问题.
        runtimeContext._IN_GAME_COUNTER = 1
        runtimeContext._CASTED_Q = False

        if not skipScreenShot:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # 格式：20230825_153045
            file_path = os.path.join(LOGS_FOLDER_NAME, f"{timestamp}.png")
            cv2.imwrite(file_path, ScreenShot())
            logger.info(f"重启前截图已保存在{file_path}中.\n请发送该截图和log文件以便进行bug反馈.")
        else:
            runtimeContext._CRASHCOUNTER +=1
            logger.info(f"跳过了重启前截图. 暂时不处理模拟器重启的问题.")
            # logger.info(f"跳过了重启前截图.\n崩溃计数器: {runtimeContext._CRASHCOUNTER}\n崩溃计数器超过5次后会重启模拟器.")
            # if runtimeContext._CRASHCOUNTER > 5:
            #     runtimeContext._CRASHCOUNTER = 0
            #     KillEmulator(setting)
            #     CheckRestartConnectADB(setting)

        waittime = 30
        packageList = DeviceShell("pm list packages -3")
        if "com.hero.dna.gf.yun.game" in packageList:
            package_name = "com.hero.dna.gf.yun.game"
            logger.info("有云游戏, 优先启动云游戏.")
            waittime = 25
        elif "com.panstudio.gplay.duetnightabyss.arpg.global" in packageList:
            package_name = "com.panstudio.gplay.duetnightabyss.arpg.global"
            logger.info("是港澳台/国际服.")
            waittime = 40
        elif "com.hero.dna.gf" in packageList:
            package_name = "com.hero.dna.gf" # "com.hero.dna.gf.yun.game"
            logger.info("准备启动游戏.")
            waittime = 40
        else:
            logger.info("你究竟再用什么版本再玩? 重启不了, 告辞.")
            return
        mainAct = DeviceShell(f"cmd package resolve-activity --brief {package_name}").strip().split('\n')[-1]
        DeviceShell(f"am force-stop {package_name}")
        Sleep(2)
        logger.info("二重螺旋, 启动!")
        logger.debug(DeviceShell(f"am start -n {mainAct}"))
        Sleep(waittime)
        raise RestartSignal()
    class RestartSignal(Exception):
        pass
    def RestartableSequenceExecution(*operations):
        while True:
            try:
                for op in operations:
                    op()
                return
            except RestartSignal:
                logger.info("任务进度重置中...")
                continue
    ##################################################################
    def ResetPosition():
        logger.info("开始复位.")
        try:
            FindCoordsOrElseExecuteFallbackAndWait(["放弃挑战","放弃挑战_云","设置"],['indungeon','indungeon_cloud'],1)
            FindCoordsOrElseExecuteFallbackAndWait("其他设置","设置",1)
            FindCoordsOrElseExecuteFallbackAndWait(["复位角色","复位角色_云"],"其他设置",1)
            FindCoordsOrElseExecuteFallbackAndWait("确定",["复位角色","复位角色_云"],1)
            while pos:=CheckIf(ScreenShot(),'确定'):
                Press(pos)
            Sleep(3)
            if not CheckIfInDungeon(ScreenShot()):
                Sleep(3)
            return True
        except Exception as e:
            logger.info(e)
            return False
    def GoLeft(time = 1000):
        SPLIT = 3000
        if time <= SPLIT:
            DeviceShell(f"input swipe 0 698 0 698 {time}")
        else:
            DeviceShell(f"input swipe 0 698 0 698 {SPLIT}")
            GoLeft(time-SPLIT)

    def DoubleJump():
        Press([1359,478])
        Sleep(0.5)
        Press([1359,478])

    def GoRight(time = 1000):
        SPLIT = 3000
        if time <= SPLIT:
            DeviceShell(f"input swipe 526 698 526 698 {time}")
        else:
            DeviceShell(f"input swipe 526 698 526 698 {SPLIT}")
            GoRight(time-SPLIT)
    def GoForward(time = 1000):
        SPLIT = 3000
        if time <= SPLIT:
            DeviceShell(f"input swipe 265 616 265 616 {time}")
        else:
            DeviceShell(f"input swipe 265 616 265 616 {SPLIT}")
            GoForward(time-SPLIT)
    def GoBack(time = 1000):
        SPLIT = 3000
        if time <= SPLIT:
            DeviceShell(f"input swipe 263 800 263 800  {time}")
        else:
            DeviceShell(f"input swipe 263 800 263 800  {SPLIT}")
            GoBack(time-SPLIT)
    def Dodge(time = 1):
        for _ in range(time):
            Press([1518,631])
            Sleep(1)
    def QuitDungeon():
        runtimeContext._GAME_COUNTER -= 1 # 因为退出流程后我们会看见再次挑战, 看见再次挑战会加1, 所以我们提前扣掉这一次.
        try:
            FindCoordsOrElseExecuteFallbackAndWait(["任务图标","放弃挑战","放弃挑战_云","再次进行"],['indungeon','indungeon_cloud'],2)
            scn = ScreenShot()
            if CheckIf(scn,"任务图标"):
                logger.info("奇怪, 怎么已经退出了.")
                return
            if CheckIf(scn,"放弃挑战") or CheckIf(scn,"放弃挑战_云"):
                Press(FindCoordsOrElseExecuteFallbackAndWait("确定",["放弃挑战","放弃挑战_云"],2))
                
                Sleep(10)
                return
            if CheckIf(scn, "再次进行"):
                return
        except:
            runtimeContext._GAME_COUNTER += 1 # 发生意外重启了, 不会看见再次挑战所以次数不会增加, 所以也没有扣掉的必要.
            return
    def CastESpell():
        nonlocal runtimeContext
        if not hasattr(CastESpell, 'last_cast_time'):
            CastESpell.last_cast_time = 0
        PROB = [1,0.30210303,0.14445311,0.08474409,0.05570346,0.03936413,0.0290976,0.02201336,0.01675358,0.01263117,0.00926888,0.00644352,0.0040144,0.00188813,0]

        if setting._CAST_E_ABILITY:
            if setting._CAST_E_PRINT:
                logger.info(f"E技能释放计时器: 当前次数:{time.time() - CastESpell.last_cast_time}")
            if time.time() - CastESpell.last_cast_time > setting._CAST_E_INTERVAL:
                Press([1086,797])
                CastESpell.last_cast_time = time.time()
    def CastQSpell():
        if not hasattr(CastQSpell, 'last_cast_time'):
            CastQSpell.last_cast_time = 0

        if setting._CAST_Q_ABILITY:
            if time.time() - CastQSpell.last_cast_time > setting._CAST_Q_INTERVAL:
                if setting._CAST_E_PRINT:
                    logger.info(f"Q技能释放计时器: 当前次数:{(time.time() - CastQSpell.last_cast_time):.2f}")
                Press([1205,779])
                Sleep(3)
                if CheckIfInDungeon():
                    Press([1203,631])
                    Sleep(1)
                    Press([1097,658])
                CastQSpell.last_cast_time = time.time()
    def CastQOnce():
        if setting._CAST_Q_ONCE:
            if not runtimeContext._CASTED_Q:
                Press([1205,779])
                Sleep(2)
                runtimeContext._CASTED_Q = True
    def CastNothingTodo():
        if not setting._CAST_Q_ABILITY:
            if not setting._CAST_E_ABILITY:
                if not hasattr(CastNothingTodo, 'last_cast_time'):
                    CastNothingTodo.last_cast_time = 0
                if time.time() - CastNothingTodo.last_cast_time > 20:
                    logger.info("呃, 什么都不干可不行, 会被踢出去的.")
                    for _ in range(3):
                        random.choice([
                            lambda: Press([1203,631]),
                            lambda: Press([1097,658]), 
                            lambda: DoubleJump()
                        ])()
                        Sleep(1)

                    CastNothingTodo.last_cast_time = time.time()
    def CastSpell():
        CastNothingTodo()
        CastQOnce()
        CastESpell()
        CastQSpell()
    def CastSpearRush(time, attack = False):
        for _ in range(time):
            DeviceShell("input swipe 1336 630 1336 630 500")
            Sleep(0.4)
        if attack:
            Press([1336,630])
            Sleep(1)
    def CheckIfInDungeon(scn = None):
        if scn is None:
            scn = ScreenShot()

        if CheckIf(scn,'indungeon',[[0,0,125,125]]) or CheckIf(scn,'indungeon_cloud',[[0,0,125,125]]):
            logger.debug("已在副本中.")
            return True
        else:
            return False
    def TryQuickUnlock(tries=1, fallback = None, args= None):
        unlock = False
        for _ in range(tries):
            Sleep(1)
            scn = ScreenShot()
            if Press(CheckIf(scn,"启动升降机")):
                Sleep(14)
                unlock = True
                break
            if Press(CheckIf(scn,"操作")) or Press(CheckIf(scn,"暴露引信")):
                Sleep(2)
                scn = ScreenShot()
                if Press(CheckIf(scn,"快速破解")) or Press(CheckIf(scn,"快速破解_云")):
                    Sleep(2)
                    unlock = True
                    break
            if (not unlock) and fallback:
                fallback(args)
        
        return unlock
    def InverseDistanceWeighting(r,g,b):
        d1 = (r-64)**2+(g-40)**2+(b-18)**2
        d2 = (r-67)**2+(g-79)**2+(b-58)**2
        d3 = (r-175)**2+(g-207)**2+(b-183)**2
        d4 = (r-113)**2+(g-157)**2+(b-126)**2
        Sa = 1/d1 + 1/d2
        Sb = 1/d3 + 1/d4
        k = Sa/(Sa+Sb)
        logger.info(f"定位结果: {k:.2f}.")
        if (k >= 0.48) and (k <= 0.52):
            logger.info(f"如果你多次看见本条信息, 请向作者报告你的画面设置和是否是云游戏.")
        if k > 0.5:
            return "A"
        else:
            return "B"
    def AUTOCalibration_Y(roi = [[175,89,1277,719]]):
        for _ in range(50):
            pos = CheckIf(ScreenShot(),"保护目标",roi) or CheckIf(ScreenShot(),"撤离点",roi)
            if not pos:
                logger.info("自动校正取消:不在目标范围内.")
                return False
            if abs(pos[0]-800) <= 10:
                return True
            DeviceShell(f"input swipe 800 450 {round((pos[0]-800)/3.5+800)} 450")
            Sleep(0.5)
        return False
    def AUTOCalibration_P(tar_p, tar_s = None, roi = None):
        """
        进行自动校准. P代表校准到一个特定的位置(p).
        tar_p: 目标符号想要前往的像素坐标.
        tar_s: 目标符号的特殊声明. 如果该参数为none, 则默认为保护目标(黄点)或撤离点(绿点).
        roi: 我们关心的图片区域. 不在这个区域中的内容一律忽略. None意味着我们使用全部的区域.
        """
        if tar_p[1] >= 595:
            if not AUTOCalibration_P([tar_p[0], 450], tar_s,roi):
                return False
        if roi == None:
            roi = [[175,89,1177,719]]
        for iter in range(50):
            scn = ScreenShot()
            if CheckIf(scn,"再次进行"):
                return False
            if tar_s == None:
                pos = CheckIf(scn,"保护目标",roi) or CheckIf(scn,"撤离点",roi)
            else:
                pos = CheckIf(scn,tar_s,roi)
            if pos:
                delta = [round((pos[0]-tar_p[0])), round((pos[1]-tar_p[1]))]
                if (abs(delta[0]) <= 5) and (abs(delta[1]) <= 5):
                    return True
                delta[0] = int(delta[0]/1.4)
                delta[1] = int(delta[1]/2)
                DeviceShell(f"input swipe 800 450 {delta[0]+800} {delta[1]+450}")
                Sleep(0.5)
        return False
    ##################################################################
    def BasicQuestSelect():
        if setting._FARM_TYPE == "开密函":
            logger.info("错误: 开密函模式无法自动选择任务. 取消执行.")
            setting._FORCESTOPING.set()
            return
        elif setting._FARM_TYPE == "迷津":
            FindCoordsOrElseExecuteFallbackAndWait("迷津",[88,407],1)
            FindCoordsOrElseExecuteFallbackAndWait("肉鸽_堕入深渊","肉鸽_前往",1)
            Press(FindCoordsOrElseExecuteFallbackAndWait("肉鸽_开始探索", ["肉鸽_堕入深渊","确定","肉鸽_关闭结算", "肉鸽_结束探索"],1))
        elif setting._FARM_TYPE != "夜航手册":
            FindCoordsOrElseExecuteFallbackAndWait(setting._FARM_TYPE,"input swipe 1400 400 1300 400",1)
            FindCoordsOrElseExecuteFallbackAndWait("开始挑战",setting._FARM_TYPE,2)
            roi = [50,182+57*(DUNGEON_TARGETS[setting._FARM_TYPE][setting._FARM_LVL]-1),275,57]
            scn = ScreenShot()
            if CheckIf(scn,"开始挑战"):
                if Press(CheckIf(scn,"等级未选中",[roi])):
                    Sleep(2)
            else:
                return # 错误. 退出.
            if setting._FARM_TYPE == "角色材料":
                mat_elem = {1: "无尽水",2: "无尽火",3:"无尽风",4:"无尽雷",5:"无尽光",6: "无尽暗"}
                if (setting._FARM_EXTRA == "无关心"):
                    select = 2
                else:
                    select = int(setting._FARM_EXTRA)
                logger.info(f"由于额外参数为\"{setting._FARM_EXTRA}\",刷取对象为{mat_elem[select]}")
                FindCoordsOrElseExecuteFallbackAndWait(mat_elem[select],[1020+83*select,778],1)
        elif setting._FARM_TYPE == "夜航手册":
            FindCoordsOrElseExecuteFallbackAndWait("前往","夜航手册",1)
            lvl = DUNGEON_TARGETS[setting._FARM_TYPE][setting._FARM_LVL]
            DeviceShell("input swipe 562 210 562 714")
            Sleep(2)
            Press([562,210+(lvl-1)*84])
            if setting._FARM_EXTRA == "无关心":
                farm_target = random.choice([1,2,3,4])
            else:
                farm_target = int(setting._FARM_EXTRA)
            if farm_target <= 5:
                FindCoordsOrElseExecuteFallbackAndWait("确认选择",[1450,228+(farm_target-1)*110],1)
            else:
                if lvl != 7:
                    DeviceShell(f"input swipe 800 555 800 222")
                    Sleep(2)
                    FindCoordsOrElseExecuteFallbackAndWait("确认选择",[1450,228+(5-1)*110],1)
                else:
                    DeviceShell(f"input swipe 800 555 800 222")
                    Sleep(2)
                    DeviceShell(f"input swipe 800 555 800 222")
                    Sleep(2)
                    FindCoordsOrElseExecuteFallbackAndWait("确认选择",[1450,228+(farm_target-4-1)*110],1)

    def resetMove():
        match setting._FARM_TYPE+setting._FARM_LVL:
            case "夜航手册40" | "夜航手册55" | "夜航手册60":
                GoForward(15000)
                GoBack(1000)
                GoLeft(100)
                return True
            case "开密函驱离":
                ResetPosition()
                return True
            case "皎皎币60":
                if not ResetPosition():
                    return False
                Sleep(3)

                if CheckIf(ScreenShot(), "保护目标", [[1091,353,81,64]]):
                    # GoForward(1500)
                    # DeviceShell(f"input swipe 800 450 1136 380")
                    # GoForward(1500)
                    # Press([520,785])
                    # Sleep(0.5)
                    # Press([1359,478])
                    # GoForward(20000)

                    # GoLeft(6000)
                    # GoForward(25000)

                    # reset_char_position = True
                    # continue
                    None
                if CheckIf(ScreenShot(), "保护目标", [[793,174,74,86]]):
                    Dodge(3)
                    GoRight(3000)
                    GoForward(16000)
                    GoLeft(2500)
                    GoForward(13000)

                    if CheckIf(ScreenShot(), "保护目标", [[502,262,96,96]]):
                        GoLeft(4000)
                        GoForward(30000)
                        return True
                    if CheckIf(ScreenShot(), "保护目标", [[746,176,98,81]]):
                        GoForward(32000)
                        return True
                return False
            case "皎皎币70":
                Sleep(2)
                if not ResetPosition():
                    return False
                scn = ScreenShot()
                if CheckIf(scn,"保护目标", [[784,254,107,112]]):
                    GoForward(14000)
                    GoRight(1200)
                    GoForward(8000)
                    GoRight(1200)
                    GoForward(7000)
                    if not ResetPosition():
                        return False
                    return True
                if CheckIf(scn,"保护目标", [[377,366,222,197]]):
                    GoBack(1000)
                    GoLeft(6000)
                    GoForward(11300)
                    GoLeft(6000)
                    DoubleJump()
                    GoLeft(3000)
                    GoLeft(14000)
                    GoLeft(6000)
                    GoBack(500)
                    GoLeft(3000)
                    GoRight(200)
                    return True
                return False
            case "夜航手册65" | "夜航手册30":
                Sleep(2)
                GoBack(1000)
                GoLeft(6000)
                GoForward(11300)
                GoLeft(6000)
                DoubleJump()
                GoLeft(3000)
                GoLeft(14000)
                if not ResetPosition():
                    return False
                return True
            case "夜航手册50":
                if CheckIf(ScreenShot(), "保护目标", [[693,212,109,110]]):
                    GoForward(9600)
                    GoRight(2850)
                    GoForward(3000)
                    GoLeft(1800)
                    GoForward(3000)
                    GoLeft(1550)
                    GoForward(2000)
                    if not ResetPosition():
                        return False
                    GoForward(10000)
                    AUTOCalibration_Y()
                    GoForward(5000)
                    return True
                if CheckIf(ScreenShot(), "保护目标", [[764,217,80,96]]):
                    GoForward(5000)
                    Sleep(1)
                    if CheckIf(ScreenShot(), "保护目标", [[745,175,126,92]]): # 电梯
                        GoForward(round((3-4/60)*1000))
                        if TryQuickUnlock():
                            GoForward(round((18+18/60)*1000))
                            return True
                        return False
                    if CheckIf(ScreenShot(), "保护目标", [[745,266,126,94]]): # 平台
                        GoRight(round((1+14/60)*1000))
                        GoForward(round((2+42/60)*1000))
                        GoLeft(round((2+30/60)*1000))
                        GoForward(round((4+42/60)*1000))
                        GoRight(round((1+28/60)*1000))
                        GoForward(round((15+54/60)*1000))
                        return True
                    return False
            case "角色经验50":
                if CheckIf(ScreenShot(), "保护目标", [[693,212,109,110]]):
                    GoForward(9600)
                    GoLeft(400)
                    if TryQuickUnlock():
                        GoRight(3250)
                        GoForward(3000)
                        GoLeft(1800)
                        GoForward(3000)
                        GoLeft(1550)
                        GoForward(2000)
                        if not ResetPosition():
                            return False
                        Sleep(5)
                        GoBack(5000)
                        Sleep(5)
                        GoBack(5000)
                        if not ResetPosition():
                            return False
                        for i in range(setting._RESTART_INTERVAL):
                            if CheckIf(ScreenShot(), "血清100%",[[69,227,153,108]]):
                                break
                            elif CheckIf(ScreenShot(), "可前往撤离点"):
                                break
                            else:
                                CastSpell()
                                Sleep(1)
                            if i == setting._RESTART_INTERVAL - 1:
                                return False
                        if not ResetPosition():
                            return False
                        GoLeft(4000)
                        DoubleJump()
                        GoLeft(1000)
                        DoubleJump()
                        GoLeft(1000)
                        GoRight(3000)
                        GoLeft(200)
                        return True
                return False
            case "角色材料10" | "开密函探险无尽":
                if not ResetPosition():
                    return False
                Sleep(3)
                if CheckIf(ScreenShot(), "保护目标", [[394,297,169,149]]):
                    GoLeft(2800)
                    if TryQuickUnlock():
                        GoRight(800)
                        return True
                return False
            case "角色材料30" | "角色材料60":
                if not ResetPosition():
                    return False
                GoLeft(9150)
                GoBack(1000)
                Press([1359,478])
                Sleep(0.5)
                Press([1359,478])
                GoBack(500)
                Sleep(0.5)
                Press([1359,478])
                Sleep(0.5)
                Press([1359,478])
                GoBack(500)
                if TryQuickUnlock():
                    GoLeft(4700)
                    GoBack(2000)
                    DeviceShell("input swipe 800 450 800 850 500")
                    DeviceShell("input swipe 800 450 800 850 500")
                    DeviceShell("input swipe 800 450 800 850 500")
                    return True
                return False
            case "武器突破60" | "武器突破70":
                GoRight(round((2+(56-32)/60)*1000))
                GoForward(round((42-25+34/60)*1000))
                GoLeft(round((2+22/60)*1000))
                GoForward(round((53-45+24/60)*1000))
                GoLeft(round((2+52/60)*1000))
                GoForward(round((9)*1000))
                GoRight(round((5+18/60)*1000))
                GoForward(round((1+20/60)*1000))
                GoLeft(round((4+14/60)*1000))
                GoForward(6000)
                if AUTOCalibration_Y([[395,61,769,381]]):
                    GoForward(round((3.5+16/60)*1000))
                    DoubleJump()
                    GoForward(1000)
                    if TryQuickUnlock(5, GoBack, 50):
                        if not ResetPosition():
                            return False
                        GoLeft(round((4-2/60)*1000))
                        for i in range(setting._RESTART_INTERVAL):
                            if CheckIf(ScreenShot(), "可前往撤离点"):
                                break
                            else:
                                CastSpell()
                                Sleep(1)
                            if i == setting._RESTART_INTERVAL - 1:
                                return False
                        for _ in range(10):
                            scn = ScreenShot()
                            if not CheckIfInDungeon(scn):
                                return False
                            if not ResetPosition():
                                return False
                            Sleep(3)
                            if CheckIf(scn,"撤离点",[[708,394,145,182]]):
                                AUTOCalibration_Y([[634,394,350,159]])
                                GoForward(round((24-4/60)*1000))
                                if CheckIf(ScreenShot(),"再次进行"):
                                    return True
                                continue
                            k = InverseDistanceWeighting(*CalculRoIAverRGB(ScreenShot(),[[0,535,544,899-535]]))
                            if k == 'A':
                                GoRight(round((3-2/60)*1000))
                                GoForward(round((2+30/60)*1000))
                                GoRight(round((4-56/60)*1000))
                                GoBack(round((4-4/60)*1000))
                                GoRight(round((4-12/60)*1000))
                                GoForward(round((9+44/60)*1000))
                                GoRight(round((9-14/60)*1000))
                                continue
                            if k == 'B':
                                GoForward(1000)
                                GoRight(round((14-56/60)*1000))
                                GoForward(round((6+24/60)*1000))
                                GoLeft(round((4-54/60)*1000))
                                GoForward(round((4-10/60)*1000))
                                if AUTOCalibration_Y([[634,394,350,159]]):
                                    GoForward(round((24-4/60)*1000))
                                    if CheckIf(ScreenShot(),"再次进行"):
                                        return True
                                continue
                return False
            case "mod强化60" | "mod强化60(测试)":
                def finalRoom():
                    AUTOCalibration_P([800,450])
                    CastSpearRush(3)
                    for iter in range(10):
                        if CheckIf(ScreenShot(),"护送目标前往撤离点"):
                            if AUTOCalibration_P([800,595]):
                                CastSpearRush(3,True)
                                GoBack(2000)
                        if iter >= 5:
                            Sleep(1)
                        if CheckIf(ScreenShot(),"再次进行"):
                            logger.info("营救结束.")
                            return True
                    return False
                def saveVIP():
                    ResetPosition()
                    if not CheckIf(ScreenShot(), "操作_营救"):
                        return
                    DeviceShell("input swipe 800 450 1083 450 500")
                    if not AUTOCalibration_P([983,450], "操作_营救"):
                        return False
                    GoForward(5000)
                    DoubleJump()
                    GoForward(2000)
                    if not AUTOCalibration_P([800,450], "操作_营救"):
                        return False
                    GoForward(1000)
                    if not TryQuickUnlock(5, GoForward, 100):
                        return False
                    
                    DeviceShell("input swipe 800 450 750 450 500")
                    AUTOCalibration_P([736,389],None,[[575,335,264,443]])
                    GoForward(9000)
                    DeviceShell("input swipe 800 450 1300 450 500")
                    AUTOCalibration_P([800,450],None,[[597,213,344,380]])
                    GoForward(2000)
                    if not TryQuickUnlock(5, GoForward, 100):
                        return False
                    Sleep(2)
                    if CheckIf(ScreenShot(),"护送目标前往撤离点"):
                        logger.info("人质已救出!")
                        DeviceShell(f"input swipe 800 450 {1600-1528} 450 500")
                        if not AUTOCalibration_P([865,450]):
                            return False
                        GoForward(5500)
                        Sleep(1)
                        if not AUTOCalibration_P([810,418]):
                            return False
                        CastSpearRush(4)
                        Sleep(1)
                        return finalRoom()

                    DeviceShell("input swipe 800 450 1528 450 500")
                    DeviceShell("input swipe 800 450 1528 450 500")
                    DeviceShell("input swipe 800 450 1100 450 500")
                    if not AUTOCalibration_P([800,450], None,[[567,226,317,409]]):
                        return False
                    GoForward(7000)
                    if not TryQuickUnlock(5, GoForward, 100):
                        return False
                    if CheckIf(ScreenShot(),"护送目标前往撤离点"):
                        logger.info("人质已救出!")
                        DeviceShell("input swipe 800 450 1528 450 500")
                        GoRight(2000)
                        if not AUTOCalibration_P([800,500]):
                            return False
                        CastSpearRush(5)
                        Sleep(1)
                        return finalRoom()

                    GoBack(7000)
                    DeviceShell("input swipe 800 450 1200 450 500")
                    if not AUTOCalibration_P([985,440], None,[[640,241,660,450]]):
                        return False
                    GoForward(7000)
                    DeviceShell("input swipe 800 450 1190 450 500")
                    if not AUTOCalibration_P([800,450], None,[[640,241,437,450]]):
                        return False
                    GoForward(2500)
                    if not TryQuickUnlock(5, GoForward, 100):
                        return False
                    Sleep(2)
                    if CheckIf(ScreenShot(),"护送目标前往撤离点"):
                        logger.info("人质已救出!")
                        if not AUTOCalibration_P([964,561]):
                            return False
                        CastSpearRush(2)
                        if not AUTOCalibration_P([800,450]):
                            return False
                        CastSpearRush(2)
                        return finalRoom()
                    
                    logger.info("第四个房间")
                    if setting._FARM_TYPE+setting._FARM_LVL == "mod强化60(测试)":
                        DeviceShell("input swipe 1528 450 600 450 500")
                        AUTOCalibration_P([800,450])
                        GoLeft(2300)
                        GoForward(2000)
                        AUTOCalibration_P([800,595])
                        CastSpearRush(2,True)
                        AUTOCalibration_P([800,595])
                        CastSpearRush(2,True)
                        GoBack(500)
                        DeviceShell("input swipe 1528 450 800 450 500")
                        AUTOCalibration_P([730,450])
                        if not TryQuickUnlock(5, GoForward, 100):
                            return False
                        Sleep(2)
                        if CheckIf(ScreenShot(),"护送目标前往撤离点"):
                            logger.info("人质已救出!")
                            AUTOCalibration_P([800,450])
                            GoRight(2000)
                            GoForward(2000)
                            GoRight(2000)
                            GoForward(2000)                
                            GoRight(2000)
                            if not AUTOCalibration_P([800,450]):
                                    return
                            CastSpearRush(3)
                            return finalRoom()

                    return False
                ################## 第一个房间
                if not AUTOCalibration_P([800,595]):
                    return
                CastSpearRush(4, True)
                if not AUTOCalibration_P([800,450]):
                    return
                CastSpearRush(2)
                Sleep(2)
                ################## 第二个房间
                scn = ScreenShot()
                if CheckIf(scn,"保护目标", [[802-50,480-50,100,100]]):
                    logger.info("正对")
                    CastSpearRush(2)
                    if not AUTOCalibration_P([800,595]):
                        return
                    CastSpearRush(3, True)
                    GoBack(2000)
                    if not AUTOCalibration_P([800,595]):
                        return
                    CastSpearRush(2, True)
                    Sleep(2)
                    CastSpearRush(2)
                    
                    return saveVIP()
                elif CheckIf(scn,"保护目标", [[646-50,377-50,100,100]]):
                    logger.info("左上")
                    CastSpearRush(2)
                    if not AUTOCalibration_P([800,595]):
                        return
                    CastSpearRush(4)
                    GoBack(2000)
                    if not AUTOCalibration_P([800,450]):
                        return
                    CastSpearRush(2)
                    return saveVIP()
                elif CheckIf(scn,"保护目标", [[1095-50,431-50,100,100]]):
                    DeviceShell("input swipe 800 450 1107 450 500")
                    if CheckIf(ScreenShot(),"保护目标",[[620-50,431-50,100,100]]):
                        logger.info("左上")
                        if not AUTOCalibration_P([723,595]):
                            return
                        CastSpearRush(5, True)
                        if not AUTOCalibration_P([800,450]):
                            return
                        CastSpearRush(3)
                        return saveVIP()
                    else:
                        logger.info("左下")
                        if not AUTOCalibration_P([882,595]):
                            return
                        CastSpearRush(3)
                        if not AUTOCalibration_P([800,450]):
                            return
                        CastSpearRush(1)
                        Sleep(1)
                        CastSpearRush(1)
                        return saveVIP()

                logger.info("不可用的第二个房间.")
                return False
            case "迷津测试":
                logger.info("不对, 你怎么能运行这个??")
                return True
            case _ :
                logger.info("没有设定开场移动. 原地挂机.")
                return True
    ################################################################
    def QuestFarm():
        nonlocal runtimeContext
        runtimeContext._START_TIME = time.time()
        runtimeContext._TOTAL_TIME = 0
        runtimeContext._IN_GAME_COUNTER = 1
        runtimeContext._GAME_COUNTER = 0
        runtimeContext._GAME_PREPARE = False

        if (setting._FARM_TYPE not in DUNGEON_TARGETS.keys()) or (setting._FARM_LVL not in DUNGEON_TARGETS[setting._FARM_TYPE].keys()):
            logger.info("\n\n任务列表已更新! 请重新手动选择地下城任务!\n\n")
            setting._FINISHINGCALLBACK()
            return

        if setting._ROUND_CUSTOM_ACTIVE:
            DEFAULTWAVE = setting._ROUND_CUSTOM_TIME
            logger.info(f"已设置自定义轮数, 每次将刷取{DEFAULTWAVE}轮次.")
        else:
            match setting._FARM_TYPE+setting._FARM_LVL:
                case "皎皎币60" | "皎皎币70":
                    DEFAULTWAVE = 3
                case "角色材料10":
                    DEFAULTWAVE = 15
                case "角色材料30" | "角色材料60" | "开密函探险无尽" | "开密函半自动无巧手":
                    DEFAULTWAVE = 15
                case _:
                    DEFAULTWAVE = 1
            logger.info(f"{setting._FARM_TYPE+setting._FARM_LVL}的默认局内轮次数为{DEFAULTWAVE}.")

        ########################################
        handlers = []
        handlers_rouge = []
        def register(list_type='all'):
            def decorator(func):
                if list_type == 'normal' or list_type == 'all':
                    handlers.append(func)
                if list_type == 'rouge' or list_type == 'all':
                    handlers_rouge.append(func)
                return func
            return decorator

        @register()
        def handle_relogin(scn):
            if Press(CheckIf(scn,"重新连接")):
                logger.info("重新连接.")
                Sleep(1)
                return True
            return False
        @register()
        def handle_login(scn):
            if Press(CheckIf(scn, "点击进入游戏")) or Press(CheckIf(scn, "点击进入游戏_云")):
                logger.info("点击进入游戏.")
                Sleep(20)
                return True
            return False
        @register('normal')
        def handle_fishing(scn):
            counter = 0
            quit_counter = 0
            t = time.time()
            if setting._FARM_TYPE == "钓鱼":
                while 1:
                    scn = ScreenShot()
                    if setting._FORCESTOPING.is_set():
                        logger.info("检测到停止请求, 结束钓鱼处理.")
                        return True
                    Press([802,741])
                    if CheckIf(scn, "悠闲钓鱼_无鱼"):
                        logger.info("检测到无鱼提示，停止钓鱼。")
                        setting._FORCESTOPING.set()
                        return False
                    if (not CheckIfInDungeon(scn)) and (not CheckIf(scn,"悠闲钓鱼_钓到鱼了")) and (not CheckIf(scn,"悠闲钓鱼_新图鉴")):
                        Press([802,741])
                        if quit_counter % 10 == 0:
                            logger.info(f"不在钓鱼界面.({quit_counter // 10})")
                        quit_counter +=1
                        Sleep(1)
                    Press(CheckIf(scn,"悠闲钓鱼_收杆"))
                    Press(CheckIf(scn,"悠闲钓鱼_授鱼以鱼"))
                    if (CheckIf(scn,"悠闲钓鱼_钓到鱼了")) or (CheckIf(scn,"悠闲钓鱼_新图鉴")):
                        logger.info("钓到鱼了!")
                        Press([802,741])
                        Sleep(3)
                        counter+=1
                        logger.info(f"钓到了{counter}条鱼, 累计用时{(time.time()-t):.2f}秒.", extra={"summary": True})                    
        @register('normal')
        def handle_dig(scn):
            if CheckIf(scn,"勘察", [[57,279,43,24]]):
                logger.info("检测到勘察任务, 强制结束.")
                setting._FORCESTOPING.set()
                return True
            return False
        @register('normal')
        def handle_coop_accept(scn):
            if Press(CheckIf(scn,"多人联机_同意", [[1514,67,64,64]])):
                logger.info("检测到多人联机的请求, 同意请求.")
                setting._FORCESTOPING.set()
                return True
            return False
        @register()
        def handle_menu(scn):
            if CheckIf(scn, "任务图标"):
                logger.info("任务菜单.")
                Press([63,27])
                Sleep(2)
                return True
            return False
        @register()
        def handle_quest(scn):
            if Press(CheckIf(scn, "历练")):
                logger.info("历练.")
                Sleep(1)
                return True
            return False
        @register()
        def handle_farm(scn):
            if CheckIf(scn,"入门指南"):
                FindCoordsOrElseExecuteFallbackAndWait("委托",[89,231],1)
                return True
            return False
        @register()
        def handle_dungeon_select(scn):
            if CheckIf(scn,"勘察无尽"):
                logger.info("关卡选择.")
                try:
                    BasicQuestSelect()
                except Exception as e:
                    logger.info(e)
                    return False
                return True
            return False
        @register('normal')
        def handle_start_dungeon(scn):
            if pos:=(CheckIf(scn, "开始挑战")):
                logger.info("开始挑战!")
                if setting._GREEN_BOOK or (setting._GREEN_BOOK_FINAL and (runtimeContext._IN_GAME_COUNTER == DEFAULTWAVE)):
                    if setting._GREEN_BOOK:
                        logger.info("因为面板设置, 使用了绿书.")
                    if (setting._GREEN_BOOK_FINAL and (runtimeContext._IN_GAME_COUNTER == DEFAULTWAVE)):
                        logger.info("因为面板设置, 这是最后一小局, 使用了绿书.")
                    Press([620,520])
                    Sleep(0.5)
                Press(pos)
                Sleep(2)
                return True
            return False
        @register('normal')
        def handle_confirm_and_select_letter(scn):
            if (find_nuts:=CheckIf(scn, "选择密函")) or (CheckIf(scn, "确认选择")):
                if find_nuts:
                    Press([889,458])
                    Sleep(0.2)
                    Press([889,458])
                    Sleep(0.2)
                Press(CheckIf(scn,"确认选择"))
                return True
            return False
        @register()
        def handle_rez(scn):
            if Press(CheckIf(scn, "复苏")):
                return True
            return False
        @register()
        def handle_monthly_sub(scn):
            now = datetime.now()
            seconds_since_midnight = (now - now.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()
            if (seconds_since_midnight>=4*3600) and (seconds_since_midnight<=6*3600):
                if Press(CheckIf(scn,"小月卡")):
                    logger.info("已领取小月卡.")
                    return True
            return False
        @register('normal')
        def handle_countinue_in_game(scn):
            nonlocal runtimeContext
            if (CheckIf(scn, "继续挑战")):
                logger.info(f"已完成第{runtimeContext._IN_GAME_COUNTER}小局!")
                if runtimeContext._IN_GAME_COUNTER + 1 <= DEFAULTWAVE:
                    cost_time = time.time()-runtimeContext._START_TIME
                    runtimeContext._TOTAL_TIME = runtimeContext._TOTAL_TIME + cost_time
                    logger.info(f"本轮用时{cost_time:.2f}秒.\n累计用时{runtimeContext._TOTAL_TIME:.2f}秒.")
                    runtimeContext._START_TIME = time.time()

                    runtimeContext._IN_GAME_COUNTER +=1
                    logger.info(f"开始第{runtimeContext._IN_GAME_COUNTER}小局...")
                    while Press(CheckIf(ScreenShot(), "继续挑战")):
                        1
                else:
                    logger.info("已完成目标小局, 撤离")
                    for _ in range(50):
                        if Press(CheckIf(ScreenShot(), "撤离")):
                            break
                        Sleep(1)

                    runtimeContext._IN_GAME_COUNTER = 1
                    Sleep(2)
                return True
            return False
        @register()
        def handle_continue(scn):
            nonlocal runtimeContext
            if pos:=(CheckIf(scn, "再次进行")):
                Press(pos)
                runtimeContext._CASTED_Q = False
                cost_time = time.time()-runtimeContext._START_TIME
                if cost_time > 10:
                    runtimeContext._GAME_COUNTER += 1
                    runtimeContext._GAME_PREPARE = False
                    runtimeContext._TOTAL_TIME = runtimeContext._TOTAL_TIME + cost_time
                    logger.info(f"本轮用时{cost_time:.2f}秒.\n累计用时{runtimeContext._TOTAL_TIME:.2f}秒.")
                    logger.info(f"第{runtimeContext._GAME_COUNTER}次{setting._FARM_TYPE+setting._FARM_LVL}完成.\n累计用时{runtimeContext._TOTAL_TIME:.2f}秒.", extra={"summary": True})
                    runtimeContext._START_TIME = time.time()
                return True
            return False
        @register('normal')
        def handle_in_dungeon(scn):
            nonlocal runtimeContext
            if CheckIfInDungeon(scn):
                if not runtimeContext._GAME_PREPARE:
                    Sleep(1)
                    if resetMove():
                        runtimeContext._GAME_PREPARE = True
                    else:
                        logger.info("尚未支持的地图, 重新进本.")
                        # SaveDebugImage()
                        QuitDungeon()
                        return True

                if time.time() - runtimeContext._START_TIME > setting._RESTART_INTERVAL:
                    logger.info("时间太久了, 重来吧")
                    runtimeContext._START_TIME = time.time()
                    QuitDungeon()
                    return True
                CastSpell()
                return True
            return False
        @register()
        def handle_cloud_start(scn):
            if pos:=CheckIf(scn,"上次登录"):
                Press([200,pos[1]])
                return True
            if Press(CheckIf(scn,"我知道啦")) or Press(CheckIf(scn,"我知道啦_2")):
                return True
            if Press(CheckIf(scn,"开始游戏_云_登录")):
                return True
            if Press(CheckIf(scn,"退出游戏")):
                return True
            return False
        @register('rouge')
        def handle_rouge_enter(scn):
            if Press(CheckIf(scn, "肉鸽_开始探索")) or Press(CheckIf(scn, "肉鸽_堕入深渊")):
                return True
            if Press(CheckIf(scn, "肉鸽_进入下一个区域")):
                Sleep(2)
                return True
            return False
        @register('rouge')
        def handle_rouge_RESTART(scn):
            if runtimeContext._ROUGE_tick_counter > 3600:
                runtimeContext._ROUGE_tick_counter = 0
                logger.info("时间太久了, 重来吧")
                runtimeContext._START_TIME = time.time()
                restartGame()
                return True
        @register('rouge')
        def handle_rouge_battle(scn):
            if CheckIf(scn, "肉鸽_战斗", [[1318,69,231,72]]):
                runtimeContext._ROUGE_battle_finished = False
                runtimeContext._ROUGE_tick_counter += 1
                if CheckIf(scn,"保护目标", [[522,337,201,144]]):
                    AUTOCalibration_P([800,450])
                    GoForward(11000)
                if runtimeContext._ROUGE_tick_counter % 7 == 0:
                    Press([1097,658])
                    DeviceShell(f"input swipe 800 0 800 800 500")
                    DeviceShell(f"input swipe 800 450 800 200 500")
                if runtimeContext._ROUGE_tick_counter % 3 == 0:
                    Press([1086,797])
                else:
                    Press([1203,631])
                    Sleep(1)
                    Press([1203,631])
                runtimeContext._ROUGE_new_battle_reset = False
                runtimeContext._ROUGE_battle_finished = False
                return True
            return False
        def Rouge_CheckNextStage(scn):
            if Press(CheckIf(scn, "肉鸽_进入下一个区域")) or Press(CheckIf(scn,"肉鸽_休整按钮")) or Press(CheckIf(scn,"肉鸽_高危战斗")):
                return True
            return False
        @register('rouge')
        def handle_rouge_explore(scn):
            if CheckIf(scn, "肉鸽_继续探索", [[1370,62,195,59]]):
                runtimeContext._ROUGE_tick_counter+=1
                if not runtimeContext._ROUGE_battle_finished:
                    Sleep(2)
                    scn = ScreenShot()
                    if CheckIf(scn, "肉鸽_继续探索", [[1370,62,195,59]]):
                        runtimeContext._ROUGE_battle_finished = True
                elif runtimeContext._ROUGE_battle_finished:
                    if not runtimeContext._ROUGE_new_battle_reset:
                        # ResetPosition()
                        # DoubleJump()
                        # Sleep(1)
                        runtimeContext._ROUGE_new_battle_reset = True
                        # SaveDebugImage()
                    else:
                        for stage in ["肉鸽_boss战", "肉鸽_下一个战斗区域","肉鸽_下一个困难战斗区域","肉鸽_最后boss"]:
                            if pos:=CheckIf(scn, stage):
                                if Rouge_CheckNextStage(scn):
                                    break
                                if (abs(pos[0]-800)>30) or (abs(pos[1]-450)>30):
                                    AUTOCalibration_P([800,450],stage)
                                if runtimeContext._ROUGE_tick_counter % 5 == 0:
                                    DoubleJump()
                                GoForward(1000)
                                if Rouge_CheckNextStage(ScreenShot()):
                                    break
                                break
                return True
            return False
        @register('rouge')
        def handle_rouge_rest(scn):
            locals_dict = locals()
            if '_has_forwarded' not in locals_dict:
                locals_dict['_has_forwarded'] = False

            if Press(CheckIf(scn,"肉鸽_休整按钮")):
                return True
            if CheckIf(scn, "肉鸽_休整", [[1370,62,195,59]]):
                if not locals_dict['_has_forwarded']:
                    GoForward(5000)
                    locals_dict['_has_forwarded'] = True
                for stage in ["肉鸽_boss战", "肉鸽_下一个战斗区域","肉鸽_下一个困难战斗区域", "肉鸽_最后boss"]:
                    if pos:=CheckIf(scn, stage):
                        if Rouge_CheckNextStage(scn):
                            locals_dict['_has_forwarded'] = False
                            break
                        if (abs(pos[0]-800)>30) or (abs(pos[1]-450)>30):
                            AUTOCalibration_P([800,450],stage)
                        if runtimeContext._ROUGE_tick_counter % 5 == 0:
                            DoubleJump()
                        GoForward(1000)
                        if Rouge_CheckNextStage(ScreenShot()):
                            locals_dict['_has_forwarded'] = False
                            break
                        break

        @register('rouge')
        def handle_rouge_relic(scn):
            if CheckIf(scn, "肉鸽_选择烛芯", [[1014,838,272,53]]):
                Press([766,695])
                Press([1414,861])
                return True
            return False
        @register('rouge')
        def handle_rouge_finishing(scn):
            if Press(CheckIf(scn, "肉鸽_关闭结算")):
                Sleep(2)
                runtimeContext._ROUGE_tick_counter = 0
                runtimeContext._ROUGE_finish_counter += 1
                logger.info(f"已完成{runtimeContext._ROUGE_finish_counter}次肉鸽.", extra={"summary": True})
                pass
        @register('rouge')
        def handle_rouge_begining_relic(scn):
            if CheckIf(scn, "肉鸽_额外遗物"):
                Press([500,425])
                Press([1414,861])
                return True
            return False
        @register('rouge')
        def handle_rouge_stack(scn):
            Press([800,858])
            return False
        ########################################
        if setting._FARM_TYPE+setting._FARM_LVL == "迷津测试":
            logger.info("使用肉鸽模式.")
            active_handlers = handlers_rouge
        else:
            active_handlers = handlers

        check_counter = 0
        round_time = time.time()

        while 1:
            if setting._FORCESTOPING.is_set():
                break

            scn = ScreenShot()

            handled_scene = False
            for handler in active_handlers:
                if handler(scn):
                    handled_scene = True
                    break

            if handled_scene == True:
                check_counter = 0
                continue
            else:
                check_counter +=1
                Press([1,1])

            if time.time()-round_time < 1:
                Sleep(1-(time.time()-round_time))
                round_time = time.time()
                logger.debug(f"round time {round_time}")

            if check_counter < 5:
                logger.debug(f"定位中, 尝试次数:{check_counter}/20")
            if check_counter >= 5:
                logger.info(f"定位中, 尝试次数:{check_counter}/20")
                if ("dna" not in DeviceShell("dumpsys window | grep mCurrentFocus")) and ("duetnightabyss" not in DeviceShell("dumpsys window | grep mCurrentFocus")) :
                    logger.info("游戏未启动, 尝试启动.")
                    try:
                        restartGame(skipScreenShot = True)
                        Press([1,1])
                    except RestartSignal:
                        pass
                    check_counter = 0
                    continue
            if check_counter >= runtimeContext._MAXRETRYLIMIT:
                logger.error("超过尝试次数, 重启游戏.")
                try:
                    restartGame()
                    Press([1,1])
                except RestartSignal:
                    pass
                check_counter = 0
                continue

        setting._FINISHINGCALLBACK()
        return
    def Farm(set:FarmConfig):
        nonlocal quest
        nonlocal setting # 初始化
        nonlocal runtimeContext
        runtimeContext = RuntimeContext()

        setting = set
        Sleep(1) # 没有等utils初始化完成

        ResetADBDevice()

        QuestFarm()

    return Farm