"""Player Controls"""

import tkinter as tk
import logging
import customtkinter as ctk
from util import BUTTON_WIDTH, PlayerState
import pygame
import time
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3

import vlc
class ControlBar(ctk.CTkFrame):
    """All Player Controls"""

    def __init__(
        self,
        parent,
        shuffle_icon,
        shuffle_enabled_icon

    ):
        super().__init__(parent, corner_radius=10, fg_color="#121212")

        # SETUP
        
        self.parent = parent  # Thêm dòng này để gán 'parent' cho 'self.parent'
        self.music_player = parent
        self.pause_icon = parent.pause_icon
        self.play_icon = parent.play_icon
        self.prev_icon = parent.prev_icon
        self.next_icon = parent.next_icon
        self.mute_icon = parent.mute_icon  # Icon mute
        self.unmute_icon = parent.unmute_icon  # Icon unmute
        self.is_muted = False
        self.play_next_command = parent.play_next_song
        self.title_max_chars = 40
        self.parent = parent
        self.shuffle_icon = shuffle_icon
        self.shuffle_enabled_icon = shuffle_enabled_icon
        self.scroll_index = 0
        self.full_title_text = ""
        self.after_id = None


        # WIDGETS
        """
        self.offset_label_text = ctk.CTkLabel(self, text="Offset(s):", font=("roboto", 10))
        self.offset_slider = ctk.CTkSlider(
            self,
            from_=-5, # Giới hạn dưới -5 giây
            to=5,     # Giới hạn trên +5 giây
            number_of_steps=100, # 10 giây / 100 bước = 0.1 giây mỗi bước
            width=120,
            command=self.slider_offset_changed # Gọi hàm khi kéo slider
        )
        self.offset_slider.set(0) # Giá trị mặc định ban đầu

        # Label hiển thị giá trị offset hiện tại
        self.current_offset_var = tk.StringVar(value="0.0s")
        self.offset_value_label = ctk.CTkLabel(
            self,
            textvariable=self.current_offset_var,
            font=("roboto", 10),
            width=40
        )

        self.save_offset_button = ctk.CTkButton(
            self,
            text="Save Offset",
            width=80,
            height=25,
            font=("roboto", 11),
            command=self.music_player.save_current_song_offset # Gọi hàm lưu trong MusicPlayer
        )
        """
        self.play_button = ctk.CTkButton(
            self,
            command=self.play_pause,
            width=BUTTON_WIDTH,
            height=10,
            text="",
            image=self.pause_icon,
            corner_radius=10,
        )
        
        self.next_button = ctk.CTkButton(
            self,
            command=self.play_next_command,
            width=BUTTON_WIDTH,
            text="",
            corner_radius=10,
            image=self.next_icon,
        )
        self.prev_button = ctk.CTkButton(
            self,
            text="",
            width=BUTTON_WIDTH,
            corner_radius=10,
            command=self.play_previous,
            image=self.prev_icon,
        )
        self.shuffle_button = ctk.CTkButton(
            master=self,
            image=self.shuffle_icon,
            text="",

            fg_color="transparent", 
            command=self.shuffle_toggle
        )
        self.shuffle_button.grid(row=0, column=0, padx=5)

        self.music_title_label = ctk.CTkLabel(
            self,
            text="",
            font=("roboto", 12),
            fg_color="#121212",
            width=20,
            anchor="w",
            text_color="#e0e0e0",
        )
        self.title_label = ctk.CTkLabel(
            self,
            text="",
            font=("Roboto", 14),
            text_color="#ffffff"
        )
        #self.title_label.grid(row=0, column=0, columnspan=5, pady=(5, 0))

        self.playback_label = ctk.CTkLabel(
            self, text="0:00 / 0:00", font=("roboto", 12), fg_color="#121212"
        )
                # 🔊 Volume Slider
        self.volume_slider = ctk.CTkSlider(
            self,
            from_=0,
            to=1,
            number_of_steps=100,
            width=100,
            progress_color="#3aafa9",
            button_color="#3aafa9",
            command=self.change_volume
        )
        self.mute_button = ctk.CTkButton(
            self,
            text="",
            image=self.unmute_icon,
            width=BUTTON_WIDTH,
            command=self.toggle_mute,
            corner_radius=10
        )
        self.mute_button.grid(row=0, column=8, padx=(0, 10))  # Thêm vào bên phải volume
        self.volume_slider.set(0.8)  # Giá trị mặc định
        self.volume_slider.grid(row=0, column=6, padx=(10, 5))

        self.volume_icon_label = ctk.CTkLabel(
            self,
            text="🔊",
            font=("Arial", 16),
            text_color="#e0e0e0"
        )
        self.volume_icon_label.grid(row=0, column=7, padx=(0, 10))

        

        # PLACEMENT
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=0)
        self.grid_columnconfigure(3, weight=0)
        self.grid_columnconfigure(4, weight=0)

        # PLACEMENT
        self.music_title_label.grid(
            row=0, column=0, sticky="w", padx=5, pady=10
        )
        self.playback_label.grid(row=0, column=1, sticky="w", padx=5, pady=10)
        self.prev_button.grid(row=0, column=2, sticky="nsew", padx=5, pady=10)
        self.play_button.grid(row=0, column=3, sticky="nsew", padx=5, pady=10)
        self.next_button.grid(row=0, column=4, sticky="nsew", padx=5, pady=10)
        self.shuffle_button.grid(row=0, column=5, sticky="ew", padx=10) # Điều chỉnh vị trí nếu cần
        """
        # Grid hàng 1: Offset controls (ví dụ đặt bên trái)
        self.offset_label_text.grid(row=1, column=2, sticky="e", padx=(0,5), pady=(0,5))
        self.offset_slider.grid(row=1, column=3, columnspan=2, sticky="ew", padx=0, pady=(0,5)) # Chiếm 2 cột
        self.offset_value_label.grid(row=1, column=5, sticky="w", padx=(5,0), pady=(0,5))
        self.save_offset_button.grid(row=1, column=6, sticky="w", padx=5, pady=(0,5))"""
    
    def check_video_duration(self):
        """Kiểm tra độ dài video sau khi bắt đầu phát"""
        if self.music_player.mediaplayer:
            self.music_player._check_video_duration()  # Gọi phương thức từ MusicPlayer
        else:
            logging.warning("Không thể kiểm tra độ dài video, mediaplayer chưa được khởi tạo.")
    def play_pause(self, event=None):
        """Plays or Pauses Music or Video."""
        if not hasattr(self, 'music_player') or not self.music_player:
            logging.error("Lỗi play_pause: music_player không tồn tại.")
            return

        # --- Xử lý Video (VLC) ---
        if self.music_player.is_video_mode:
            if self.music_player.mediaplayer:
                try:
                    if self.music_player.mediaplayer.is_playing():
                        print("DEBUG play_pause (Video): Pausing video")
                        self.music_player.mediaplayer.pause()
                        self.music_player.STATE = PlayerState.PAUSED
                    else:
                        print("DEBUG play_pause (Video): Playing/Resuming video")
                        self.music_player.mediaplayer.play()
                        self.music_player.STATE = PlayerState.PLAYING
                except Exception as vlc_err:
                    print(f"Lỗi VLC play/pause: {vlc_err}")
                    logging.error(f"Lỗi VLC play/pause: {vlc_err}")
            else:
                print("DEBUG play_pause (Video): Mediaplayer không tồn tại.")
                self.music_player.STATE = PlayerState.STOPPED

        # --- Xử lý Audio (Pygame) ---
        else:
            if self.music_player.STATE == PlayerState.PLAYING:
                print("DEBUG play_pause (Audio): Pausing audio")
                # Lấy vị trí hiện tại TRƯỚC KHI pause
                current_pos_before_pause = self.music_player.get_song_position()
                try:
                    self.music_player.music.pause() # Gọi hàm pause của pygame
                    self.music_player.STATE = PlayerState.PAUSED # Cập nhật state
                    # Cập nhật offset dựa trên vị trí lấy được, và reset start_time
                    self.music_player.seek_offset = current_pos_before_pause # Dùng vị trí đã tính
                    self.music_player.start_time = None # Đặt start_time là None
                    print(f"DEBUG play_pause (Audio): Set start_time=None, seek_offset={self.music_player.seek_offset:.2f}")
                    logging.info("Audio paused")
                except pygame.error as pause_err:
                    print(f"LỖI pygame pause: {pause_err}")
                    logging.error(f"Lỗi pygame pause: {pause_err}")

            else: # Trạng thái là PAUSED hoặc STOPPED
                print("DEBUG play_pause (Audio): Resuming/Playing audio")
                try:
                    self.music_player.music.unpause() # unpause sẽ resume nếu đang pause
                    self.music_player.STATE = PlayerState.PLAYING # Cập nhật state
                    # Reset start_time để bắt đầu tính thời gian từ lúc resume
                    self.music_player.start_time = time.time()
                    # seek_offset giữ nguyên giá trị đã lưu khi pause
                    print(f"DEBUG play_pause (Audio): Set start_time={self.music_player.start_time:.2f}, seek_offset={self.music_player.seek_offset:.2f}")
                    logging.info("Audio resumed")
                    # Đảm bảo vòng lặp update chạy lại
                    self.music_player.start_update_loop()
                except pygame.error as unpause_err:
                    print(f"LỖI pygame unpause: {unpause_err}")
                    logging.error(f"Lỗi pygame unpause: {unpause_err}")

        # Cập nhật nút play/pause trên UI (luôn làm sau khi xử lý state)
        self.update_play_button(self.music_player.STATE)

