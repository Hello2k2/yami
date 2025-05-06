# Thêm vào phần import
import tkinter as tk
import customtkinter as ctk
from pathlib import Path # Thêm Path từ pathlib

class PlaylistFrame(ctk.CTkFrame):
    """Playlist Holder"""

    def __init__(self, parent):
        super().__init__(parent, corner_radius=10, fg_color="#121212")
        self.parent = parent # Chính là MusicPlayer instance
        self.original_playlist_data = [] # Lưu trữ playlist gốc (path, stem)

        # ---- Cấu hình Grid ----
        # Hàng 0 cho thanh tìm kiếm
        # Hàng 1 cho listbox
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)  # cột cho listbox/search
        self.grid_columnconfigure(1, weight=0)  # cột cho scrollbar

        # ---- Thanh tìm kiếm ----
        self.search_entry = ctk.CTkEntry(
            self,
            placeholder_text="Tìm kiếm trong playlist...",
            height=30,
            corner_radius=8
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(10, 0), pady=(10, 5))
        # Gọi hàm filter_playlist mỗi khi nội dung thay đổi
        self.search_entry.bind("<KeyRelease>", self.filter_playlist_event)

        # ---- Listbox và Scrollbar (Giữ nguyên cấu hình grid) ----
        self.song_list = tk.Listbox(
            self,
            activestyle="none",
            relief="flat",
            bg="#141414",
            fg="#e0e0e0",
            selectbackground="#3aafa9",
            font=("roboto", 12),
            highlightthickness=0,
            # borderwidth=0 # Đảm bảo không có viền tk mặc định
        )
        self.song_list.grid(row=1, column=0, sticky="nsew", padx=(10,0), pady=(0,10)) # Thêm padx/pady

        self.scrollbar = ctk.CTkScrollbar(self, command=self.song_list.yview)
        self.scrollbar.grid(row=1, column=1, sticky="ns", pady=(0,10)) # Thêm pady

        self.song_list.config(yscrollcommand=self.scrollbar.set)
        self.song_list.bind("<Double-1>", self.play)
        self.song_list.bind("<Return>", self.play)

    def filter_playlist_event(self, event=None):
        """Sự kiện được gọi khi người dùng nhập vào ô tìm kiếm."""
        search_term = self.search_entry.get().lower()
        self.update_listbox(search_term)

    def update_listbox(self, search_term=""):
        """Cập nhật Listbox dựa trên bộ lọc tìm kiếm."""
        self.song_list.delete(0, tk.END) # Xóa các mục hiện tại

        # Lọc từ self.original_playlist_data
        filtered_items = []
        for index, (file_path, file_stem) in enumerate(self.original_playlist_data):
            if search_term in file_stem.lower():
                # Lưu (index gốc, tên hiển thị)
                filtered_items.append((index, f"• {file_stem}"))

        # Thêm các mục đã lọc vào Listbox
        for _, display_name in filtered_items:
            self.song_list.insert(tk.END, display_name)

    def set_original_playlist(self, playlist_paths):
        """Lưu trữ playlist gốc và cập nhật Listbox lần đầu."""
        self.original_playlist_data = []
        for index, file_path in enumerate(playlist_paths):
             try:
                 file_stem = Path(file_path).stem
                 self.original_playlist_data.append((index, file_stem))
             except Exception: # Bỏ qua nếu không lấy được stem
                  pass
        # Cập nhật listbox với danh sách đầy đủ ban đầu
        self.update_listbox()

    def play(self, event):
        """Phát bài hát được chọn trong Listbox đã lọc."""
        try:
            # Lấy index của mục được chọn trong Listbox hiện tại
            selected_listbox_index = event.widget.curselection()[0]
            # Lấy tên hiển thị của mục đó
            selected_display_name = self.song_list.get(selected_listbox_index)

            # Tìm index gốc trong original_playlist_data dựa trên tên hiển thị
            original_index_to_play = -1 # Đổi tên biến để rõ ràng hơn
            # --- SỬA LẠI VÒNG LẶP Ở ĐÂY ---
            for original_idx, file_stem in self.original_playlist_data: # Giải nén đúng cấu trúc (index, stem)
                 # So sánh tên hiển thị trong listbox với tên đã định dạng từ dữ liệu gốc
                 if f"• {file_stem}" == selected_display_name:
                      original_index_to_play = original_idx # Lưu lại index gốc cần phát
                      break # Tìm thấy thì dừng lặp

            if original_index_to_play != -1:
                 # Gọi hàm trên đối tượng cha (MusicPlayer) với index gốc đã tìm được
                 if hasattr(self.parent, 'load_and_play_song'):
                      print(f"Playing original index: {original_index_to_play}") # In index gốc
                      self.parent.load_and_play_song(original_index_to_play)
                 else:
                      print("LỖI: self.parent không có hàm load_and_play_song")
            else:
                 # Trường hợp hiếm gặp: không tìm thấy index gốc khớp với tên hiển thị
                 print(f"LỖI: Không tìm thấy index gốc cho '{selected_display_name}' trong original_playlist_data")

        except IndexError:
            # Người dùng nhấp đúp vào chỗ trống hoặc listbox rỗng
            print("DEBUG: IndexError in play - No selection or empty listbox.")
            pass # Không chọn gì thì bỏ qua
        except Exception as e:
            # In lỗi cụ thể ra để debug
            print(f"Lỗi không xác định trong PlaylistFrame.play: {e}")
            logging.exception(f"Lỗi trong PlaylistFrame.play") # Ghi log chi tiết hơn

    def highlight_current_song(self, original_song_index):
        """Highlight bài hát trong Listbox dựa trên index gốc."""
        self.song_list.selection_clear(0, tk.END)

        # Tìm vị trí của bài hát (với original_song_index) trong Listbox hiện tại
        target_display_name = ""
        for index, file_stem in self.original_playlist_data:
            if index == original_song_index:
                target_display_name = f"• {file_stem}"
                break

        if target_display_name:
            # Lấy danh sách các mục đang hiển thị trong listbox
            current_listbox_items = self.song_list.get(0, tk.END)
            try:
                # Tìm index của mục đó trong listbox hiện tại
                listbox_index_to_select = current_listbox_items.index(target_display_name)
                self.song_list.selection_set(listbox_index_to_select)
                self.song_list.see(listbox_index_to_select)
                print(f"Highlighted listbox index: {listbox_index_to_select} for original index: {original_song_index}")
            except ValueError:
                # Bài hát không có trong listbox hiện tại (do đang lọc)
                print(f"Song with original index {original_song_index} not found in current filtered list.")
                pass # Không highlight nếu không tìm thấy