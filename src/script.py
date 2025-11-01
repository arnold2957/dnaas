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

DUNGEON_TARGETS = BuildQuestReflection()

####################################
CONFIG_VAR_LIST = [
            #var_name,                      type,          config_name,                  default_value
            ["farm_target_text_var",        tk.StringVar,  "_FARMTARGET_TEXT",           list(DUNGEON_TARGETS.keys())[0] if DUNGEON_TARGETS else ""],
            ["farm_target_var",             tk.StringVar,  "_FARMTARGET",                ""],
            ["emu_path_var",                tk.StringVar,  "_EMUPATH",                   ""],
            ["adb_port_var",                tk.StringVar,  "_ADBPORT",                   16384],
            ["last_version",                tk.StringVar,  "LAST_VERSION",               ""],
            ["latest_version",              tk.StringVar,  "LATEST_VERSION",             None],

            ["cast_e_var",                  tk.BooleanVar, "_CAST_E_ABILITY",            True],
            ["cast_intervel_var",           tk.IntVar,     "_CAST_E_INTERVAL",           5],
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
    _TOTALTIME = 0
    _COUNTERDUNG = 0
    _COUNTERCOMBAT = 0
    _COUNTERCHEST = 0
    _TIME_COMBAT= 0
    _TIME_COMBAT_TOTAL = 0
    _TIME_CHEST = 0
    _TIME_CHEST_TOTAL = 0
    #### 其他临时参数
    _MEET_CHEST_OR_COMBAT = False
    _ENOUGH_AOE = False
    _COMBATSPD = False
    _SUICIDE = False # 当有两个人死亡的时候(multipeopledead), 在战斗中尝试自杀.
    _MAXRETRYLIMIT = 20
    _ACTIVESPELLSEQUENCE = None
    _SHOULDAPPLYSPELLSEQUENCE = True
    _RECOVERAFTERREZ = False
    _ZOOMWORLDMAP = False
    _CRASHCOUNTER = 0
    _IMPORTANTINFO = ""
class FarmQuest:
    _DUNGWAITTIMEOUT = 0
    _TARGETINFOLIST = None
    _EOT = None
    _preEOTcheck = None
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
    emulator_headless = "MuMuVMMHeadless.exe"
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
                f"taskkill /f /im {emulator_headless}", 
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
            KillEmulator(setting)
            KillAdb(setting)
            time.sleep(2)
        except Exception as e:
            logger.error(f"重启ADB服务时出错: {e}")
            time.sleep(2)
            KillEmulator(setting)
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

    screenshot[pixels_not_in_roi1_mask] = 0

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

                #cv2.imwrite('screen.png', image)
                return image
            except Exception as e:
                logger.debug(f"{e}")
                if isinstance(e, (AttributeError,RuntimeError, ConnectionResetError, cv2.error)):
                    logger.info("adb重启中...")
                    ResetADBDevice()
    def CheckIf(screenImage, shortPathOfTarget, roi = None, outputMatchResult = False):
        template = LoadTemplateImage(shortPathOfTarget)
        screenshot = screenImage
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
            cv2.imwrite("origin.png", screenshot)
            cv2.rectangle(screenshot, max_loc, (max_loc[0] + template.shape[1], max_loc[1] + template.shape[0]), (0, 255, 0), 2)
            cv2.imwrite("matched.png", screenshot)

        logger.debug(f"搜索到疑似{shortPathOfTarget}, 匹配程度:{max_val*100:.2f}%")
        if max_val < threshold:
            logger.debug("匹配程度不足阈值.")
            return None
        if max_val<=0.9:
            logger.debug(f"警告: {shortPathOfTarget}的匹配程度超过了{threshold*100:.0f}%但不足90%")

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
    def restartGame(skipScreenShot = False):
        nonlocal runtimeContext
        runtimeContext._COMBATSPD = False # 重启会重置2倍速, 所以重置标识符以便重新打开.
        runtimeContext._MAXRETRYLIMIT = min(50, runtimeContext._MAXRETRYLIMIT + 5) # 每次重启后都会增加5次尝试次数, 以避免不同电脑导致的反复重启问题.
        runtimeContext._TIME_CHEST = 0
        runtimeContext._TIME_COMBAT = 0 # 因为重启了, 所以清空战斗和宝箱计时器.
        runtimeContext._ZOOMWORLDMAP = False

        if not skipScreenShot:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # 格式：20230825_153045
            file_path = os.path.join(LOGS_FOLDER_NAME, f"{timestamp}.png")
            cv2.imwrite(file_path, ScreenShot())
            logger.info(f"重启前截图已保存在{file_path}中.")
        else:
            runtimeContext._CRASHCOUNTER +=1
            logger.info(f"跳过了重启前截图.\n崩溃计数器: {runtimeContext._CRASHCOUNTER}\n崩溃计数器超过5次后会重启模拟器.")
            if runtimeContext._CRASHCOUNTER > 5:
                runtimeContext._CRASHCOUNTER = 0
                KillEmulator(setting)
                CheckRestartConnectADB(setting)

        package_name = "jp.co.drecom.wizardry.daphne"
        mainAct = DeviceShell(f"cmd package resolve-activity --brief {package_name}").strip().split('\n')[-1]
        DeviceShell(f"am force-stop {package_name}")
        Sleep(2)
        logger.info("巫术, 启动!")
        logger.debug(DeviceShell(f"am start -n {mainAct}"))
        Sleep(10)
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
        FindCoordsOrElseExecuteFallbackAndWait("放弃挑战",[50,40],1)
        FindCoordsOrElseExecuteFallbackAndWait("其他设置","设置",1)
        FindCoordsOrElseExecuteFallbackAndWait(["复位角色","复位角色_云"],"其他设置",1)
        FindCoordsOrElseExecuteFallbackAndWait("确定",["复位角色","复位角色_云"],1)
        while pos:=CheckIf(ScreenShot(),'确定'):
            Press(pos)
        Sleep(2)
    def GoLeft(time = 1000):
        SPLIT = 3000
        if time <= SPLIT:
            DeviceShell(f"input swipe 143 692 206 692 {time}")
        else:
            DeviceShell(f"input swipe 143 692 206 692 {SPLIT}")
            GoLeft(time-SPLIT)
    def GoRight(time = 1000):
        SPLIT = 3000
        if time <= SPLIT:
            DeviceShell(f"input swipe 339 698 384 698 {time}")
        else:
            DeviceShell(f"input swipe 339 698 384 698 {SPLIT}")
            GoRight(time-SPLIT)
    def GoForward(time = 1000):
        SPLIT = 3000
        if time <= SPLIT:
            DeviceShell(f"input swipe 265 616 265 586 {time}")
        else:
            DeviceShell(f"input swipe 265 616 265 586 {SPLIT}")
            GoForward(time-SPLIT)
    def GoBack(time = 1000):
        SPLIT = 3000
        if time <= SPLIT:
            DeviceShell(f"input swipe 265 774 265 804 {time}")
        else:
            DeviceShell(f"input swipe 265 774 265 804 {SPLIT}")
    def Dodge(time = 1):
        for _ in range(time):
            Press([1518,631])
            Sleep(1)

    def QuitDungeon():
        FindCoordsOrElseExecuteFallbackAndWait("放弃挑战",[50,40],2)
        Press(FindCoordsOrElseExecuteFallbackAndWait("确定","放弃挑战",2))
        Sleep(2)

    def CastESpell(setting):
        if setting._CAST_E_ABILITY:
            Press([1086,797])
            Sleep(setting._CAST_E_INTERVAL)

    ##################################################################
    def QuestFarm():
        nonlocal setting # 强制自动战斗 等等.
        nonlocal runtimeContext
        match setting._FARMTARGET:
            case "驱离":
                counter = 0
                start_time = time.time()
                total_time = 0
                logger.info("开始任务!")
                reset_char_position = False
                while 1:
                    scn = ScreenShot()
                    if Press(CheckIf(scn, "开始挑战")):
                        Sleep(10)
                        continue
                    if Press(CheckIf(scn, "再次进行")) or Press(CheckIf(scn, "继续挑战")):
                        counter+=1
                        cost_time = time.time()-start_time
                        total_time = total_time + cost_time
                        logger.info(f"第{counter}次完成.\n本次用时{cost_time:.2f}秒.\n累计用时{total_time:.2f}秒.", extra={"summary": True})
                        start_time = time.time()
                        Sleep(3)
                        reset_char_position = False
                        continue
                    if time.time() - start_time > 600:
                        logger.info("时间太久了, 重来吧")
                        QuitDungeon()
                        start_time = time.time()
                    
                    if not reset_char_position:
                        ResetPosition()
                        reset_char_position = True

                    CastESpell(setting)

                    if setting._FORCESTOPING.is_set():
                        break
            case "60皎皎币":
                counter = 0
                in_game_counter = 0
                start_time = time.time()
                total_time = 0
                reset_char_position = False
                logger.info("开始任务!")
                   
                while 1:
                    scn = ScreenShot()
                    if Press(CheckIf(scn, "开始挑战")):
                        Sleep(10)
                        continue
                    if pos:=(CheckIf(scn, "继续挑战")):
                        if in_game_counter != 2:
                            logger.info("已完成一小局")
                            Press(pos)
                            in_game_counter +=1
                        else:
                            in_game_counter = 0
                            logger.info("已完成三小局, 撤离")
                            Press(CheckIf(scn, "撤离"))
                            Sleep(2)
                            continue
                    if Press(CheckIf(scn, "再次进行")):
                        counter+=1
                        cost_time = time.time()-start_time
                        total_time = total_time + cost_time
                        logger.info(f"第{counter}次完成.\n本次用时{cost_time:.2f}秒.\n累计用时{total_time:.2f}秒.", extra={"summary": True})
                        start_time = time.time()
                        reset_char_position = False
                        continue
                    
                    if CheckIf(scn,'indungeon',[[0,0,125,125]]):
                        if (not reset_char_position):
                            ResetPosition()
                            Sleep(3)

                            if CheckIf(ScreenShot(), "保护目标", [[1091,353,81,64]]):
                                GoForward(1500)
                                DeviceShell(f"input swipe 800 450 1136 380")
                                GoForward(1500)
                                Press([520,785])
                                Sleep(0.5)
                                Press([1359,478])
                                GoForward(20000)

                                GoLeft(6000)
                                GoForward(25000)

                                reset_char_position = True
                                continue
                            if CheckIf(ScreenShot(), "保护目标", [[793,174,74,86]]):
                                Dodge(3)
                                GoRight(3000)
                                GoForward(16000)
                                GoLeft(2500)
                                GoForward(13000)
                                
                                if CheckIf(ScreenShot(), "保护目标", [[502,262,96,96]]):
                                    GoLeft(4000)
                                    GoForward(30000)
                                    reset_char_position = True
                                    continue
                                if CheckIf(ScreenShot(), "保护目标", [[746,176,98,81]]):
                                    GoForward(32000)
                                    reset_char_position = True
                                    continue

                            QuitDungeon()
                            counter -= 1
                            continue

                        CastESpell(setting)
                    
                    if setting._FORCESTOPING.is_set():
                        break
            case "65mod":
                counter = 0
                in_game_counter = 0
                start_time = time.time()
                total_time = 0
                reset_char_position = False
                logger.info("开始任务!")
                   
                while 1:
                    scn = ScreenShot()
                    if Press(CheckIf(scn, "开始挑战")):
                        Sleep(10)
                        continue
                    if pos:=(CheckIf(scn, "继续挑战")):
                        if in_game_counter != 2:
                            logger.info("已完成一小局")
                            Press(pos)
                            in_game_counter +=1
                        else:
                            in_game_counter = 0
                            logger.info("已完成三小局, 撤离")
                            Press(CheckIf(scn, "撤离"))
                            Sleep(2)
                            continue
                    if Press(CheckIf(scn, "再次进行")):
                        counter+=1
                        cost_time = time.time()-start_time
                        total_time = total_time + cost_time
                        logger.info(f"第{counter}次完成.\n本次用时{cost_time:.2f}秒.\n累计用时{total_time:.2f}秒.", extra={"summary": True})
                        start_time = time.time()
                        reset_char_position = False
                        continue
                    
                    if time.time() - start_time > 3000:
                        logger.info("时间太久了, 重来吧")
                        QuitDungeon()
                        start_time = time.time()
                    
                    if CheckIf(scn,'indungeon',[[0,0,125,125]]):
                        if (not reset_char_position):
                            Sleep(2)
                            GoLeft(8500)
                            GoForward(10300)
                            GoLeft(22500)
                            ResetPosition()
                            reset_char_position = True

                        CastESpell(setting)
                    
                    if setting._FORCESTOPING.is_set():
                        break
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

        quest = LoadQuest(setting._FARMTARGET)
        if quest:
            QuestFarm()
        else:
            setting._FINISHINGCALLBACK()
    return Farm