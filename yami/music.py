"""Root Widget"""

from pathlib import Path
import tkinter as tk
import tempfile
import asyncio
import logging
import json
import tkinter as tk
from tkvideo import tkvideo
import lyricsgenius
import pygame
from mutagen import File, id3
import mutagen
from tkinter import messagebox
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
import customtkinter as ctk
from PIL import Image, ImageDraw
import spotdl
try:
    from stream_server import start_flask_server_thread, stop_flask_server, set_yami_instance
    _flask_server_available = True
except ImportError:
    logging.error("Lỗi import stream_server.")
    _flask_server_available = False
    def start_flask_server_thread(host, port): print("Lỗi: stream_server không khả dụng."); return False
    def stop_flask_server(): print("Lỗi: stream_server không khả dụng.")
    def set_yami_instance(inst): pass

try:
    from dlna_service import start_dlna_service_thread, stop_dlna_service_thread
    _dlna_available = True
except ImportError:
    logging.error("Lỗi import dlna_service.")
    _dlna_available = False
    def start_dlna_service_thread(ip, port): print("Lỗi: dlna_service không khả dụng."); return False
    def stop_dlna_service_thread(): print("Lỗi: dlna_service không khả dụng.")

import shutil
from mutagen.mp3 import MP3
from mutagen.wave import WAVE
import pygame
from pydub import AudioSegment
import os
from lyrics_handler import LyricsHandler
from tkinter import filedialog, simpledialog, messagebox
from topbar import TopBar
from playlist import PlaylistFrame
from control import ControlBar
from cover_art import CoverArtFrame
from progress import BottomFrame
from util import GEOMETRY, TITLE, PlayerState, EVENT_INTERVAL
import logging
import sys 
import vlc
import io
from colorthief import ColorThief
import io
import os
import subprocess
import shlex
import shutil # Để tìm đường dẫn VLC
import os
import sys
import logging # Đảm bảo có logging
# ... các import khác của bạn
import hashlib
import random
import cv2
from PIL import Image
import gc 
import socket
import logging # Đảm bảo logging đã được import
import re

import time
from stream_server import start_flask_server_thread, stop_flask_server, set_yami_instance # (Điều chỉnh đường dẫn import nếu cần)
import threading # Import threading
ctk.set_default_color_theme("yami/yami/data/theme.json")
ctk.set_appearance_mode("dark")

# Cấu hình API Key của Genius
GENIUS_API_KEY = "rtIiUaGp2t7mKDPEWUo2ysQzCJCaRw_fiu2ab5OiNX7l87h8J45P05nV_THbz1sI"
genius = lyricsgenius.Genius(GENIUS_API_KEY)
"""
thanhtieens trình tạm ổn nhuwnos cập nhật sai thời gian (bớt sài cộng dồn ngu lại 
sài cho thông minh lên nào cô bé dễ thương cửa anhr"""
# Thư mục cache lưu lời bài hát
genius.skip_non_songs = True
genius.excluded_terms = ["(Remix)", "(Live)"]
CACHE_DIR = os.path.join(os.getcwd(), "lyrics_cache")
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)
class MusicPlayer(ctk.CTk):
    """ROOT"""


    def __init__(self, loop=None):
        """ROOT INIT"""
        super().__init__()


        # CONFIG
        set_yami_instance(self)
        self.geometry(GEOMETRY)
        self.title(TITLE)

        # STATE (Nhóm các thuộc tính trạng thái ở đây)
        self.playlist = []
        self.STATE = PlayerState.STOPPED
        self.shuffle_enabled = False
        self.current_folder = ""
        self.playlist_index = 0
        self.song_length = 0  # Thời lượng bài hát hiện tại (giây)
        self.start_time = None # Thời điểm bắt đầu phát/tiếp tục (cho audio)
        self.seek_offset = 0   # Thời gian đã phát trước khi seek/pause (cho audio)
        self.is_video_mode = False # Trạng thái đang phát video hay audio
        self.original_state_before_seek = None
        # --- LAN STREAMING STATE (SỬ DỤNG VLC) ---
        self.is_streaming_lan = False
        self.lan_stream_port = 5555 # Cổng mặc định cho VLC stream
        self.vlc_stream_process = None # Lưu tiến trình VLC đang chạy
        self.vlc_executable_path = None # Đường dẫn đến VLC
        self._find_vlc_executable() # Tìm VLC khi khởi động
        self.is_file_serving_mode = False
        self.is_lan_sharing_active = False # Chỉ cần 1 biến trạng thái chung
        self.flask_server_thread = None
        # Gọi set_yami_instance cho stream_server (Flask)
        if _flask_server_available:
             try:
                 set_yami_instance(self)
             except NameError: # Trường hợp import lỗi
                 print("Lỗi khi gọi set_yami_instance")

        # === THÊM CÁC THUỘC TÍNH LYRICS MỚI VÀO ĐÂY ===
        self.current_lyrics_type = None  # Loại lời: 'lrc', 'txt', 'error', None
        self.current_lyrics_data = None  # Dữ liệu lời: list [(giây, dòng)] hoặc string
        self.current_lrc_line_index = -1 # Index dòng LRC đang highlight (-1 là không có)
        # Offset mặc định nếu không có gì được lưu
        self.DEFAULT_GLOBAL_OFFSET = 0.0

        # --- QUẢN LÝ OFFSET ---
        self.song_specific_offsets = {} # Dictionary lưu {audio_stem: offset_value}
        self.current_applied_offset = self.DEFAULT_GLOBAL_OFFSET # Offset đang áp dụng cho bài hát hiện tại
        self.offset_file_path = "song_offsets.json" # Tên file lưu offset
        self.load_offsets() # Tải offset đã lưu khi khởi động
        # =============================================

        self._update_loop_id = None # ID cho vòng lặp cập nhật UI

        # --- Các thiết lập khác ---

        # Kiểm tra hệ điều hành và cấu hình VLC phù hợp
        try:
            if sys.platform.startswith("win"):
                self.vlc_instance = vlc.Instance("--vout=direct3d", "--no-video-title-show", "--quiet")
            elif sys.platform.startswith("linux"):
                # Thêm kiểm tra Wayland/X11 nếu cần thiết cho OpenGL
                self.vlc_instance = vlc.Instance("--no-xlib", "--vout=gl", "--no-video-title-show", "--quiet") # Dùng 'gl' thay vì 'OpenGL'
            elif sys.platform.startswith("darwin"):
                self.vlc_instance = vlc.Instance("--vout=macosx", "--no-video-title-show", "--quiet")
            else:
                self.vlc_instance = vlc.Instance("--no-video-title-show", "--quiet")
            self.mediaplayer = self.vlc_instance.media_player_new()
            logging.info(f"[INIT] Khởi tạo VLC instance và media player thành công.")
        except Exception as vlc_err:
            logging.exception("Lỗi khởi tạo VLC!")
            messagebox.showerror("Lỗi VLC", f"Không thể khởi tạo VLC media player:\n{vlc_err}\nChức năng phát video có thể không hoạt động.")
            self.vlc_instance = None
            self.mediaplayer = None


        # Event loop (Xem xét lại: Có thể không cần nếu dùng threading cho download)
        # self.loop = loop if loop is not None else asyncio.new_event_loop()

        # Spotdl Downloader (Có thể không dùng trực tiếp)
        # self.downloader = spotdl.Downloader(...)
        # spotdl.SpotifyClient.init(...)


        # SETUP PYGAME
        self.initialize_pygame() # Đảm bảo hàm này xử lý lỗi nếu có

        # ICONS
        # Cần chắc chắn đường dẫn icon là đúng và hàm này xử lý lỗi FileNotFoundError
        try:
            self.setup_icons()
            logging.info("[INIT] Setup icons thành công.")
        except FileNotFoundError as icon_err:
             logging.error(f"Lỗi không tìm thấy file icon: {icon_err}")
             messagebox.showwarning("Lỗi Icon", f"Không tìm thấy file icon:\n{icon_err}\nMột số nút có thể thiếu hình ảnh.")
             # Có thể gán icon mặc định hoặc None ở đây
             self.shuffle_icon = None
             self.shuffle_enabled_icon = None
             # ... gán None cho các icon khác ...
        except Exception as icon_setup_err:
             logging.exception("Lỗi không xác định khi setup icons!")
             # Gán None để tránh lỗi khi tạo ControlBar
             self.shuffle_icon = None
             self.shuffle_enabled_icon = None

        self.vlc_log_path = os.path.expanduser("~/yami_vlc_stream.txt") # Ghi log vào file ẩn trong thư mục home
        print(f"VLC stream log sẽ được ghi vào: {self.vlc_log_path}")
        # FRAMES (Khởi tạo các thành phần giao diện)
        try:
            self.topbar = TopBar(self)
            self.playlist_frame = PlaylistFrame(self)
            self.bottom_frame = BottomFrame(self) # Đảm bảo tên lớp đúng
            self.cover_art_frame = CoverArtFrame(self)
            # Khởi tạo LyricsHandler (đảm bảo GENIUS_API_KEY hợp lệ)
            # --- SỬA LẠI DÒNG NÀY ---
            mxlrc_executable_path = "yami/yami/mxlrc" # <-- Thay bằng đường dẫn thật của bạn
            self.lyrics_handler = LyricsHandler(genius_api_key=GENIUS_API_KEY, mxlrc_path=mxlrc_executable_path)
