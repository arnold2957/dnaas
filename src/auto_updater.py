import os
import sys
import json
import hashlib
import threading
from urllib.request import urlopen, Request
from urllib.error import URLError
import subprocess
import time
from tkinter import ttk
import tkinter as tk
import queue
from utils import *


class CancelException(Exception):
    """自定义取消异常"""
    pass

class Progressbar(tk.Toplevel):
    def __init__(self,parent, title="进度", max_size = 1):
        self.canceled = False
        super().__init__(parent)
        self.title(title)
        self.geometry(f"300x100")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
        # 创建进度条
        self.bar = ttk.Progressbar(self, length=300-20, mode="determinate")
        self.bar.pack(pady=20)
        
        self.downloaded_size_var = tk.IntVar(value = "")
        label = ttk.Label(self, textvariable= self.downloaded_size_var)
        label.pack()

        # 最大值
        self.max_size = max_size

    def _on_cancel(self):
        """取消按钮回调函数"""
        self.canceled = True
        self.quit()
        self.destroy()

    def update_progress(self, value):
        """设置进度值并检查取消状态"""
        if self.canceled:
            raise CancelException("用户取消操作")

        percent = round((value / self.max_size) * 100, 2)
        self.bar["value"] = percent

        def short_byte_string(bytes:int):
            if bytes >= 1024*1024*1024:
                return f"{round(bytes/1024/1024/1024,2)} GB"
            if bytes >= 1024*1024:
                return f"{round(bytes/1024/1024,2)} MB"
            if bytes >= 1024:
                return f"{round(bytes/1024,2)} KB"
            return f"{bytes} B"

        self.downloaded_size_var.set(f"{short_byte_string(value)} / {short_byte_string(self.max_size)} ({percent}%)")
        
        if self.canceled:
            raise CancelException("用户取消操作")