####
####
    def change_volume(self, value):
        """Cập nhật âm lượng khi kéo slider"""
        try:
            if self.music_player.mediaplayer:  # VLC video
                current_volume = self.music_player.mediaplayer.audio_get_volume()
                new_volume = int(value * 100)
                if new_volume != current_volume:  # Chỉ thay đổi khi có sự khác biệt
                    self.music_player.mediaplayer.audio_set_volume(new_volume)
                    logging.info(f"Âm lượng mới: {new_volume:.2f}")
            else:  # Pygame audio
                current_volume = pygame.mixer.music.get_volume()
                if abs(current_volume - value) > 0.05:  # Chỉ thay đổi khi sự khác biệt lớn hơn 0.05
                    pygame.mixer.music.set_volume(value)
                    logging.info(f"Âm lượng mới: {value:.2f}")
        except Exception as e:
            logging.error(f"Lỗi khi đặt âm lượng: {e}")

        


    def update_play_button(self, state):
        """Switches Play/Pause Icon"""

        if state == PlayerState.PLAYING:
            self.play_button.configure(image=self.pause_icon)
        else:
            self.play_button.configure(image=self.play_icon)

    def play_previous(self, event=None):
        """Play Previous Song/Goto Last Song"""

        if not self.music_player.playlist:
            return

        # PLAY FROM END
        if self.music_player.playlist_index == 0:
            logging.info("playing from end")
            self.music_player.playlist_index = (
                len(self.music_player.playlist) - 1
            )
        # PLAY PREVIOUS
        else:
            self.music_player.playlist_index -= 1
            logging.info("playing previous")
        self.music_player.load_and_play_song(self.music_player.playlist_index)

        # UPDATE SELECTION
        self.music_player.playlist_frame.song_list.selection_clear(0, tk.END)
        self.music_player.playlist_frame.song_list.select_set(
            self.music_player.playlist_index
        )
    def shuffle_toggle(self):
        """Bật/Tắt chế độ Shuffle và cập nhật icon"""
        self.parent.toggle_shuffle()  # Cập nhật trạng thái từ MusicPlayer

        if self.parent.shuffle_enabled:
            self.shuffle_button.configure(image=self.shuffle_enabled_icon)
        else:
            self.shuffle_button.configure(image=self.shuffle_icon)

    def volume_up(self, event=None):
        """Tăng âm lượng"""
        volume = pygame.mixer.music.get_volume()
        if volume < 1.0:
            new_volume = max(0.0, min(volume + 0.1, 1.0))
            pygame.mixer.music.set_volume(new_volume)

            logging.info(f"Tăng âm lượng: {pygame.mixer.music.get_volume()}")

    def volume_down(self, event=None):
        """Giảm âm lượng"""
        volume = pygame.mixer.music.get_volume()
        if volume > 0.0:
            new_volume = max(0.0, min(volume - 0.1, 1.0))
            pygame.mixer.music.set_volume(new_volume)
            logging.info(f"Giảm âm lượng: {pygame.mixer.music.get_volume()}")

    # TRUNCATOR
    def stop_music(self, event=None):
        """Dừng nhạc"""
        if self.STATE == PlayerState.PLAYING:
            self.music.stop()
            self.STATE = PlayerState.STOPPED
            self.control_bar.update_play_button(self.STATE)  # Cập nhật nút play-pause
            logging.info("Nhạc đã dừng.")
            

    def set_music_title(self, title):
        """Truncates And Sets Music Title or starts scroll if too long"""
        combined_title = f"{title}`"
        self.full_title_text = combined_title

        # Reset nếu có scroll trước đó
        if self.after_id:
            self.after_cancel(self.after_id)

        self.scroll_index = 0
        self.scroll_title()

    def show_notification(self, message, duration=2000):
        """Hiển thị thông báo nhỏ trong thời gian ngắn (ms)"""
        notif = ctk.CTkLabel(
            self,
            text=message,
            font=("Roboto", 14),
            fg_color="#333333",
            text_color="white",
            corner_radius=8,
            padx=10,
            pady=5
        )
        notif.place(relx=0.5, rely=1.2, anchor="s")  # Đặt bên dưới control bar

        # Tự động xóa sau `duration` milliseconds
        self.after(duration, notif.destroy)
    def toggle_mute(self):
        """Bật / Tắt tiếng"""
        try:
            if self.music_player.mediaplayer:
                current_volume = self.music_player.mediaplayer.audio_get_volume()
                if self.is_muted:
                    self.music_player.mediaplayer.audio_set_volume(self.last_volume)
                    self.mute_button.configure(image=self.unmute_icon)
                    self.volume_slider.set(self.last_volume / 100)
                    logging.info("Unmuted video")
                else:
                    self.last_volume = current_volume
                    self.music_player.mediaplayer.audio_set_volume(0)
                    self.mute_button.configure(image=self.mute_icon)
                    self.volume_slider.set(0)
                    logging.info("Muted video")
            else:
                current_volume = pygame.mixer.music.get_volume()
                if self.is_muted:
                    pygame.mixer.music.set_volume(self.last_volume)
                    self.mute_button.configure(image=self.unmute_icon)
                    self.volume_slider.set(self.last_volume)
                    logging.info("Unmuted audio")
                else:
                    self.last_volume = current_volume
                    pygame.mixer.music.set_volume(0)
                    self.mute_button.configure(image=self.mute_icon)
                    self.volume_slider.set(0)
                    logging.info("Muted audio")
            self.is_muted = not self.is_muted
        except Exception as e:
            logging.error(f"Lỗi khi bật/tắt mute: {e}")
    def scroll_title(self):
        if len(self.full_title_text) <= self.title_max_chars:
            self.music_title_label.configure(text=self.full_title_text)
            return

        display_text = self.full_title_text[self.scroll_index:self.scroll_index + self.title_max_chars]
        self.music_title_label.configure(text=display_text)

        self.scroll_index += 1
        if self.scroll_index + self.title_max_chars > len(self.full_title_text):
            self.scroll_index = 0  # Reset lại từ đầu khi hết chữ

        self.after_id = self.after(200, self.scroll_title)  # Cập nhật sau mỗi 200ms