# -------------------------
             # Khởi tạo ControlBar (sau khi có icon)
            self.control_bar = ControlBar(
                parent=self,
                shuffle_icon=getattr(self, 'shuffle_icon', None), # Dùng getattr để an toàn
                shuffle_enabled_icon=getattr(self, 'shuffle_enabled_icon', None)
            )
            logging.info("[INIT] Khởi tạo các Frame và Handler thành công.")
        except Exception as frame_init_err:
             logging.exception("Lỗi nghiêm trọng khi khởi tạo các Frame giao diện!")
             messagebox.showerror("Lỗi Giao Diện", f"Không thể khởi tạo giao diện chính:\n{frame_init_err}")
             self.quit() # Thoát nếu giao diện lỗi nặng
             return # Dừng init


        # Layout configuration
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)


        # WIDGET PLACEMENT
        try:
            self.setup_bindings() # Đặt bindings trước khi grid widgets? (Tùy bạn)
            self.topbar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=(5,0))
            self.cover_art_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
            self.playlist_frame.grid(row=1, column=1, sticky="nsew", padx=10, pady=(10, 0))
            self.control_bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
            self.bottom_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=(0,5))
            logging.info("[INIT] Đặt layout widget thành công.")
        except Exception as grid_err:
             logging.exception("Lỗi khi đặt layout widget!")
             # Có thể không cần thoát ở đây nếu một phần giao diện vẫn hiển thị được


        self.dynamic_theme_enabled = True # Bật/tắt theme động từ ảnh bìa


    def format_time(self, seconds):
        """Helper method to format seconds into MM:SS format."""
        minutes = int(seconds // 60)
        sec = int(seconds % 60)
        return f"{minutes:02d}:{sec:02d}"
    def _check_video_duration(self, retries=10):
        try:
            if self.mediaplayer:
                length_ms = self.mediaplayer.get_length()
                if length_ms > 0:
                    self.song_length = length_ms / 1000
                    print(f"✅ Video length: {self.song_length:.2f} giây")
                    self.bottom_frame.start_progress_bar(self.song_length)
                    self.start_update_loop()
                    return

            if retries > 0:
                print("⏳ Đợi video load để lấy độ dài...")
                self.after(500, lambda: self._check_video_duration(retries - 1))
            else:
                print("⚠️ Không lấy được độ dài video. Dùng mặc định 60s.")
                self.song_length = 60
                self.bottom_frame.start_progress_bar(self.song_length)
                self.start_update_loop()

        except Exception as e:
            logging.error(f"[ERROR] _check_video_duration: {e}")


    def start_update_loop(self):
        if not self._update_loop_id:
            self._update_loop()


    def stop_update_loop(self):
        if self._update_loop_id:
            self.after_cancel(self._update_loop_id)
            self._update_loop_id = None


    def _update_loop(self):
        current_playback_time = -1.0 # Thời gian phát hiện tại (giây)

        if self.STATE == PlayerState.PLAYING:
            # --- Lấy thời gian hiện tại (logic cũ) ---
            if self.is_video_mode:
                if self.mediaplayer and self.mediaplayer.is_playing():
                    current_playback_time = self.mediaplayer.get_time() / 1000.0
                    total_length = self.mediaplayer.get_length() / 1000.0
                else: total_length = 0
            else: # Audio mode
                current_playback_time = self.get_song_position() # Lấy thời gian từ timer/seek
                total_length = self.song_length
            # -----------------------------------------

            # --- Cập nhật thanh tiến trình và label thời gian (logic cũ) ---
            if total_length > 0:
                progress = max(0, min(current_playback_time / total_length, 1))
                try: # Thêm try-except phòng khi widget bị hủy
                    self.bottom_frame.progress_bar.set(progress)
                    self.control_bar.playback_label.configure(
                        text=f"{self.format_time(current_playback_time)} / {self.format_time(total_length)}"
                    )
                except Exception as ui_update_err:
                    # print(f"Lỗi cập nhật progress/label: {ui_update_err}") # Debug nếu cần
                    pass # Bỏ qua lỗi nhỏ khi cập nhật UI
                # --- Tự động chuyển bài (có thể giữ hoặc bỏ comment tùy ý) ---
                if current_playback_time >= total_length - 0.5: # Ngưỡng 0.5s trước khi hết
                    logging.info("[INFO] Media near end. Playing next...")
                    self.play_next_song() # Tạm comment lại
            else:
                try:
                    self.bottom_frame.progress_bar.set(0)
                    self.control_bar.playback_label.configure(text="--:-- / --:--")
                except Exception: pass
            # -----------------------------------------

            # === LOGIC MỚI: XỬ LÝ HIGHLIGHT LRC ===
            if not self.is_video_mode and self.current_lyrics_type == 'lrc' and isinstance(self.current_lyrics_data, list) and current_playback_time >= 0:
                new_line_index = -1
                # Tìm dòng LRC cuối cùng có thời gian (SAU KHI ÁP DỤNG OFFSET) <= thời gian hiện tại
                for i, (raw_line_time, _) in enumerate(self.current_lyrics_data):
                    # Áp dụng offset hiện tại vào thời gian gốc của dòng lời
                    adjusted_line_time = raw_line_time + self.current_applied_offset
                    if adjusted_line_time <= current_playback_time:
                        new_line_index = i
                    else:
                        break # Dừng sớm

                # Chỉ gọi hàm highlight nếu index thực sự thay đổi
                if new_line_index != self.current_lrc_line_index:
                    self.current_lrc_line_index = new_line_index
                    try:
                        self.cover_art_frame.highlight_lyric_line(self.current_lrc_line_index)
                    except AttributeError:
                        # Chỉ log lỗi này một lần để tránh spam
                        if not hasattr(self, '_highlight_func_missing_logged'):
                            logging.error("cover_art_frame chưa có hàm highlight_lyric_line")
                            print("LỖI: cover_art_frame chưa có hàm highlight_lyric_line")
                            self._highlight_func_missing_logged = True # Đánh dấu đã log
                    except Exception as high_err:
                        logging.exception(f"Lỗi khi gọi highlight_lyric_line: {high_err}")
                        print(f"LỖI highlight: {high_err}")
            # =====================================

        elif self.STATE == PlayerState.STOPPED:
            try:
                self.bottom_frame.progress_bar.set(0)
                # Reset highlight khi dừng
                if self.current_lrc_line_index != -1:
                    self.current_lrc_line_index = -1
                    if hasattr(self.cover_art_frame, 'highlight_lyric_line'):
                        self.cover_art_frame.highlight_lyric_line(self.current_lrc_line_index) # Gọi với -1 để bỏ highlight
            except Exception: pass

        # Lặp lại (giữ nguyên)
        # Đảm bảo self._update_loop_id được quản lý đúng bởi start/stop_update_loop
       
        self._update_loop_id = self.after(EVENT_INTERVAL, self._update_loop)
       
    def update_current_offset(self, value):
        """Được gọi bởi command của offset slider."""
        new_offset = round(value, 2) # Làm tròn đến 2 chữ số thập phân
        if new_offset != self.current_applied_offset:
            print(f"Offset slider changed to: {new_offset:.2f}s")
            self.current_applied_offset = new_offset
            # Cần cập nhật lại dòng highlight hiện tại ngay lập tức vì offset đã thay đổi
            # Chạy lại phần tìm index trong _update_loop
            if self.STATE == PlayerState.PLAYING and not self.is_video_mode and self.current_lyrics_type == 'lrc':
                 current_playback_time = self.get_song_position()
                 new_line_index = -1
                 for i, (raw_line_time, _) in enumerate(self.current_lyrics_data):
                      adjusted_line_time = raw_line_time + self.current_applied_offset
                      if adjusted_line_time <= current_playback_time:
                           new_line_index = i
                      else:
                           break
                 if new_line_index != self.current_lrc_line_index:
                      self.current_lrc_line_index = new_line_index
                      try: self.cover_art_frame.highlight_lyric_line(self.current_lrc_line_index)
                      except Exception: pass

    # --- HÀM MỚI ĐỂ LƯU OFFSET CHO BÀI HÁT ---
    def save_current_song_offset(self):
        """Lưu giá trị offset hiện tại cho bài hát đang phát."""
        if not self.playlist or self.STATE == PlayerState.STOPPED or self.playlist_index >= len(self.playlist):
            messagebox.showwarning("Lưu Offset", "Không có bài hát nào đang phát để lưu offset.", parent=self)
            return

        current_song_path = self.playlist[self.playlist_index]
        try:
            audio_stem = Path(current_song_path).stem
            offset_to_save = round(self.current_applied_offset, 2) # Lấy giá trị hiện tại

            self.song_specific_offsets[audio_stem] = offset_to_save
            print(f"Đã cập nhật offset cho '{audio_stem}' thành {offset_to_save:.2f}s trong bộ nhớ.")

            # Lưu toàn bộ dictionary vào file
            self.save_offsets()
            messagebox.showinfo("Lưu Offset", f"Đã lưu offset {offset_to_save:.2f}s cho bài hát này.", parent=self)

        except Exception as e:
            logging.error(f"Lỗi khi lấy stem hoặc lưu offset cho '{current_song_path}': {e}")
            messagebox.showerror("Lỗi Lưu Offset", f"Không thể lưu offset:\n{e}", parent=self)


    def on_closing(self):
         """Xử lý các tác vụ trước khi đóng ứng dụng."""
         print("Closing application...")
         # DỪNG VLC STREAM NẾU ĐANG CHẠY
         self._stop_vlc_stream()
         if _flask_server_available: stop_flask_server()
         if _dlna_available: stop_dlna_service_thread()
         # --- XÓA HOẶC COMMENT OUT VIỆC DỪNG FLASK SERVER ---
         # if hasattr(self, 'is_streaming_lan') and self.is_streaming_lan and hasattr(self, 'stream_server'):
         #     if self.stream_server: self.stream_server.stop() # Bỏ dòng này
         # -------------------------------------------------
         self.stop_event_checker()
         self.stop_update_loop()
         self.save_offsets()
         try:
            if pygame.mixer.get_init():
                 pygame.mixer.music.stop()
            if self.mediaplayer: # Dừng VLC player cục bộ
                 self.stop_video() # Hàm này nên có
         except Exception as close_err:
              print(f"Lỗi khi dọn dẹp trước khi đóng: {close_err}")
         self.destroy()
    def get_audio_length(self, path):
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == ".mp3":
                # Cần import: from mutagen.mp3 import MP3
                audio = MP3(path)
            elif ext == ".wav":
                # Cần import: from mutagen.wave import WAVE
                audio = WAVE(path)
            else:
                return 0
            # Kiểm tra xem audio.info có tồn tại không
            if audio and audio.info:
                 return audio.info.length
            else:
                 logging.warning(f"Không tìm thấy 'info' cho file: {path}")
                 return 0
        except Exception as e:
            # Cần import: import logging
            logging.warning(f"Không thể lấy độ dài file '{os.path.basename(path)}': {e}")
            return 0


    def _start_timer_and_update_loop(self):
        """Đặt lại timer và offset khi bắt đầu phát audio."""
        self.start_time = time.time()
        self.seek_offset = 0
        # Thêm print ở đây
        
        # Gọi hàm kiểm tra và bắt đầu vòng lặp (giữ nguyên)
        self.wait_until_loaded_and_update()

    def _get_local_ip(self):
        """Lấy địa chỉ IP LAN của máy."""
        s = None
        try:
            # Tạo socket UDP (không cần kết nối thực sự)
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1) # Thử thêm option broadcast
            # Kết nối đến một địa chỉ IP công cộng (không gửi dữ liệu)
            # Điều này giúp hệ điều hành chọn interface mạng phù hợp nhất
            s.connect(("8.8.8.8", 80)) # Dùng IP DNS Google
            ip_address = s.getsockname()[0]
            logging.info(f"Lấy được IP LAN qua socket connect: {ip_address}")
            # Kiểm tra lại lần nữa nếu là loopback (ít khả năng sau khi connect ra ngoài)
            if ip_address.startswith("127."):
                 logging.warning("IP nhận được vẫn là loopback sau khi connect. Thử cách khác...")
                 raise socket.error("IP is loopback") # Gây lỗi để nhảy xuống fallback
            return ip_address
        except socket.error as e:
            logging.warning(f"Không thể lấy IP qua socket connect: {e}. Thử lấy bằng hostname...")
            # Fallback: Thử lấy bằng hostname
            try:
                hostname = socket.gethostname()
                # Lấy tất cả IP liên kết với hostname
                ip_list = socket.getaddrinfo(hostname, None, socket.AF_INET)
                # Tìm IP không phải loopback đầu tiên
                for item in ip_list:
                    ip_address = item[4][0] # Lấy địa chỉ IP từ tuple
                    if not ip_address.startswith("127."):
                         logging.info(f"Lấy được IP LAN qua hostname/getaddrinfo: {ip_address}")
                         return ip_address
                # Nếu duyệt hết mà chỉ có loopback
                logging.warning(f"Chỉ tìm thấy IP loopback từ hostname: {hostname}")
                return None
            except socket.gaierror as e_host:
                logging.error(f"Lỗi khi lấy IP bằng hostname/getaddrinfo: {e_host}")
                return None
            except Exception as e_host_generic:
                logging.error(f"Lỗi không xác định khi lấy IP bằng hostname: {e_host_generic}")
                return None
        except Exception as e_generic:
             logging.error(f"Lỗi không xác định khi lấy IP: {e_generic}")
             return None
        finally:
            if s:
                s.close()
    # Trong class MusicPlayer(ctk.CTk): của music.py
    def get_path_from_playlist(self, index):
        """Trả về đường dẫn đầy đủ của file tại index trong playlist."""
        if self.playlist and 0 <= index < len(self.playlist):
            return self.playlist[index]
        else:
            logging.warning(f"get_path_from_playlist: Invalid index {index} requested.")
            return None
    def get_song_position(self):
        """Tính toán vị trí phát hiện tại của audio (Pygame)."""
        current_real_time = time.time() # Lấy thời gian hiện tại một lần
        # In ra các giá trị để debug
        # Dùng getattr để tránh lỗi nếu thuộc tính chưa tồn tại
        state = getattr(self, 'STATE', 'Unknown')
        start_time = getattr(self, 'start_time', None)
        seek_offset = getattr(self, 'seek_offset', 0.0)
        #print(f"DEBUG get_pos: State={state}, start_time={start_time}, seek_offset={seek_offset:.2f}, now={current_real_time:.2f}")

        if state == PlayerState.PLAYING and start_time is not None:
            calculated_pos = seek_offset + (current_real_time - start_time)
            #print(f"DEBUG get_pos: Calculated = {calculated_pos:.2f}")
            # Đảm bảo không trả về giá trị âm hoặc lớn hơn thời lượng bài hát (nếu có thể)
            # return max(0, calculated_pos)
            return calculated_pos # Trả về giá trị tính được
        # print(f"DEBUG get_pos: Returning offset = {seek_offset:.2f}") # Bỏ comment nếu cần xem khi không playing
        return seek_offset


    def start_seek_drag(self, event):
        """Gọi khi nhấn chuột xuống thanh progress bar."""
        print("DEBUG: start_seek_drag triggered")
        # Chỉ xử lý nếu có nhạc
        if not self.playlist or self.STATE == PlayerState.STOPPED:
            self.original_state_before_seek = None # Đảm bảo reset
            return

        # Lưu trạng thái gốc
        self.original_state_before_seek = self.STATE

        # Nếu đang phát, tạm dừng
        if self.STATE == PlayerState.PLAYING:
            print("DEBUG: Pausing for seek drag...")
            try:
                if self.is_video_mode:
                    if self.mediaplayer: self.mediaplayer.pause()
                else:
                    pygame.mixer.music.pause()
                self.STATE = PlayerState.PAUSED
                # Cập nhật nút play/pause trên UI nếu cần (tùy chọn)
                # self.control_bar.update_play_button(self.STATE)
                # Dừng vòng lặp update UI tạm thời khi pause để tua
                self.stop_update_loop()
                # Cập nhật seek_offset khi pause
                if not self.is_video_mode:
                     current_pos = self.get_song_position() # Lấy vị trí trước khi pause hoàn toàn
                     self.seek_offset = current_pos
                     self.start_time = None # Reset start time khi pause
                     print(f"DEBUG: Paused. seek_offset={self.seek_offset:.2f}, start_time=None")
            except Exception as e:
                logging.error(f"Lỗi khi tạm dừng để tua: {e}")
                self.original_state_before_seek = None # Reset nếu có lỗi
                return # Không tiếp tục nếu không pause được

        # Thực hiện tua đến vị trí nhấn chuột ban đầu
        self.seek_on_click_or_drag(event)

    def seek_on_click_or_drag(self, event):
        """
        Gọi khi nhấn hoặc kéo chuột trên thanh progress bar.
        CHỈ cập nhật vị trí và UI, KHÔNG thay đổi trạng thái play/pause.
        """
        # Chỉ xử lý nếu có nhạc và không phải đang STOPPED
        # (Không cần kiểm tra original_state_before_seek ở đây vì hàm này cũng đc gọi bởi Button-1)
        if not self.playlist or self.STATE == PlayerState.STOPPED:
            return

        progress_bar_widget = self.bottom_frame.progress_bar
        try:
            if not progress_bar_widget.winfo_exists(): return
            progress_bar_width = progress_bar_widget.winfo_width()
            if progress_bar_width <= 0: return

            click_x = event.x
            click_x = max(0, min(click_x, progress_bar_width))
            new_position_ratio = click_x / progress_bar_width

            # Gọi hàm logic tua thực tế (_perform_seek không đổi)
            # Hàm này chỉ set vị trí và cập nhật UI tức thời
            self._perform_seek(new_position_ratio)

        except Exception as e:
            logging.error(f"Lỗi trong seek_on_click_or_drag: {e}")

    def end_seek_drag(self, event):
        """Gọi khi nhả chuột ra khỏi thanh progress bar."""
        print("DEBUG: end_seek_drag triggered")
        # Nếu trước đó đã lưu trạng thái (tức là đã nhấn thành công)
        if self.original_state_before_seek is not None:
            # Nếu trạng thái gốc là PLAYING, thì phát lại
            if self.original_state_before_seek == PlayerState.PLAYING:
                print("DEBUG: Resuming after seek drag...")
                try:
                    if self.is_video_mode:
                        if self.mediaplayer: self.mediaplayer.play()
                    else:
                        # Vị trí đã được set bởi _perform_seek, chỉ cần unpause
                        pygame.mixer.music.unpause()
                        # Reset start_time để tính tiếp từ vị trí mới
                        self.start_time = time.time()
                        print(f"DEBUG: Resumed. seek_offset={self.seek_offset:.2f}, start_time={self.start_time:.2f}")

                    self.STATE = PlayerState.PLAYING
                    # Cập nhật lại nút play/pause trên UI nếu cần
                    # self.control_bar.update_play_button(self.STATE)
                    # Khởi động lại vòng lặp update UI
                    self.start_update_loop()
                except Exception as e:
                    logging.error(f"Lỗi khi phát lại sau khi tua: {e}")
                    # Nếu lỗi resume, có thể cần đặt lại state hoặc xử lý khác
                    self.STATE = PlayerState.PAUSED # Giữ state paused nếu resume lỗi
            # else: Trạng thái gốc là PAUSED hoặc STOPPED, không cần làm gì thêm

            # Reset trạng thái gốc đã lưu
            self.original_state_before_seek = None


    # Hàm _perform_seek giữ nguyên logic set vị trí và cập nhật UI tức thời
    def _perform_seek(self, new_position_ratio):
        """Thực hiện việc tua đến tỉ lệ vị trí đã cho (KHÔNG đổi trạng thái play/pause)."""
        if self.is_video_mode:
            # ... (logic set_time cho VLC, cập nhật UI) ...
            if self.mediaplayer and self.mediaplayer.is_playable():
                total_length_ms = self.mediaplayer.get_length()
                if total_length_ms > 0:
                     total_length_sec = total_length_ms / 1000.0
                     new_time_sec = new_position_ratio * total_length_sec
                     new_time_ms = int(new_time_sec * 1000)
                     self.mediaplayer.set_time(new_time_ms)
                     # Cập nhật UI ngay
                     self.bottom_frame.progress_bar.set(new_position_ratio)
                     self.control_bar.playback_label.configure(
                         text=f"{self.format_time(new_time_sec)} / {self.format_time(total_length_sec)}"
                     )
        else: # Audio mode
            if self.song_length > 0:
                new_position_sec = new_position_ratio * self.song_length
                try:
                    # Cập nhật seek_offset ngay khi tua (quan trọng khi đang PAUSED)
                    self.seek_offset = new_position_sec
                    # Chỉ gọi set_pos nếu mixer còn hoạt động
                    if pygame.mixer.get_init(): # Kiểm tra mixer đã init chưa
                       pygame.mixer.music.set_pos(new_position_sec)

                    # Cập nhật UI ngay lập tức
                    self.bottom_frame.progress_bar.set(new_position_ratio)
                    self.control_bar.playback_label.configure(
                       text=f"{self.format_time(new_position_sec)} / {self.format_time(self.song_length)}"
                    )
                    # Cập nhật highlight LRC ngay cả khi đang kéo (nếu đang PAUSED)
                    if self.current_lyrics_type == 'lrc':
                        new_line_index = -1
                        for i, (line_time, _) in enumerate(self.current_lyrics_data):
                            if line_time <= new_position_sec: new_line_index = i
                            else: break
                        if new_line_index != self.current_lrc_line_index:
                            self.current_lrc_line_index = new_line_index
                            try: self.cover_art_frame.highlight_lyric_line(self.current_lrc_line_index)
                            except Exception as high_err: logging.error(f"Lỗi highlight khi kéo seek: {high_err}")

                except pygame.error as seek_err:
                    logging.error(f"Lỗi pygame khi seek trong _perform_seek: {seek_err}")
            # else: song_length is 0


    def _find_vlc_executable(self):
        """Tìm đường dẫn thực thi của VLC."""
        self.vlc_executable_path = shutil.which('vlc')
        if not self.vlc_executable_path:
            # Thử một số đường dẫn mặc định khác nếu cần (tùy HĐH)
            if sys.platform.startswith("win"):
                # Thử tìm trong Program Files
                possible_paths = [
                    os.path.join(os.environ.get("ProgramFiles", ""), "VideoLAN", "VLC", "vlc.exe"),
                    os.path.join(os.environ.get("ProgramFiles(x86)", ""), "VideoLAN", "VLC", "vlc.exe")
                ]
                for path in possible_paths:
                    if os.path.exists(path):
                        self.vlc_executable_path = path
                        break
            # elif sys.platform.startswith("darwin"): # macOS
            #     possible_path = "/Applications/VLC.app/Contents/MacOS/VLC"
            #     if os.path.exists(possible_path):
            #          self.vlc_executable_path = possible_path

        if self.vlc_executable_path:
            logging.info(f"Tìm thấy VLC tại: {self.vlc_executable_path}")
        else:
            logging.warning("Không tìm thấy VLC executable. Chức năng stream LAN sẽ không hoạt động.")
            messagebox.showwarning("Thiếu VLC", "Không tìm thấy VLC Media Player.\nVui lòng cài đặt VLC để sử dụng chức năng stream qua LAN.", parent=self)

    def _stop_vlc_stream(self):
        """Dừng tiến trình VLC streaming đang chạy (nếu có)."""
        if self.vlc_stream_process and self.vlc_stream_process.poll() is None:
            logging.info(f"Đang dừng tiến trình VLC streaming (PID: {self.vlc_stream_process.pid})...")
            try:
                self.vlc_stream_process.terminate()
                self.vlc_stream_process.wait(timeout=2) # Chờ tối đa 2 giây
                logging.info("Đã dừng tiến trình VLC streaming.")
            except subprocess.TimeoutExpired:
                logging.warning("Tiến trình VLC không dừng kịp thời, đang buộc dừng (kill)...")
                self.vlc_stream_process.kill() # Buộc dừng nếu terminate không hiệu quả
                logging.warning("Đã buộc dừng tiến trình VLC.")
            except Exception as e:
                logging.error(f"Lỗi khi dừng tiến trình VLC: {e}")
        self.vlc_stream_process = None # Đặt lại thành None

    def toggle_lan_sharing(self):
        """Bật/Tắt đồng thời DLNA services và Flask file server."""

        # --- Cấu hình cổng ---
        flask_media_port = 8080        # Cổng phục vụ file media
        dlna_description_port = 8081   # Cổng phục vụ mô tả DLNA (phải khác)

        # --- Kiểm tra thư viện có sẵn không ---
        if not _flask_server_available or not _dlna_available:
            messagebox.showerror("Lỗi", "Một hoặc cả hai thành phần stream (Flask/DLNA) không khả dụng do lỗi import.", parent=self)
            return

        if not self.is_lan_sharing_active:
            # --- Bật LAN Sharing ---
            print("Đang bật LAN Sharing (DLNA + File Server)...")
            logging.info("Enabling LAN Sharing...")

            local_ip = self._get_local_ip()
            if not local_ip:
                messagebox.showerror("Lỗi Mạng", "Không thể xác định IP LAN.", parent=self)
                logging.error("Failed to get local IP for LAN Sharing.")
                return

            # 1. Khởi động Flask File Server (nếu chưa chạy)
            flask_started = False
            if self.flask_server_thread and self.flask_server_thread.is_alive():
                print("Flask server đã chạy.")
                flask_started = True
            else:
                print("Khởi động luồng Flask server...")
                self.flask_server_thread = threading.Thread(target=start_flask_server_thread, args=('0.0.0.0', flask_media_port), daemon=True)
                self.flask_server_thread.start()
                time.sleep(1.0) # Chờ server khởi động
                if self.flask_server_thread.is_alive():
                    flask_started = True
                else:
                    print("LỖI: Không khởi động được luồng Flask server!")
                    messagebox.showerror("Lỗi Server", "Không thể khởi động máy chủ HTTP phục vụ file.", parent=self)
                    # Không tiếp tục nếu Flask lỗi

            # 2. Khởi động DLNA Services (nếu Flask đã chạy)
            dlna_started = False
            if flask_started:
                print("Khởi động luồng DLNA services...")
                dlna_started = start_dlna_service_thread(local_ip, dlna_description_port)
                if not dlna_started:
                    messagebox.showerror("Lỗi DLNA", "Không thể khởi động dịch vụ DLNA. Kiểm tra console/log.", parent=self)
                    # Cân nhắc dừng Flask nếu DLNA lỗi? (Tùy logic bạn muốn)
                    # stop_flask_server()
                    # self.flask_server_thread = None
            else:
                print("Bỏ qua khởi động DLNA vì Flask server lỗi.")


            # 3. Cập nhật trạng thái cuối cùng
            if flask_started and dlna_started:
                self.is_lan_sharing_active = True
                display_text = f"LAN Sharing ON (DLNA + HTTP:{flask_media_port})"
                self.control_bar.show_notification(display_text)
                print(display_text)
                print(f"   DLNA clients should detect 'Yami Media Server'.")
                print(f"   Media file access via DLNA will use URLs like http://{local_ip}:{flask_media_port}/file?...")
                # Cập nhật UI nút
                if hasattr(self.topbar, 'update_lan_sharing_button_state'): # Dùng tên hàm mới cho nút
                     self.topbar.update_lan_sharing_button_state(True)
            else:
                 # Nếu một trong hai không khởi động được, coi như thất bại
                 print("Không thể bật đầy đủ LAN Sharing do lỗi ở một thành phần.")
                 self.is_lan_sharing_active = False
                 # Đảm bảo dừng các thành phần đã lỡ chạy
                 stop_dlna_service_thread()
                 stop_flask_server()
                 self.flask_server_thread = None # Reset thread


        else:
            # --- Tắt LAN Sharing ---
            print("Đang tắt LAN Sharing (DLNA + File Server)...")
            logging.info("Disabling LAN Sharing...")

            # 1. Dừng DLNA Services
            stop_dlna_service_thread()

            # 2. Dừng Flask File Server
            stop_flask_server()
            self.flask_server_thread = None # Reset thread

            self.is_lan_sharing_active = False
            self.control_bar.show_notification("LAN Sharing OFF")
            print("LAN Sharing Disabled.")
            # Cập nhật UI nút
            if hasattr(self.topbar, 'update_lan_sharing_button_state'):
                 self.topbar.update_lan_sharing_button_state(False)

    def apply_theme_from_cover(self, pil_image, steps=10, delay=30):
        if not self.dynamic_theme_enabled:
            return

        palette = get_theme_palette(pil_image)
        dominant_rgb = palette[0]
        accent_rgb = palette[1] if len(palette) > 1 else palette[0]
        bg_rgb = palette[2] if len(palette) > 2 else dominant_rgb

        target_colors = {
            "dominant": dominant_rgb,
            "accent": accent_rgb,
            "bg": bg_rgb,
        }

        if not hasattr(self, "_theme_current_colors"):
            self._theme_current_colors = {
                "dominant": dominant_rgb,
                "accent": accent_rgb,
                "bg": bg_rgb,
            }

        def fade_step(step):
            t = step / steps
            interpolated = {
                key: tuple(
                    int(self._theme_current_colors[key][i] + (target_colors[key][i] - self._theme_current_colors[key][i]) * t)
                    for i in range(3)
                )
                for key in target_colors
            }

            dom_hex = rgb_to_hex(interpolated["dominant"])
            acc_rgb = interpolated["accent"]
            bg_hex = rgb_to_hex(interpolated["bg"])
            brightness = sum(interpolated["dominant"]) / 3
            text_color = "white" if brightness < 128 else "black"

            # Tăng độ sáng nhưng giữ lại màu sắc
            acc_brightness = sum(acc_rgb) / 3
            lighten = 0.5 if acc_brightness < 100 else 0.3
            
            acc_hex = rgb_to_hex(interpolated["accent"])

            try:
                # Main frames
                self.cover_art_frame.configure(
                    fg_color=dom_hex,      # Viền ngoài hoặc nền khung
                    border_color=dom_hex,
                    border_width=2,
                    corner_radius=10
                )
                self.control_bar.configure(fg_color=dom_hex)
                self.bottom_frame.configure(fg_color=bg_hex)

                self.control_bar.volume_slider.configure(button_color=acc_hex, progress_color=bg_hex)
                self.bottom_frame.progress_bar.configure(progress_color=bg_hex)
                # Labels

                self.control_bar.music_title_label.configure(
                    fg_color=bg_hex,
                    text_color=text_color
                )

                self.control_bar.playback_label.configure(
                    fg_color=bg_hex,
                    text_color=text_color
                )


                # Playlist
                self.playlist_frame.song_list.configure(
                    bg=bg_hex,
                    fg=text_color,
                    selectbackground=dom_hex,
                    selectforeground=text_color
                )
                self.playlist_frame.scrollbar.configure(
                    button_color=acc_hex,
                    
                )

                # Cover + lyrics
                # Cover Art image section
                self.cover_art_frame.mp3_cover_art_label.configure(
                    fg_color=dom_hex
                )

                # Lyrics textbox
                self.cover_art_frame.lyrics_textbox.configure(
                    fg_color=bg_hex,
                    text_color=text_color
                )
                # Playback buttons (play, next, prev, shuffle)
                self.control_bar.play_button.configure(
                    fg_color=bg_hex,
                    hover_color=acc_hex,
                    text_color=text_color
                )

                self.control_bar.next_button.configure(
                    fg_color=bg_hex,
                    hover_color=acc_hex,
                    text_color=text_color
                )

                self.control_bar.prev_button.configure(
                    fg_color=bg_hex,
                    hover_color=acc_hex,
                    text_color=text_color
                )

                self.control_bar.shuffle_button.configure(
                    fg_color=bg_hex,
                    hover_color=acc_hex,
                    text_color=text_color
                )


            except Exception as e:
                print("❌ Fade error:", e)

            if step < steps:
                self.after(delay, lambda: fade_step(step + 1))
            else:
                self._theme_current_colors = target_colors

        fade_step(0)


    def load_offsets(self):
        """Tải các offset đã lưu cho từng bài hát từ file JSON."""
        if os.path.exists(self.offset_file_path):
            try:
                with open(self.offset_file_path, 'r', encoding='utf-8') as f:
                    self.song_specific_offsets = json.load(f)
                print(f"Đã tải {len(self.song_specific_offsets)} offset riêng từ {self.offset_file_path}")
            except (json.JSONDecodeError, IOError) as e:
                print(f"Lỗi khi tải file offset '{self.offset_file_path}': {e}. Sử dụng dictionary rỗng.")
                self.song_specific_offsets = {}
        else:
            print("Không tìm thấy file offset, sử dụng dictionary rỗng.")
            self.song_specific_offsets = {}

    def save_offsets(self):
        """Lưu dictionary offset riêng của bài hát vào file JSON."""
        try:
            with open(self.offset_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.song_specific_offsets, f, ensure_ascii=False, indent=4)
            print(f"Đã lưu offset vào {self.offset_file_path}")
        except IOError as e:
            print(f"Lỗi khi lưu file offset '{self.offset_file_path}': {e}")

    def convert_to_mp3(song_path):
        """
        Chuyển đổi file nhạc sang định dạng MP3 nếu không phải MP3.
        """
        mp3_path = song_path.rsplit(".", 1)[0] + ".mp3"  # Đổi đuôi thành .mp3

        if os.path.exists(mp3_path):
            return mp3_path  # Nếu file đã tồn tại, không cần chuyển đổi

        try:
            audio = AudioSegment.from_file(song_path)
            audio.export(mp3_path, format="mp3", bitrate="192k")  # Chuyển sang MP3
            return mp3_path
        except Exception as e:
            print(f"Lỗi khi chuyển đổi {song_path} sang MP3: {e}")
            return None  # Trả về None nếu lỗi
    def clean_title(title: str) -> str:
        addon = None

        # Tìm tất cả đoạn trong ngoặc
        pattern = r"[\(\[].*?(?:[\)\]]|$)"
        matches = re.findall(pattern, title)

        for match in matches:
            lower = match.lower()
            if "lofi chill" in lower:
                addon = "Lofi Chill"
                break
            elif "lofi" in lower:
                addon = "Lofi"
                break
            elif "remix" in lower:
                addon = "Remix"
                break

        # Xoá toàn bộ đoạn ngoặc
        title = re.sub(pattern, "", title).strip()

        # Gắn thêm phần addon (nếu có)
        if addon:
            title = f"{title} {addon}"

        # Dọn khoảng trắng dư
        title = re.sub(r"\s{2,}", " ", title).strip()
        return title

        
    def get_metadata(self,song_path):
        """Lấy title và artist từ metadata (nếu có)."""
        try:
            audio = mutagen.File(song_path, easy=True)
            if not audio:
                return None, None

            title = audio.get('title', [None])[0]
            artist = audio.get('artist', [None])[0]

            return title, artist
        except Exception as e:
            logging.error(f"Lỗi khi đọc metadata: {e}")
            return None, None
    def get_lyrics(self, song_title, artist, attempt=0, tried_shorter_title=False):

        MAX_ATTEMPTS = 5  # Giới hạn số lần thử để tránh vòng lặp vô tận
        try:
            # Bỏ nội dung trong dấu [] và () nhưng giữ từ "remix", "lofi" trong dấu ngoặc
            song_title = re.sub(r"\[(?!.*(remix|lofi)).*?\]", "", song_title).strip()
            song_title = re.sub(r"\((?!.*(remix|lofi)).*?\)", "", song_title).strip()
            # Tách tiêu đề nếu có dấu "-" và thử tìm kiếm từng phần
            if "-" in song_title and not tried_shorter_title:
                title_parts = song_title.split("-")
                for part in title_parts:
                    part = part.strip()
                    logging.info(f"Thử tìm kiếm với phần: {part}")
                    result = self.get_lyrics(part, artist, attempt + 1, tried_shorter_title=True)
                    if "Không tìm thấy" not in result:
                        return result
            song_title_cleaned = song_title.split("feat.")[0].strip()
            if song_title_cleaned.lower().startswith("anh trai say hi"):
                song_title_cleaned = song_title_cleaned.replace("Anh Trai Say Hi", "").strip()
            cache_key = hashlib.md5(f"{song_title_cleaned}_{artist}".encode('utf-8')).hexdigest()
            cache_path = os.path.join(CACHE_DIR, f"{cache_key}.txt")
            if os.path.exists(cache_path):
                with open(cache_path, 'r', encoding='utf-8') as cache_file:
                    cached_lyrics = cache_file.read()
                logging.info("Lấy lời bài hát từ cache.")
                return cached_lyrics
            logging.info(f"Đang tìm kiếm: {song_title_cleaned} - {artist}")
            song = genius.search_song(song_title_cleaned, artist)
            if not song:
                logging.info(f"Không tìm thấy '{song_title_cleaned}', thử tìm kiếm không có nghệ sĩ hợp tác.")
                song = genius.search_song(song_title_cleaned)
            if not song:
                logging.info("Không tìm thấy bài hát chính xác, thử tìm kiếm 10 bài hát gần giống...")

                results = genius.search(song_title_cleaned)

                songs = results['hits'][:10]
                best_song = None
                max_views = -1
                for s in songs:
                    song_result = s['result']
                    song_title_api = song_result['title']
                    if song_result["stats"].get("pageviews", 0) > max_views:
                        max_views = song_result["stats"].get("pageviews", 0)
                        best_song = song_result
                if best_song:
                    logging.info(f"Tìm thấy bài hát có lượt xem cao nhất: {best_song['title']}")
                    song = genius.search_song(best_song['title'])
            if not song:
                logging.error("Không tìm thấy bài hát hợp lý.")
                return "Không tìm thấy bài hát hợp lý."
            lyrics = song.lyrics if hasattr(song, 'lyrics') else "Không có lời bài hát."
            lyrics = lyrics.replace("/artists/Genius-english-translations", "").strip()
            try:
                with open(cache_path, 'w', encoding='utf-8') as cache_file:
                    cache_file.write(lyrics)
                logging.info(f"Lưu lời bài hát vào cache: {cache_path}")
            except IOError as e:
                logging.error(f"Không thể ghi vào file {cache_path}: {e}")
                return "Không thể ghi vào file cache."
            return lyrics
        except Exception as e:
            logging.error(f"Đã xảy ra lỗi khi tìm lời bài hát: {e}")
            return "Đã có lỗi xảy ra khi tìm lời bài hát. Vui lòng thử lại."
        return self.get_lyrics(song_path)
    def play_previous_song(self, _event=None):
        if not self.playlist:
            return

        if self.playlist_index <= 0:
            self.playlist_index = len(self.playlist) - 1
        else:
            self.playlist_index -= 1
        self.show_notification("🎵 Playing previous track")

        self.load_and_play_song(self.playlist_index)
        self.playlist_frame.song_list.selection_clear(0, tk.END)
        self.playlist_frame.song_list.select_set(self.playlist_index)
        logging.info("playing previous song")
    # 🧠 Nằm trong class MusicPlayer
    

    def toggle_video_pause(self):
        """Play/Pause video nếu đang dùng VLC"""
        if self.mediaplayer and self.mediaplayer.is_playing():
            self.mediaplayer.pause()
            self.STATE = PlayerState.PAUSED
        elif self.mediaplayer:
            self.mediaplayer.play()
            
            # 🔍 CHỜ CHO VIDEO LOAD XONG METADATA
            self.after(300, self._check_video_duration)
            if duration <= 0:
                logging.warning("Không lấy được độ dài video trong toggle_video_pause.")
                return

            self.STATE = PlayerState.PLAYING

        self.control_bar.update_play_button(self.STATE)


    def play_next_video(self):
        """Auto gọi play_next_song — nếu playlist có video sẽ tự động xử lý"""
        self.play_next_song()

    def play_previous_video(self):
        """Auto gọi play_previous — nếu playlist có video sẽ tự động xử lý"""
        self.control_bar.play_previous()  # hoặc self.play_previous_song nếu bạn có hàm riêng

    def stop_video(self):
        """Dừng video và giải phóng tài nguyên"""
        if self.mediaplayer:
            try:
                self.mediaplayer.set_media(None)  # Clear media
                if self.mediaplayer.is_playing():
                    self.mediaplayer.stop()
                self.mediaplayer.release()  # Giải phóng tài nguyên VLC
                self.stop_update_loop()

            except Exception as e:
                logging.warning(f"[WARN] Lỗi khi stop/release VLC player: {e}")
            finally:
                self.mediaplayer = None
                gc.collect()  # Tối ưu bộ nhớ chỉ khi cần thiết
        self.cover_art_frame.mp4_video_label.grid_remove()
        self.cover_art_frame.mp3_cover_art_label.configure(image=None, text="Không có video nào đang phát.")
        self.cover_art_frame.mp3_cover_art_label.grid()



    def play_video(self, video_path):
        """Phát video và kiểm tra trạng thái của player"""
        try:
            self.stop_video()  # Dừng video cũ

            logging.info("[VIDEO] mediaplayer is None, creating new one...")
            self.mediaplayer = self.vlc_instance.media_player_new()

            media = self.vlc_instance.media_new(video_path)
            self.mediaplayer.set_media(media)

            canvas_id = self.cover_art_frame.get_video_label_id()
            if sys.platform.startswith("win"):
                self.mediaplayer.set_hwnd(canvas_id)
            elif sys.platform.startswith("linux"):
                self.mediaplayer.set_xwindow(canvas_id)
            elif sys.platform.startswith("darwin"):
                self.mediaplayer.set_nsobject(canvas_id)

            self.mediaplayer.play()

            # CHỈ SAU KHI play() mới gọi hiển thị video và resize
            self.after(300, lambda: self.cover_art_frame.display_mp4_video(self.mediaplayer))


            # Check video duration nhẹ nhàng
            self.after(500, lambda: self._check_video_duration(retries=10))

            self.STATE = PlayerState.PLAYING
            self.control_bar.update_play_button(self.STATE)

        except Exception as e:
            logging.error(f"Lỗi khi phát video: {e}")



    def wait_until_loaded_and_update(self, retries=10):
        if self.STATE == PlayerState.PLAYING and self.song_length > 0:
            logging.info("✅ Đã load được độ dài bài hát. Bắt đầu update loop.")
            self.start_update_loop()
        elif retries > 0:
            logging.info(f"⏳ Đợi nhạc load... còn {retries} lần")
            self.after(500, lambda: self.wait_until_loaded_and_update(retries - 1))
        else:
            logging.warning("⚠️ Không load được song_length, vẫn cố bắt đầu update loop.")
            self.start_update_loop()



    def load_and_play_song(self, index):
        
        try:
            song_path = self.playlist[index]
            file_extension = os.path.splitext(song_path)[1].lower()
            # --- CẬP NHẬT VLC STREAM KHI ĐỔI BÀI ---
            """if self.is_streaming_lan:
                logging.info("Đang stream LAN, cập nhật VLC cho bài hát mới...")
                self._stop_vlc_stream() # Dừng stream bài cũ
                if self.vlc_executable_path and os.path.exists(song_path):
                    try:
                        # Khởi động lại stream cho bài mới
                        sout_options = f"access=http,mux=mp3,dst=0.0.0.0:{self.lan_stream_port}/stream"
                        # DÙNG MODULE TRANSCODE RÕ RÀNG:
                        sout_string = f'#transcode{{acodec=mp3,ab=192,channels=2,samplerate=44100}}:http{{mux=mp3,dst=:{self.lan_stream_port}/stream,mime=audio/mpeg}}'

                        vlc_command = [
                            self.vlc_executable_path,
                            '-I', 'dummy',
                            song_path,                # Đường dẫn bài hát (không quote)
                            '--sout', sout_string,
                            '--sout-keep',
                            # --- Thêm các tham số ghi log ---
                            '--verbose=2',
                            '--file-logging',
                            f'--logfile={self.vlc_log_path}'
                            # ---------------------------------
                        ]
                        self.vlc_stream_process = subprocess.Popen(
                             vlc_command
                        )
                        logging.info(f"Đã khởi động lại VLC stream cho: {os.path.basename(song_path)}")
                    except Exception as e:
                         logging.error(f"Lỗi khởi động lại VLC stream khi đổi bài: {e}")
                         self.is_streaming_lan = False # Tắt stream nếu lỗi
                         # self.topbar.update_lan_button_state(self.is_streaming_lan) # Cập nhật UI
                else:
                    logging.warning("Không thể khởi động lại stream: thiếu VLC hoặc file không tồn tại.")
                    self.is_streaming_lan = False # Tắt stream
                    # self.topbar.update_lan_button_state(self.is_streaming_lan) # Cập nhật UI
            # -----------------------------------------
            if self.is_file_serving_mode:
                set_current_file_for_server(song_path)"""
            if file_extension in (".mp4", ".avi", ".mkv"):
                self._handle_video_playback(song_path, index)
            elif file_extension in (".mp3", ".wav", ".ogg", ".flac"):
                self._handle_audio_playback(song_path, index)
        except Exception as e:
            logging.error(f"Lỗi khi load/play: {e}")
    def _handle_video_playback(self, song_path, index):
        pil_img = extract_video_thumbnail(song_path)
        if pil_img:
            self.apply_theme_from_cover(pil_img)
        else:
            logging.warning("Không lấy được thumbnail từ video.")

        self.is_video_mode = True
        self.play_video(song_path)
        self.STATE = PlayerState.PLAYING
        self.playlist_index = index
        self.control_bar.set_music_title(Path(song_path).stem, "Unknown")
        self.control_bar.update_play_button(self.STATE)
        self.bottom_frame.start_progress_bar(0)
        self.cover_art_frame.update_lyrics("")
        self.cover_art_frame.mp3_cover_art_label.configure(image=None, text="")
        self.start_update_loop()
    def _handle_audio_playback(self, song_path, index):
        # === THÊM DÒNG DEBUG NGAY ĐẦU TIÊN ===
       
        # =====================================

        self.is_video_mode = False
        self.stop_video()

        # if not song_path.endswith(".mp3"): ...

        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(song_path)
            pygame.mixer.music.play()
            logging.info(f"Playing audio: {os.path.basename(song_path)}")
        except pygame.error as e:
            logging.error(f"Lỗi Pygame khi tải/phát {os.path.basename(song_path)}: {e}")
            return

        self.STATE = PlayerState.PLAYING
        self.playlist_index = index

        # === THÊM DÒNG DEBUG NGAY TRƯỚC KHI GỌI get_audio_length ===
        
        try:
            # Gọi get_audio_length
            self.song_length = self.get_audio_length(song_path)
           
        except AttributeError as ae:
            # Bắt lại lỗi AttributeError cụ thể
            print(f"LỖI AttributeError ngay khi gọi get_audio_length: {ae}")
            logging.exception("Lỗi AttributeError khi gọi get_audio_length")
            # In lại self để xem nó là gì tại thời điểm lỗi
            print(f"LỖI _handle_audio_playback: self type LÚC LỖI = {type(self)}, id = {id(self)}")
            return # Dừng lại nếu lỗi
        except Exception as audio_len_err: # Bắt các lỗi khác nếu có
            print(f"LỖI khác khi gọi get_audio_length: {audio_len_err}")
            logging.exception("Lỗi khác khi gọi get_audio_length")
            return # Dừng lại nếu lỗi

        # Chỉ gọi các hàm sau nếu get_audio_length thành công
        self.after(200, self._start_timer_and_update_loop)
        try:
            audio_stem = Path(song_path).stem
            # Ưu tiên offset đã lưu riêng cho bài này
            saved_offset = self.song_specific_offsets.get(audio_stem)

            if saved_offset is not None:
                self.current_applied_offset = saved_offset
                print(f"Áp dụng offset đã lưu cho '{audio_stem}': {self.current_applied_offset:.2f}s")
            else:
                # Nếu không có offset riêng, dùng offset mặc định
                self.current_applied_offset = self.DEFAULT_GLOBAL_OFFSET
                print(f"Sử dụng offset mặc định cho '{audio_stem}': {self.current_applied_offset:.2f}s")

            # Cập nhật hiển thị trên slider trong ControlBar
            if hasattr(self, 'control_bar') and hasattr(self.control_bar, 'update_offset_slider_display'):
                    self.control_bar.update_offset_slider_display(self.current_applied_offset)

        except Exception as e:
                logging.error(f"Lỗi khi xử lý offset cho bài hát: {e}")
                self.current_applied_offset = self.DEFAULT_GLOBAL_OFFSET # Fallback về mặc định
                # Cập nhật slider về mặc định nếu lỗi
                if hasattr(self, 'control_bar') and hasattr(self.control_bar, 'update_offset_slider_display'):
                    self.control_bar.update_offset_slider_display(self.current_applied_offset)

        song_title = self.get_song_title(song_path)
        artist = self.get_song_artist(song_path)
        self.control_bar.set_music_title(song_title)

        print(f"Đang lấy lời cho: {song_title}")
        lyrics_result = self.lyrics_handler.get_lyrics_for_song(song_path, song_title, artist)
        self.current_lyrics_type = lyrics_result.get('type', 'error')
        self.current_lyrics_data = lyrics_result.get('data', 'Lỗi không xác định khi lấy lời.')
        self.current_lrc_line_index = -1
        print(f"Loại lời tìm thấy: {self.current_lyrics_type}")

        try:
            self.cover_art_frame.update_lyrics(self.current_lyrics_type, self.current_lyrics_data)
            print("Đã gọi cover_art_frame.update_lyrics")
        except AttributeError:
            logging.error("cover_art_frame chưa có hàm update_lyrics(type, data)")
            print("LỖI: cover_art_frame chưa có hàm update_lyrics(type, data)")
        except Exception as lyr_update_err:
            logging.exception(f"Lỗi khi gọi update_lyrics: {lyr_update_err}")
            print(f"LỖI: khi gọi update_lyrics: {lyr_update_err}")

        cover_image, pil_img = self.get_album_cover(song_path)
        if cover_image:
            self.cover_art_frame.display_mp3_cover_art(cover_image)
            if pil_img and self.dynamic_theme_enabled:
                self.apply_theme_from_cover(pil_img)
        else:
            self.cover_art_frame.display_mp3_cover_art(None)

        self.control_bar.update_play_button(self.STATE)
        # Gọi start_progress_bar sau khi có song_length
        if self.song_length > 0:
            self.bottom_frame.start_progress_bar(self.song_length)
        else:
            print("Cảnh báo: song_length <= 0, không thể bắt đầu progress bar đúng.")
            # Có thể đặt progress bar về 0 hoặc trạng thái chờ
            try: self.bottom_frame.progress_bar.set(0)
            except Exception: pass

    def show_lyrics(self):
        try:
            if not self.playlist:
                logging.warning("Playlist trống.")
                self.lyrics_box.configure(state="normal")
                self.lyrics_box.delete("1.0", "end")
                self.lyrics_box.insert("1.0", "Không có bài hát nào đang phát.")
                self.lyrics_box.configure(state="disabled")
                return

            song_path = self.playlist[self.playlist_index]
            lyrics = self.lyrics_handler.get_lyrics_for_song(song_path)

            self.lyrics_box.configure(state="normal")
            self.lyrics_box.delete("1.0", "end")
            self.lyrics_box.insert("1.0", lyrics if lyrics else "Không tìm thấy lời bài hát.")
            self.lyrics_box.configure(state="disabled")

        except Exception as e:
            logging.error(f"Lỗi khi hiển thị lời bài hát: {e}")
            self.lyrics_box.configure(state="normal")
            self.lyrics_box.delete("1.0", "end")
            self.lyrics_box.insert("1.0", "Không thể hiển thị lời bài hát.")
            self.lyrics_box.configure(state="disabled")


    def toggle_shuffle(self):
        self.shuffle_enabled = not self.shuffle_enabled

        if self.shuffle_enabled:
            self.control_bar.shuffle_button.configure(
                fg_color="#3aafa9",
                image=self.shuffle_enabled_icon
            )
            self.control_bar.show_notification("🔀 Đã bật phát ngẫu nhiên")
        else:
            self.control_bar.shuffle_button.configure(
                fg_color="transparent",
                image=self.shuffle_icon
            )
            self.control_bar.show_notification("⏹️ Đã tắt phát ngẫu nhiên")

    def play_next_song(self, _event=None):
        if not self.playlist:
            return

        if self.shuffle_enabled:
            available_indices = [i for i in range(len(self.playlist)) if i != self.playlist_index]
            if available_indices:
                self.playlist_index = random.choice(available_indices)
            else:
                # Nếu chỉ còn một bài hát hoặc không có bài hát nào khác, có thể dừng hoặc phát lại từ đầu
                self.playlist_index = 0
        else:
            # PLAY FROM BEGINING
            if self.playlist_index >= len(self.playlist) - 1:
                self.playlist_index = 0
            else:
                self.playlist_index += 1
        
        
        



        self.load_and_play_song(self.playlist_index)

        # UPDATE SELECTION
        self.playlist_frame.song_list.selection_clear(0, tk.END)
        self.playlist_frame.song_list.select_set(self.playlist_index)
        logging.info("playing next song")
    def get_song_length(self, file_path):
        audio = File(file_path)
        if audio is not None and audio.info is not None:
            return audio.info.length
        return 0

    def get_song_title(self, path):
        try:
            audio = EasyID3(path)
            return audio.get("title", ["Unknown Title"])[0]
        except Exception as e:
            logging.warning(f"Không lấy được title từ file: {e}")
            return "Unknown Title"

    def get_album_cover(self, file_path):
        if not file_path.endswith(".mp3"):
            return None, None

        try:
            audio_file = id3.ID3(file_path)
            for tag in audio_file.getall("APIC"):
                if tag.mime in ("image/jpeg", "image/png"):
                    cover_data = tag.data
                    pil_image = Image.open(io.BytesIO(cover_data)).convert("RGB")
                    resized = pil_image.resize((250, 250))
                    ctk_img = ctk.CTkImage(
                        light_image=resized,
                        dark_image=resized,
                        size=(250, 250)
                    )
                    return ctk_img, pil_image  # ✅ Trả về cả hai
        except Exception as e:
            logging.error(f"Lỗi khi lấy cover art: {e}")
        
        return None, None


    def round_corners(self, image, radius):
        rounded_mask = Image.new("L", image.size, 0)
        draw = ImageDraw.Draw(rounded_mask)
        draw.rounded_rectangle((0, 0) + image.size, radius, fill=255)
        rounded_image = Image.new("RGBA", image.size)
        rounded_image.paste(image, (0, 0), mask=rounded_mask)
        return rounded_image

    def volume_up(self, event=None):
        volume = pygame.mixer.music.get_volume()
        if volume < 1.0:
            pygame.mixer.music.set_volume(volume + 0.1)
            logging.info(f"Tăng âm lượng: {pygame.mixer.music.get_volume()}")

    def volume_down(self, event=None):
        volume = pygame.mixer.music.get_volume()
        if volume > 0.0:
            pygame.mixer.music.set_volume(volume - 0.1)
            logging.info(f"Giảm âm lượng: {pygame.mixer.music.get_volume()}")

    def get_song_artist(self, path):
        try:
            audio = EasyID3(path)
            return audio.get("artist", ["Unknown Artist"])[0]
        except Exception as e:
            logging.warning(f"Không lấy được artist từ file: {e}")
            return "Unknown Artist"
    def prompt_load_external_lrc(self):
        """Mở hộp thoại để chọn file .lrc và áp dụng cho bài hát hiện tại."""
        print("--- Bắt đầu quá trình load LRC ngoài ---")
        # Kiểm tra xem có bài hát nào đang được chọn/phát không
        if not self.playlist or self.STATE == PlayerState.STOPPED or self.playlist_index >= len(self.playlist):
            messagebox.showinfo("Thông báo", "Chưa có bài hát nào đang được chọn hoặc phát.", parent=self)
            return

        current_song_path = self.playlist[self.playlist_index]
        try:
            # Lấy phần tên file không bao gồm đuôi mở rộng
            audio_stem = Path(current_song_path).stem
        except Exception as e:
            logging.error(f"Không thể lấy stem từ '{current_song_path}': {e}")
            messagebox.showerror("Lỗi", "Không thể xử lý tên file nhạc hiện tại.", parent=self)
            return

        # Mở hộp thoại chọn file, chỉ cho phép chọn file .lrc
        selected_lrc_file = filedialog.askopenfilename(
            title=f"Chọn file LRC cho '{audio_stem}'",
            filetypes=[("LRC files", "*.lrc"), ("All files", "*.*")],
            parent=self # Đảm bảo hộp thoại hiện trên cửa sổ chính
        )

        # Nếu người dùng không chọn file nào
        if not selected_lrc_file:
            print("Người dùng đã hủy chọn file LRC.")
            return

        # Kiểm tra lại xem có đúng là file .lrc không (mặc dù đã lọc)
        if not selected_lrc_file.lower().endswith(".lrc"):
             messagebox.showwarning("Lỗi File", "Vui lòng chọn một file có đuôi .lrc.", parent=self)
             return

        print(f"Đã chọn file LRC: {selected_lrc_file}")

        # --- Sao chép file LRC vào thư mục cache ---
        try:
            # Kiểm tra xem lyrics_handler và cache_dir có tồn tại không
            if not hasattr(self, 'lyrics_handler') or not hasattr(self.lyrics_handler, 'cache_dir'):
                 messagebox.showerror("Lỗi Cấu hình", "Không tìm thấy thư mục cache lời bài hát.", parent=self)
                 return

            # Đường dẫn đích trong thư mục cache (ví dụ: lyrics_cache/TenBaiHat.lrc)
            target_lrc_path = os.path.join(self.lyrics_handler.cache_dir, f"{audio_stem}.lrc")
            print(f"Sao chép tới: {target_lrc_path}")

            # Dùng shutil.copy2 để sao chép (giữ metadata file) và ghi đè nếu tồn tại
            shutil.copy2(selected_lrc_file, target_lrc_path)
            logging.info(f"Đã sao chép file LRC tùy chỉnh vào cache: {target_lrc_path}")

            # --- (Tùy chọn) Xóa file cache .txt tương ứng nếu có ---
            # Lấy thông tin để tạo cache key cho file .txt
            song_title = self.get_song_title(current_song_path)
            artist = self.get_song_artist(current_song_path)
            # Giả sử lyrics_handler có các hàm clean_title/artist
            if hasattr(self.lyrics_handler, 'clean_title') and hasattr(self.lyrics_handler, 'clean_artist'):
                 cleaned_title = self.lyrics_handler.clean_title(song_title or "")
                 cleaned_artist = self.lyrics_handler.clean_artist(artist or "")
                 if cleaned_title: # Chỉ xóa khi có title sạch
                      cache_key = hashlib.md5(f"{cleaned_title}_{cleaned_artist}".encode('utf-8')).hexdigest()
                      txt_cache_path = os.path.join(self.lyrics_handler.cache_dir, f"{cache_key}.txt")
                      if os.path.exists(txt_cache_path):
                           try:
                               os.remove(txt_cache_path)
                               logging.info(f"Đã xóa cache TXT cũ: {txt_cache_path}")
                           except OSError as e:
                               logging.warning(f"Không thể xóa cache TXT cũ '{txt_cache_path}': {e}")
            # --------------------------------------------------------

            # Tải lại lời bài hát cho bài hiện tại để hiển thị lời mới
            self.reload_lyrics_for_current_song()

            messagebox.showinfo("Thành công", "Đã áp dụng file LRC được chọn.", parent=self)

        except AttributeError as ae:
             # Bắt lỗi nếu thiếu lyrics_handler hoặc hàm clean
             logging.exception(f"Lỗi thuộc tính khi áp dụng LRC: {ae}")
             messagebox.showerror("Lỗi", f"Lỗi cấu hình khi xử lý lời bài hát:\n{ae}", parent=self)
        except Exception as e:
            # Bắt các lỗi khác (ví dụ: lỗi sao chép file)
            logging.exception(f"Lỗi khi sao chép/áp dụng file LRC: {e}")
            messagebox.showerror("Lỗi", f"Đã xảy ra lỗi khi áp dụng file LRC:\n{e}", parent=self)

    def reload_lyrics_for_current_song(self):
        """Tải lại và hiển thị lời cho bài hát đang ở index hiện tại."""
        print(f"Reloading lyrics for index {self.playlist_index}")
        # Kiểm tra tính hợp lệ của playlist và index
        if not self.playlist or not (0 <= self.playlist_index < len(self.playlist)):
             print("Cannot reload lyrics, invalid index or empty playlist.")
             # Có thể reset hiển thị lời bài hát ở đây nếu muốn
             # self.current_lyrics_type = None
             # self.current_lyrics_data = None
             # try: self.cover_art_frame.update_lyrics(None, "...")
             # except: pass
             return

        song_path = self.playlist[self.playlist_index]
        # Lấy title/artist để dùng nếu cần fallback tìm Genius sau khi cache lỗi
        song_title = self.get_song_title(song_path)
        artist = self.get_song_artist(song_path)

        # Kiểm tra sự tồn tại của lyrics_handler
        if not hasattr(self, 'lyrics_handler') or not hasattr(self.lyrics_handler, 'get_lyrics_for_song'):
             logging.error("Cannot reload lyrics: lyrics_handler or get_lyrics_for_song method not found.")
             self.current_lyrics_type = 'error'
             self.current_lyrics_data = 'Lỗi cấu hình trình xử lý lời.'
        else:
            # Gọi lại hàm get_lyrics_for_song (nó sẽ ưu tiên cache LRC mới nhất)
            lyrics_result = self.lyrics_handler.get_lyrics_for_song(song_path, song_title, artist)
            self.current_lyrics_type = lyrics_result.get('type', 'error')
            self.current_lyrics_data = lyrics_result.get('data', 'Lỗi khi tải lại lời.')

        # Reset dòng highlight và cập nhật giao diện
        self.current_lrc_line_index = -1
        print(f"Reloaded lyrics type: {self.current_lyrics_type}")
        try:
            # Kiểm tra cover_art_frame
            if not hasattr(self, 'cover_art_frame') or not hasattr(self.cover_art_frame, 'update_lyrics'):
                 logging.error("Cannot update lyrics UI: cover_art_frame or update_lyrics method not found.")
                 return
            self.cover_art_frame.update_lyrics(self.current_lyrics_type, self.current_lyrics_data)
            print("Reloaded lyrics UI.")
        except Exception as lyr_update_err:
            logging.exception(f"Lỗi khi cập nhật UI lời bài hát sau khi reload: {lyr_update_err}")

    def initialize_pygame(self):
        pygame.init()
        pygame.mixer.init()
        self.music = pygame.mixer.music
        pygame.mixer.music.set_endevent(pygame.USEREVENT)

    def check_for_events(self):
        pygame.display.init()
        for event in pygame.event.get():
            if event.type == pygame.USEREVENT:
                self.play_next_song()

    def setup_icons(self):
        self.play_icon = ctk.CTkImage(Image.open("yami/yami/data/play_arrow.png"))
        self.pause_icon = ctk.CTkImage(Image.open("yami/yami/data/pause.png"))
        self.prev_icon = ctk.CTkImage(Image.open("yami/yami/data/skip_prev.png"))
        self.next_icon = ctk.CTkImage(Image.open("yami/yami/data/skip_next.png"))
        self.folder_icon = ctk.CTkImage(Image.open("yami/yami/data/folder.png"))
        self.music_icon = ctk.CTkImage(Image.open("yami/yami/data/music.png"))
        self.shuffle_icon = ctk.CTkImage(Image.open("yami/yami/data/unshuffle.png"))
        self.shuffle_enabled_icon = ctk.CTkImage(Image.open("yami/yami/data/shuffle.png"))  # Thêm icon này
        self.mute_icon = ctk.CTkImage(Image.open("yami/yami/data/mute.png"))
        self.unmute_icon = ctk.CTkImage(Image.open("yami/yami/data/unmute.png"))
        self.refresh_icon = ctk.CTkImage(Image.open("yami/yami/data/refresh.png"))
        self.load_lrc_icon = ctk.CTkImage(Image.open("yami/yami/data/add_lyrics.png"))
        self.stream_icon = ctk.CTkImage(Image.open("yami/yami/data/online-streaming-icon.png"))
 # Đảm bảo file icon này tồn tại
        logging.info("icons setup")

    def setup_bindings(self):
        self.bind("<F10>", self.play_next_song)
        self.bind("<F8>", self.control_bar.play_previous)
        self.bind("<F9>", self.control_bar.play_pause)
        self.bind("<space>", self.control_bar.play_pause)
        self.bind("<F7>", self.control_bar.stop_music) # Giả sử hàm này tồn tại
        self.bind("<F5>", self.control_bar.volume_up)   # Giả sử hàm này tồn tại
        self.bind("<F6>", self.control_bar.volume_down) # Giả sử hàm này tồn tại
        self.bind("<F3>", self.toggle_shuffle)

        # --- THAY ĐỔI BINDING CHO THANH TUA ---
        # Cả nhấn chuột và kéo chuột đều gọi cùng hàm seek_on_click_or_drag
        # Nhấn chuột: Bắt đầu quá trình tua (lưu trạng thái, pause nếu cần)
        self.bottom_frame.progress_bar.bind("<Button-1>", self.start_seek_drag)
        # Kéo chuột: Thực hiện tua (chỉ cập nhật vị trí và UI)
        self.bottom_frame.progress_bar.bind("<B1-Motion>", self.seek_on_click_or_drag)
        # Nhả chuột: Kết thúc quá trình tua (resume nếu cần)
        self.bottom_frame.progress_bar.bind("<ButtonRelease-1>", self.end_seek_drag)
        # --------------------------------------



def extract_video_thumbnail(video_path, time_in_sec=1):
    try:
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_number = int(fps * time_in_sec)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

        success, frame = cap.read()
        cap.release()

        if not success:
            return None

        # Chuyển từ BGR (OpenCV) sang RGB (PIL)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(frame_rgb)

        return pil_img
    except Exception as e:
        print(f"Lỗi khi lấy thumbnail video: {e}")
        return None

def get_theme_palette(pil_image, color_count=5):
    with io.BytesIO() as buffer:
        pil_image.save(buffer, format="PNG")
        buffer.seek(0)
        thief = ColorThief(buffer)
        return thief.get_palette(color_count=color_count, quality=1)




def rgb_to_hex(rgb):
    return '#%02x%02x%02x' % rgb

if __name__ == "__main__":
    music_player = MusicPlayer()
    music_player.mainloop()