class AutoUpdater():
    def __init__(self, msg_queue: queue.Queue, github_user: str, github_repo: str, current_version: str):
        self.github_user = github_user
        self.github_repo = github_repo
        self.current_version = current_version
        self.msg_queue = msg_queue

    def _is_newer_version(self, new_version):
        # 分割版本号
        new_parts = new_version.split('.')[:3]  # 只取前三个部分

        withoutbeta = self.current_version.split('-')[:1][0]  # 只取前三个部分
        current_parts = withoutbeta.split('.')[:3]  # 只取前三个部分
        
        # 确保两个列表都有3个元素（不足的补0）
        while len(new_parts) < 3:
            new_parts.append('0')
        while len(current_parts) < 3:
            current_parts.append('0')
        
        # 逐段比较版本号
        for i in range(3):
            new_num = int(new_parts[i])
            current_num = int(current_parts[i])
            
            if new_num > current_num:
                return True
            elif new_num < current_num:
                return False
        
        return False  # 所有部分都相等

    def check_for_updates(self):
        """执行更新检查逻辑"""
        update_url = f"https://{self.github_user}.github.io/{self.github_repo}/release.json"
        # try:
        #     req = Request(update_url, headers={'Cache-Control': 'no-cache'})
        #     with urlopen(req, timeout=10) as response:
        #         data = json.loads(response.read().decode())
            
        #     if self._is_newer_version(data['version']):
        #         print(f"发现新版本: {data['version']}")
        #         self.update_data = data
        #         self.msg_queue.put(('update_available', data))

        # except (URLError, ValueError, json.JSONDecodeError) as e:
        #     # 发生错误，同样通过队列报告。
        #     error_message = f"检查更新失败: {e}"
        #     # logger.error(error_message) # 暂时把这个关掉 看看是否是多线程问题
        #     # self.msg_queue.put(('error', error_message))

    def download(self):
        try:
            # 创建临时目录
            temp_dir = "__update_temp__"
            os.makedirs(temp_dir, exist_ok=True)
            
            # 下载压缩包
            download_url = self.update_data['download_url']
            archive_name = os.path.basename(download_url)
            archive_path = os.path.join(temp_dir, archive_name)
            
            self._download_bar_and_retry(download_url,archive_path)
            
            # 验证MD5
            if not self._verify_md5(archive_path, self.update_data['md5']):
                self.msg_queue.put(('error', "文件校验失败，请手动更新"))
                return
                
            # 解压到临时目录的子文件夹
            unpack_dir = os.path.join(temp_dir, "unpacked")
            os.makedirs(unpack_dir, exist_ok=True)
            self._extract_archive(archive_path, unpack_dir)
            
            # 生成重启脚本
            restart_script = self._create_restart_script(unpack_dir)
            
            # 发送重启信号.
            self.msg_queue.put(('restart_ready', restart_script))
                
        except Exception as e:
            self.msg_queue.put(('error', f"更新失败: {str(e)}"))
    
    def _download_bar_and_retry(self, download_url, archive_path):
        max_retries = 3
        retry_count = 0
        success = False

        while retry_count <= max_retries and not success:
            try:
                # 打开网络连接
                with urlopen(download_url) as response:
                    # 获取文件总大小（字节）
                    total_size = int(response.headers.get('Content-Length', 0))
                    
                    self.msg_queue.put(('download_started', total_size))
                    
                    # 打开本地文件
                    with open(archive_path, 'wb') as out_file:
                        downloaded = 0
                        # 分块读取数据（每次800KB）
                        while True:
                            chunk = response.read(819200)  # 800KB缓冲区
                            if not chunk:
                                break  # 数据读取完成
                            
                            # 写入本地文件
                            out_file.write(chunk)
                            downloaded += len(chunk)
                            
                            self.msg_queue.put(('progress', downloaded))
                        
                        # 下载完成标记
                        success = True
                self.msg_queue.put(('download_complete', None))
                
            except (URLError, IOError, ConnectionResetError) as e:
                # 网络或IO异常处理
                retry_count += 1
                
                if retry_count > max_retries:
                    # 重试次数耗尽，抛出原始异常
                    raise e
                else:
                    # 显示重试信息
                    print(f"下载中断，正在重试 ({retry_count}/{max_retries})...")
                    time.sleep(2)  # 重试前等待2秒


    def _extract_archive(self, archive_path, target_dir):
        """解压压缩包"""
        if archive_path.lower().endswith('.zip'):
            # 使用Python内置zipfile模块解压
            import zipfile
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(target_dir)
        else:
            raise Exception(f"不支持的压缩格式: {os.path.splitext(archive_path)[1]}")

    def _verify_md5(self, file_path, expected_md5):
        """验证文件MD5哈希值"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest() == expected_md5

    def _create_restart_script(self, unpack_dir):
        """创建重启脚本(跨平台), 并返回启动脚本的路径或指令."""
        if sys.platform == "win32":
            script = f"""@echo off
REM 等待原始程序退出
timeout /t 2 /nobreak >nul

REM 复制解压后的文件到当前目录
xcopy /E /Y /Q "{unpack_dir}\\*" "."

REM 启动新版本程序
start "" "{os.path.basename(sys.argv[0])}"

REM 清理临时文件
rmdir /S /Q "__update_temp__"

REM 删除自身
del "%~f0"
    """
            with open("_update_restart.bat", "w") as f:
                f.write(script)
            return "_update_restart.bat"
        else:  # Linux/macOS
            script = f"""#!/bin/bash
    # 等待原始程序退出
    sleep 2

    # 移动解压后的文件到当前目录
    mv -f "{unpack_dir}"/* .

    # 添加执行权限（如果需要）
    chmod +x "{os.path.basename(sys.argv[0])}"

    # 启动新版本程序
    nohup ./{os.path.basename(sys.argv[0])} >/dev/null 2>&1 &

    # 清理临时文件
    rm -rf "__update_temp__"

    # 删除自身
    rm -- "$0"
    """
            with open("_update_restart.sh", "w") as f:
                f.write(script)
            return "nohup ./_update_restart.sh &"