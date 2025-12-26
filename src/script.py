from ppadb.client import Client as AdbClient
from win10toast import ToastNotifier
from scipy.optimize import curve_fit
from scipy.signal import find_peaks
from enum import Enum
from datetime import datetime
import os
import subprocess
import re
from utils import *
import i18n
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
    "夜航手册": {"30":2, "40":3,"50":4,"55":5, "60":6,"65":7,"70":8,"80":8},
    "魔之楔(不是夜航手册!)": {"40":1, "60": 2, "80":3, "100":4},
    "mod强化": {"60":4, "60(测试)":4},
    "开密函": {"驱离":0, "探险无尽":0, "半自动无巧手":0},
    "钓鱼": {"悠闲":0},
    "迷津": {"默认难度":0},
    # "测试": {"测试":0}
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
        logger.info(i18n.get_text("checking_closing_adb"))
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
        logger.info(i18n.get_text("adb_terminated"))
    except Exception as e:
        logger.error(i18n.get_text("error_terminate_emulator", str(e)))

def KillEmulator(setting : FarmConfig):
    emulator_name = os.path.basename(setting._EMUPATH)
    emulator_SVC = "MuMuVMMSVC.exe"
    try:
        logger.info(i18n.get_text("checking_closing_emulator", emulator_name))
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
        logger.info(i18n.get_text("emulator_terminated", emulator_name))
    except Exception as e:
        logger.error(i18n.get_text("error_terminate_emulator", str(e)))
def StartEmulator(setting):
    hd_player_path = setting._EMUPATH
    if not os.path.exists(hd_player_path):
        logger.error(i18n.get_text("emulator_executable_not_found", hd_player_path))
        return False

    try:
        logger.info(i18n.get_text("starting_emulator", hd_player_path))
        subprocess.Popen(
            hd_player_path,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=os.path.dirname(hd_player_path))
    except Exception as e:
        logger.error(i18n.get_text("error_start_emulator", str(e)))
        return False

    logger.info(i18n.get_text("waiting_emulator_start"))
    time.sleep(15)
def GetADBPath(setting):
    adb_path = setting._EMUPATH
    adb_path = adb_path.replace("HD-Player.exe", "HD-Adb.exe") # 蓝叠
    adb_path = adb_path.replace("MuMuPlayer.exe", "adb.exe") # mumu
    adb_path = adb_path.replace("MuMuNxDevice.exe", "adb.exe") # mumu
    if not os.path.exists(adb_path):
        logger.error(i18n.get_text("adb_not_found", adb_path))
        return None

    return adb_path

def CMDLine(cmd):
    logger.debug(f"cmd line: {cmd}")
    return subprocess.run(cmd,shell=True, capture_output=True, text=True, timeout=10,encoding='utf-8')

def CheckRestartConnectADB(setting: FarmConfig):
    MAXRETRIES = 20

    adb_path = GetADBPath(setting)

    for attempt in range(MAXRETRIES):
        logger.info(i18n.get_text("attempting_connect_adb", attempt + 1, MAXRETRIES))

        if attempt == 3:
            logger.info(i18n.get_text("too_many_failures_close_adb"))
            KillAdb(setting)

            # 我们不起手就关, 但是如果2次链接还是尝试失败, 那就触发一次强制重启.

        try:
            logger.info(i18n.get_text("checking_adb_service"))
            result = CMDLine(f"\"{adb_path}\" devices")
            logger.debug(f"adb链接返回(输出信息):{result.stdout}")
            logger.debug(f"adb链接返回(错误信息):{result.stderr}")

            if ("daemon not running" in result.stderr) or ("offline" in result.stdout):
                logger.info(i18n.get_text("adb_service_not_started"))
                CMDLine(f"\"{adb_path}\" kill-server")
                CMDLine(f"\"{adb_path}\" start-server")
                time.sleep(2)

            logger.debug(i18n.get_text("attempting_connect_adb_debug"))
            result = CMDLine(f"\"{adb_path}\" connect 127.0.0.1:{setting._ADBPORT}")
            logger.debug(f"adb链接返回(输出信息):{result.stdout}")
            logger.debug(f"adb链接返回(错误信息):{result.stderr}")

            if result.returncode == 0 and ("connected" in result.stdout or "already" in result.stdout):
                logger.info(i18n.get_text("connected_emulator"))
                break
            if ("refused" in result.stderr) or ("cannot connect" in result.stdout):
                logger.info(i18n.get_text("emulator_not_running_start"))
                StartEmulator(setting)
                logger.info(i18n.get_text("emulator_started"))
                logger.info(i18n.get_text("attempting_connect_emulator"))
                result = CMDLine(f"\"{adb_path}\" connect 127.0.0.1:{setting._ADBPORT}")
                if result.returncode == 0 and ("connected" in result.stdout or "already" in result.stdout):
                    logger.info(i18n.get_text("connected_emulator"))
                    break
                logger.info(i18n.get_text("cannot_connect_check_port"))

            logger.info(i18n.get_text("connection_failed", result.stderr.strip()))
            time.sleep(2)
            # KillEmulator(setting)
            KillAdb(setting)
            time.sleep(2)
        except Exception as e:
            logger.error(i18n.get_text("error_restart_adb", e))
            time.sleep(2)
            # KillEmulator(setting)
            KillAdb(setting)
            time.sleep(2)
            return None
    else:
        logger.info(i18n.get_text("max_retries_reached"))
        return None

    try:
        client = AdbClient(host="127.0.0.1", port=5037)
        devices = client.devices()

        # 查找匹配的设备
        target_device = f"127.0.0.1:{setting._ADBPORT}"
        for device in devices:
            if device.serial == target_device:
                logger.info(i18n.get_text("got_device_object", device.serial))
                return device
    except Exception as e:
        logger.error(i18n.get_text("error_get_adb_device", e))

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
    def DeviceShellRaw(cmdStr):
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
                if not completed.wait(timeout:=7):
                    # 线程超时未完成
                    logger.warning(i18n.get_text("adb_command_timeout", cmdStr))
                    raise TimeoutError(f"ADB命令在{timeout}秒内未完成")

                if exception is not None:
                    raise exception

                return result
            except (TimeoutError, RuntimeError, ConnectionResetError, cv2.error) as e:
                logger.warning(i18n.get_text("adb_operation_failed", type(e).__name__, e))
                logger.info(i18n.get_text("attempting_restart_adb"))

                ResetADBDevice()
                time.sleep(1)

                continue
            except Exception as e:
                # 非预期异常直接抛出
                logger.error(i18n.get_text("unexpected_adb_exception", type(e).__name__, e))
                raise

    def DeviceShell(cmdStr):
        """
        Wrapper around DeviceShellRaw that randomizes coordinates for input commands.
        Randomizes Press, GoLeft, GoRight, GoForward, GoBack, and DoubleJump by ±2 pixels.
        """
        # Check if this is an input tap or swipe command that should be randomized
        if cmdStr.startswith("input tap "):
            # Parse: input tap x y
            match = re.match(r"input tap (\d+) (\d+)", cmdStr)
            if match:
                x, y = int(match.group(1)), int(match.group(2))
                x_randomized = x + random.randint(-2, 2)
                y_randomized = y + random.randint(-2, 2)
                cmdStr = f"input tap {x_randomized} {y_randomized}"
        
        elif cmdStr.startswith("input swipe "):
            # Parse: input swipe x1 y1 x2 y2 [duration]
            match = re.match(r"input swipe (\d+) (\d+) (\d+) (\d+)(?: (\d+))?", cmdStr)
            if match:
                x1, y1, x2, y2 = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
                duration = match.group(5) if match.group(5) else None
                
                # Randomize all coordinates by ±2 pixels
                x1_randomized = x1 + random.randint(-2, 2)
                y1_randomized = y1 + random.randint(-2, 2)
                x2_randomized = x2 + random.randint(-2, 2)
                y2_randomized = y2 + random.randint(-2, 2)
                
                if duration:
                    cmdStr = f"input swipe {x1_randomized} {y1_randomized} {x2_randomized} {y2_randomized} {duration}"
                else:
                    cmdStr = f"input swipe {x1_randomized} {y1_randomized} {x2_randomized} {y2_randomized}"
        
        # Pass the (possibly modified) command to the raw implementation
        return DeviceShellRaw(cmdStr)

    def Sleep(t=1):
        time.sleep(t)
    def ScreenShot():
        while True:
            try:
                # logger.debug('ScreenShot')
                screenshot = setting._ADBDEVICE.screencap()
                screenshot_np = np.frombuffer(screenshot, dtype=np.uint8)

                if screenshot_np.size == 0:
                    logger.error(i18n.get_text("screenshot_empty"))
                    raise RuntimeError("截图数据为空")

                image = cv2.imdecode(screenshot_np, cv2.IMREAD_COLOR)

                if image is None:
                    logger.error(i18n.get_text("opencv_decode_failed"))
                    raise RuntimeError("图像解码失败")

                if image.shape != (900, 1600, 3):  # OpenCV格式为(高, 宽, 通道)
                    logger.error(i18n.get_text("screenshot_size_abnormal", image.shape))
                    Sleep(5)
                    raise ValueError("截图尺寸异常")

                #cv2.imwrite('screen.png', image)
                return image
            except Exception as e:
                logger.debug(f"{e}")
                if isinstance(e, (AttributeError,RuntimeError, ConnectionResetError, cv2.error)):
                    logger.info(i18n.get_text("adb_restarting"))
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
                    logger.info(i18n.get_text("cv2_exception"))
                    # timestamp = datetime.now().strftime("cv2_%Y%m%d_%H%M%S")  # 格式：20230825_153045
                    # file_path = os.path.join(LOGS_FOLDER_NAME, f"{timestamp}.png")
                    # cv2.imwrite(file_path, ScreenShot())
                    return None

        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if outputMatchResult:
            cv2.imwrite(f"DEBUG_origin_{t}.png", screenshot)
            cv2.rectangle(screenshot, max_loc, (max_loc[0] + template.shape[1], max_loc[1] + template.shape[0]), (0, 255, 0), 2)
            cv2.imwrite(f"DEBUG_matched_{t}.png", screenshot)

        logger.debug(i18n.get_text("found_suspected", shortPathOfTarget, max_val*100))
        if max_val < threshold:
            logger.debug(i18n.get_text("match_below_threshold"))
            return None
        if max_val<=0.9:
            logger.debug(i18n.get_text("match_warning", shortPathOfTarget, threshold*100))
        logger.debug(i18n.get_text("matched_successfully", shortPathOfTarget))
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
        logger.debug(i18n.get_text("found_suspected", shortPathOfTarget, max_val*100))
        if max_val >= threshold:
            if max_val<=0.9:
                logger.debug(i18n.get_text("match_warning", shortPathOfTarget, 80))

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
            logger.debug(i18n.get_text("center_match_check", mean_diff))

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
                                    logger.debug(i18n.get_text("error_invalid_target", p))
                                    setting._FORCESTOPING.set()
                                    return None
                    else:
                        if isinstance(fallback, str):
                            pressTarget(fallback)
                        else:
                            logger.debug(i18n.get_text("error_invalid_target", "None"))
                            setting._FORCESTOPING.set()
                            return None
                Sleep(waitTime) # and wait

            logger.info(i18n.get_text("screenshot_target_not_found_restart", runtimeContext._MAXRETRYLIMIT, targetPattern))
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
            logger.info(i18n.get_text("pre_restart_screenshot_saved", file_path))
        else:
            runtimeContext._CRASHCOUNTER +=1
            logger.info(i18n.get_text("skipped_screenshot"))
            # logger.info(f"跳过了重启前截图.\n崩溃计数器: {runtimeContext._CRASHCOUNTER}\n崩溃计数器超过5次后会重启模拟器.")
            # if runtimeContext._CRASHCOUNTER > 5:
            #     runtimeContext._CRASHCOUNTER = 0
            #     KillEmulator(setting)
            #     CheckRestartConnectADB(setting)

        waittime = 30
        packageList = DeviceShell("pm list packages -3")
        if "com.hero.dna.gf.yun.game" in packageList:
            package_name = "com.hero.dna.gf.yun.game"
            logger.info(i18n.get_text("cloud_game_detected"))
            waittime = 25
        elif "com.panstudio.gplay.duetnightabyss.arpg.global" in packageList:
            package_name = "com.panstudio.gplay.duetnightabyss.arpg.global"
            logger.info(i18n.get_text("global_server_detected"))
            waittime = 40
        elif "com.hero.dna.gf" in packageList:
            package_name = "com.hero.dna.gf" # "com.hero.dna.gf.yun.game"
            logger.info(i18n.get_text("preparing_start_game"))
            waittime = 40
        else:
            logger.info(i18n.get_text("unknown_version_restart_failed"))
            return
        mainAct = DeviceShell(f"cmd package resolve-activity --brief {package_name}").strip().split('\n')[-1]
        DeviceShell(f"am force-stop {package_name}")
        Sleep(2)
        logger.info(i18n.get_text("game_start"))
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
                logger.info(i18n.get_text("task_progress_reset"))
                continue
    ##################################################################
    def ResetPosition():
        logger.info(i18n.get_text("starting_reset"))
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
        # logger.info(f"往左走 剩余{time}")
        SPLIT = 3000
        if time <= SPLIT:
            DeviceShell(f"input swipe 560 550 50 550 {int(1.02*time)}")
        else:
            DeviceShell(f"input swipe 560 550 50 550 {int(1.02*SPLIT)}")
            GoLeft(time-SPLIT)

    def DoubleJump():
        Press([1359,478])
        Sleep(0.5)
        Press([1359,478])

    def GoRight(time = 1000):
        # logger.info(f"往右走 剩余{time}")
        SPLIT = 3000
        if time <= SPLIT:
            DeviceShell(f"input swipe 50 550 560 550 {int(1.02*time)}")
        else:
            DeviceShell(f"input swipe 50 550 560 550 {int(1.02*SPLIT)}")
            GoRight(time-SPLIT)
    def GoForward(time = 1000):
        # logger.info(f"往前走 剩余{time}")
        SPLIT = 3000
        if time <= SPLIT:
            DeviceShell(f"input swipe 500 610 500 400 {int(time*21/20)}")
        else:
            DeviceShell(f"input swipe 500 610 500 400 {int(SPLIT*21/20)}")
            GoForward(time-SPLIT)
    def GoBack(time = 1000):
        # logger.info(f"往后走 剩余{time}")
        SPLIT = 3000
        if time <= SPLIT:
            DeviceShell(f"input swipe 500 400 500 710 {int(time*31/30)}")
        else:
            DeviceShell(f"input swipe 500 400 500 710 {int(SPLIT*31/30)}")
            GoBack(time-SPLIT)
    def Dodge(time = 1):
        for _ in range(time):
            Press([1500,582])
            Sleep(1)
    def QuitDungeon():
        runtimeContext._GAME_COUNTER -= 1 # 因为退出流程后我们会看见再次挑战, 看见再次挑战会加1, 所以我们提前扣掉这一次.
        try:
            FindCoordsOrElseExecuteFallbackAndWait(["任务图标","放弃挑战","放弃挑战_云","再次进行"],['indungeon','indungeon_cloud'],2)
            scn = ScreenShot()
            if CheckIf(scn,"任务图标"):
                logger.info(i18n.get_text("strange_already_exited"))
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
                logger.info(i18n.get_text("e_skill_timer", time.time() - CastESpell.last_cast_time))
            if time.time() - CastESpell.last_cast_time > setting._CAST_E_INTERVAL:
                Press([1086,797])
                CastESpell.last_cast_time = time.time()
    def CastQSpell():
        if not hasattr(CastQSpell, 'last_cast_time'):
            CastQSpell.last_cast_time = 0

        if setting._CAST_Q_ABILITY:
            if time.time() - CastQSpell.last_cast_time > setting._CAST_Q_INTERVAL:
                if setting._CAST_E_PRINT:
                    logger.info(i18n.get_text("q_skill_timer", time.time() - CastQSpell.last_cast_time))
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
                    logger.info(i18n.get_text("doing_nothing_kick"))
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
            logger.debug(i18n.get_text("already_in_dungeon"))
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
        logger.info(i18n.get_text("positioning_result", k))
        if (k >= 0.48) and (k <= 0.52):
            logger.info(i18n.get_text("report_graphics_settings"))
        if k > 0.5:
            return "A"
        else:
            return "B"
    def AUTOCalibration_Y(roi = [[175,89,1277,719]]):
        for _ in range(50):
            pos = CheckIf(ScreenShot(),"保护目标",roi) or CheckIf(ScreenShot(),"撤离点",roi)
            if not pos:
                logger.info(i18n.get_text("auto_calibration_cancelled"))
                return False
            if abs(pos[0]-800) <= 10:
                return True
            DeviceShell(f"input swipe 1200 225 {round((pos[0]-800)/3.5+1200)} 225")
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
                DeviceShell(f"input swipe 1200 225 {delta[0]+1200} {delta[1]+225}")
                Sleep(0.5)
        return False
    ##################################################################
    def BasicQuestSelect():
        if setting._FARM_TYPE == "开密函":
            logger.info(i18n.get_text("error_open_letter_mode"))
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
                logger.info(i18n.get_text("extra_param_farming_target", setting._FARM_EXTRA, mat_elem[select]))
                FindCoordsOrElseExecuteFallbackAndWait(mat_elem[select],[1020+83*select,778],1)
        elif setting._FARM_TYPE == "夜航手册":
            FindCoordsOrElseExecuteFallbackAndWait("前往","夜航手册",1)
            lvl = DUNGEON_TARGETS[setting._FARM_TYPE][setting._FARM_LVL]
            if setting._FARM_LVL != '80':
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
            case "夜航手册40":
                return True
            case "夜航手册55" | "夜航手册60":
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
                    Sleep(0.5)
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
                    Sleep(0.5)
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
                Sleep(0.5)
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
                    Sleep(0.5)
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
                    DeviceShell("input swipe 800 225 1083 225 500")
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
                    
                    DeviceShell("input swipe 800 225 750 225 500")
                    AUTOCalibration_P([736,389],None,[[575,335,264,443]])
                    GoForward(9000)
                    DeviceShell("input swipe 800 225 1300 225 500")
                    AUTOCalibration_P([800,450],None,[[597,213,344,380]])
                    GoForward(2000)
                    if not TryQuickUnlock(5, GoForward, 100):
                        return False
                    Sleep(2)
                    if CheckIf(ScreenShot(),"护送目标前往撤离点"):
                        logger.info("人质已救出!")
                        DeviceShell(f"input swipe 800 225 {1600-1528} 225 500")
                        if not AUTOCalibration_P([865,450]):
                            return False
                        GoForward(5500)
                        Sleep(1)
                        if not AUTOCalibration_P([810,418]):
                            return False
                        CastSpearRush(4)
                        Sleep(1)
                        return finalRoom()

                    DeviceShell("input swipe 800 225 1528 225 500")
                    DeviceShell("input swipe 800 225 1528 225 500")
                    DeviceShell("input swipe 800 225 1100 225 500")
                    if not AUTOCalibration_P([800,450], None,[[567,226,317,409]]):
                        return False
                    GoForward(7000)
                    if not TryQuickUnlock(5, GoForward, 100):
                        return False
                    if CheckIf(ScreenShot(),"护送目标前往撤离点"):
                        logger.info("人质已救出!")
                        DeviceShell("input swipe 800 225 1528 225 500")
                        GoRight(2000)
                        if not AUTOCalibration_P([800,500]):
                            return False
                        CastSpearRush(5)
                        Sleep(1)
                        return finalRoom()

                    GoBack(7000)
                    DeviceShell("input swipe 800 225 1200 225 500")
                    if not AUTOCalibration_P([985,440], None,[[640,241,660,450]]):
                        return False
                    GoForward(7000)
                    DeviceShell("input swipe 800 225 1190 225 500")
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
                        DeviceShell("input swipe 1528 225 600 225 500")
                        AUTOCalibration_P([800,450])
                        GoLeft(2300)
                        GoForward(2000)
                        AUTOCalibration_P([800,595])
                        CastSpearRush(2,True)
                        AUTOCalibration_P([800,595])
                        CastSpearRush(2,True)
                        GoBack(500)
                        DeviceShell("input swipe 1528 225 800 225 500")
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
                    DeviceShell("input swipe 800 225 1107 225 500")
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
            case "迷津默认难度":
                logger.info("不对, 你怎么能运行这个??")
                return True
            case "测试测试":
                
                GoForward(11300)
                GoLeft(500)
                GoLeft(500)
                GoLeft(500)
                GoLeft(500)
                             
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
            logger.info(i18n.get_text("custom_rounds_set", DEFAULTWAVE))
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
            task_name = i18n.to_english(setting._FARM_TYPE) + i18n.to_english(setting._FARM_LVL)
            logger.info(i18n.get_text("default_rounds", task_name, DEFAULTWAVE))

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
                logger.info(i18n.get_text("reconnecting"))
                Sleep(1)
                return True
            return False
        @register()
        def handle_login(scn):
            if Press(CheckIf(scn, "点击进入游戏")) or Press(CheckIf(scn, "点击进入游戏_云")):
                logger.info(i18n.get_text("click_enter_game"))
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
                        logger.info(i18n.get_text("stop_fishing_detected"))
                        return True
                    Press([802,741])
                    if CheckIf(scn, "悠闲钓鱼_无鱼"):
                        logger.info(i18n.get_text("no_fish_detected"))
                        setting._FORCESTOPING.set()
                        return False
                    if (not CheckIfInDungeon(scn)) and (not CheckIf(scn,"悠闲钓鱼_钓到鱼了")) and (not CheckIf(scn,"悠闲钓鱼_新图鉴")):
                        Press([802,741])
                        if quit_counter % 10 == 0:
                            logger.info(i18n.get_text("not_in_fishing_ui", quit_counter // 10))
                        quit_counter +=1
                        Sleep(1)
                    Press(CheckIf(scn,"悠闲钓鱼_收杆"))
                    Press(CheckIf(scn,"悠闲钓鱼_授鱼以鱼"))
                    if (CheckIf(scn,"悠闲钓鱼_钓到鱼了")) or (CheckIf(scn,"悠闲钓鱼_新图鉴")):
                        logger.info(i18n.get_text("caught_fish"))
                        Press([802,741])
                        Sleep(3)
                        counter+=1
                        logger.info(i18n.get_text("caught_fish_stat", counter, time.time()-t), extra={"summary": True})
        @register('normal')
        def handle_dig(scn):
            if CheckIf(scn,"勘察", [[57,279,43,24]]):
                logger.info(i18n.get_text("exploration_task_detected"))
                setting._FORCESTOPING.set()
                return True
            return False
        @register('normal')
        def handle_coop_accept(scn):
            if Press(CheckIf(scn,"多人联机_同意", [[1514,67,64,64]])):
                logger.info(i18n.get_text("coop_request_detected"))
                setting._FORCESTOPING.set()
                return True
            return False
        @register()
        def handle_menu(scn):
            if CheckIf(scn, "任务图标"):
                logger.info(i18n.get_text("quest_menu"))
                Press([63,27])
                Sleep(2)
                return True
            return False
        @register()
        def handle_quest(scn):
            if Press(CheckIf(scn, "历练")):
                logger.info(i18n.get_text("training"))
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
                logger.info(i18n.get_text("level_selection"))
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
                logger.info(i18n.get_text("start_challenge"))
                if setting._GREEN_BOOK or (setting._GREEN_BOOK_FINAL and (runtimeContext._IN_GAME_COUNTER == DEFAULTWAVE)):
                    if setting._GREEN_BOOK:
                        logger.info(i18n.get_text("green_book_used"))
                    if (setting._GREEN_BOOK_FINAL and (runtimeContext._IN_GAME_COUNTER == DEFAULTWAVE)):
                        logger.info(i18n.get_text("green_book_used_final"))
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
                    logger.info(i18n.get_text("monthly_card_collected"))
                    return True
            return False
        @register('normal')
        def handle_countinue_in_game(scn):
            nonlocal runtimeContext
            if (CheckIf(scn, "继续挑战")):
                logger.info(i18n.get_text("round_completed", runtimeContext._IN_GAME_COUNTER))
                if runtimeContext._IN_GAME_COUNTER + 1 <= DEFAULTWAVE:
                    cost_time = time.time()-runtimeContext._START_TIME
                    runtimeContext._TOTAL_TIME = runtimeContext._TOTAL_TIME + cost_time
                    logger.info(i18n.get_text("round_time_stat", cost_time, runtimeContext._TOTAL_TIME))
                    runtimeContext._START_TIME = time.time()

                    runtimeContext._IN_GAME_COUNTER +=1
                    logger.info(i18n.get_text("starting_round", runtimeContext._IN_GAME_COUNTER))
                    while Press(CheckIf(ScreenShot(), "继续挑战")):
                        1
                else:
                    logger.info(i18n.get_text("target_rounds_completed"))
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
                    logger.info(i18n.get_text("round_time_stat", cost_time, runtimeContext._TOTAL_TIME))
                    task_name = i18n.to_english(setting._FARM_TYPE) + i18n.to_english(setting._FARM_LVL)
                    logger.info(i18n.get_text("game_completed_stat", runtimeContext._GAME_COUNTER, task_name, runtimeContext._TOTAL_TIME), extra={"summary": True})
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
                        logger.info(i18n.get_text("unsupported_map"))
                        # SaveDebugImage()
                        QuitDungeon()
                        return True

                if time.time() - runtimeContext._START_TIME > setting._RESTART_INTERVAL:
                    logger.info(i18n.get_text("took_too_long_restart"))
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
                logger.info(i18n.get_text("took_too_long_restart"))
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
                    DeviceShell(f"input swipe 1200 0 1200 800 500")
                    DeviceShell(f"input swipe 1200 450 1200 200 500")
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
                logger.info(i18n.get_text("rogue_runs_completed", runtimeContext._ROUGE_finish_counter), extra={"summary": True})
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
        if setting._FARM_TYPE == "迷津":
            logger.info(i18n.get_text("rogue_mode_used"))
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
                logger.debug(i18n.get_text("positioning_attempt", check_counter))
            if check_counter >= 5:
                logger.info(i18n.get_text("positioning_attempt", check_counter))
                if ("dna" not in DeviceShell("dumpsys window | grep mCurrentFocus")) and ("duetnightabyss" not in DeviceShell("dumpsys window | grep mCurrentFocus")) :
                    logger.info(i18n.get_text("game_not_running_start"))
                    try:
                        restartGame(skipScreenShot = True)
                        Press([1,1])
                    except RestartSignal:
                        pass
                    check_counter = 0
                    continue
            if check_counter >= runtimeContext._MAXRETRYLIMIT:
                logger.error(i18n.get_text("max_attempts_restart"))
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