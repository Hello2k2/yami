import tkinter as tk
import customtkinter as ctk
import vlc
from PIL import Image
import logging # Thêm logging để ghi lỗi nếu cần

class CoverArtFrame(ctk.CTkFrame):
    """Khung hiển thị ảnh bìa và lời bài hát (MP3) hoặc video (MP4)"""

    def __init__(self, parent):
        super().__init__(parent)

        self.rowconfigure(0, weight=1) # Hàng cho ảnh/video
        self.rowconfigure(1, weight=0) # Hàng cho lyrics
        self.columnconfigure(0, weight=1)

        self.image_refs = []
        self.max_image_refs = 10
        self.video_width = 400 # Kích thước video mặc định
        self.video_height = 300

        # Lưu trữ dữ liệu LRC đã parse để highlight
        self.parsed_lrc_data = None
        self.number_of_lrc_lines = 0

        # ----- Cover Art Label (MP3) -----
        self.mp3_cover_art_label = ctk.CTkLabel(
            self,
            image=None,
            text="Không có ảnh",
            # Bỏ width/height cố định để linh hoạt hơn
            # width=250,
            # height=250,
            fg_color="#141414",
            corner_radius=20,
        )
        self.mp3_cover_art_label.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # ----- Lyrics Textbox -----
        self.lyrics_textbox = ctk.CTkTextbox(
            self,
            height=150, # Giữ chiều cao cố định hoặc điều chỉnh
            fg_color="#141414",
            text_color="#e0e0e0",
            font=("Roboto", 12),
            wrap="word", # Tự động xuống dòng
            corner_radius=10,
            border_spacing=5,
            state="disabled" # Ban đầu không cho sửa
        )
        self.lyrics_textbox.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10)) # Giãn ngang

        # --- Cấu hình Tag Highlight ---
        # Màu này nên lấy từ theme hoặc định nghĩa rõ ràng
        highlight_bg_color = "#3aafa9" # Ví dụ màu xanh lá
        highlight_fg_color = "black"   # Ví dụ màu chữ đen trên nền xanh
        try:
            self.lyrics_textbox.tag_config(
                "highlight",
                background=highlight_bg_color,
                foreground=highlight_fg_color,
                # font=('Roboto', 12, 'bold') # Có thể thêm font đậm
            )
        except Exception as tag_err:
             logging.error(f"Lỗi cấu hình tag highlight: {tag_err}")
        # ---------------------------

        # ----- Video Container (ẩn lúc đầu) -----
        self.video_container = ctk.CTkFrame(
            self,
            fg_color="#000000",
            corner_radius=20,
        )
        self.video_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.video_container.grid_remove()

        # ----- Video Label -----
        self.mp4_video_label = tk.Label(
            self.video_container,
            bg="black",
        )
        self.mp4_video_label.pack(expand=True, fill="both")

        # Giữ layout không tự co lại
        self.video_container.pack_propagate(False)
        self.mp4_video_label.pack_propagate(False)

    def update_lyrics(self, lyrics_type, lyrics_data):
        """
        Cập nhật nội dung Textbox dựa trên loại và dữ liệu lời bài hát.
        lyrics_type: 'lrc', 'txt', hoặc 'error'
        lyrics_data: list [(time, line)] cho 'lrc', string cho 'txt'/'error'
        """
        self.parsed_lrc_data = None # Reset dữ liệu LRC cũ
        self.number_of_lrc_lines = 0 # Reset số dòng
        last_line_index = "1.0"

        try:
            self.lyrics_textbox.configure(state="normal") # Cho phép sửa đổi
            self.lyrics_textbox.delete("1.0", ctk.END) # Xóa nội dung cũ

            if lyrics_type == 'lrc' and isinstance(lyrics_data, list):
                print(f"Hiển thị {len(lyrics_data)} dòng LRC...") # Debug
                self.parsed_lrc_data = lyrics_data # Lưu lại để highlight
                full_lrc_text = ""
                for i, (_, line_text) in enumerate(lyrics_data):
                    # Thêm text vào chuỗi, kèm newline
                    full_lrc_text += line_text + "\n"
                    self.number_of_lrc_lines += 1 # Đếm số dòng

                if full_lrc_text:
                    # Chèn toàn bộ text vào textbox (loại bỏ dòng trắng cuối nếu có)
                    self.lyrics_textbox.insert("1.0", full_lrc_text.strip())
                    # last_line_index = f"{self.number_of_lrc_lines}.end" # Không cần thiết lắm
                else:
                    self.lyrics_textbox.insert("1.0", "LRC có dữ liệu nhưng không có text.")
                # Xóa highlight cũ khi load lời mới
                self.highlight_lyric_line(-1)

            elif lyrics_type == 'txt':
                if lyrics_data and isinstance(lyrics_data, str):
                    self.lyrics_textbox.insert("1.0", lyrics_data.strip())
                    # self.number_of_lrc_lines = lyrics_data.count('\n') + 1 # Không cần đếm cho txt
                else:
                    self.lyrics_textbox.insert("1.0", "Không tìm thấy lời bài hát.")

            elif lyrics_type == 'error':
                error_msg = lyrics_data if isinstance(lyrics_data, str) else "Lỗi không xác định khi lấy lời."
                self.lyrics_textbox.insert("1.0", error_msg)
            else: # Trường hợp không xác định
                 logging.warning(f"Nhận được lyrics_type không xác định: {lyrics_type}")
                 self.lyrics_textbox.insert("1.0", "Không thể hiển thị lời bài hát (unknown type).")

            # Cuộn lên đầu textbox
            self.lyrics_textbox.yview_moveto(0)

        except Exception as e:
            logging.exception(f"Lỗi trong update_lyrics: {e}")
            try: # Cố gắng hiển thị lỗi nếu có vấn đề
                 self.lyrics_textbox.delete("1.0", ctk.END)
                 self.lyrics_textbox.insert("1.0", f"Lỗi hiển thị lời: {e}")
            except Exception: pass
        finally:
            # Luôn đặt lại trạng thái chỉ đọc
            self.lyrics_textbox.configure(state="disabled")
            # self._last_lyrics_index = last_line_index # Có thể không cần


    def highlight_lyric_line(self, line_index):
        """
        Làm nổi bật dòng lời thứ line_index (0-based) trong lyrics_textbox.
        Nếu line_index < 0, xóa mọi highlight.
        """
        try:
            # Đảm bảo widget còn tồn tại
            if not self.lyrics_textbox.winfo_exists():
                return

            # print(f"Highlighting request for index: {line_index}") # Debug

            # Xóa tag 'highlight' cũ trên toàn bộ văn bản trước khi áp dụng cái mới
            self.lyrics_textbox.tag_remove("highlight", "1.0", ctk.END)

            # Chỉ highlight nếu index hợp lệ và có dữ liệu LRC
            if line_index >= 0 and self.parsed_lrc_data and line_index < self.number_of_lrc_lines:
                # Dòng thứ N trong dữ liệu LRC tương ứng với dòng N+1 trong Textbox
                textbox_line_num = line_index + 1
                start_index = f"{textbox_line_num}.0"
                end_index = f"{textbox_line_num}.end" # Lấy hết dòng
                # print(f"Applying highlight to range: {start_index} - {end_index}") # Debug

                # Thêm tag highlight vào dòng được chỉ định
                self.lyrics_textbox.tag_add("highlight", start_index, end_index)

                # Cuộn đến dòng đó để đảm bảo nó hiển thị (chỉ cuộn nếu cần)
                # self.lyrics_textbox.see(start_index)
                # Cách cuộn mượt hơn một chút: đảm bảo cả đầu và cuối dòng trong view
                # Có thể cần tính toán vị trí để cuộn vào giữa màn hình thay vì chỉ see()
                self.lyrics_textbox.see(f"{textbox_line_num}.0 linestart") # Đảm bảo đầu dòng thấy được


        except tk.TclError as tcl_err:
             # Lỗi thường gặp nếu index không hợp lệ hoặc widget bị hủy
             if "text doesn't contain line" in str(tcl_err):
                  logging.warning(f"Highlight lỗi: Index {line_index+1} không tồn tại trong textbox.")
             elif "invalid command name" in str(tcl_err):
                  logging.warning("Highlight lỗi: Textbox có thể đã bị hủy.")
             else:
                  logging.exception(f"Lỗi Tcl khi highlight dòng {line_index}: {tcl_err}")
        except Exception as e:
            logging.exception(f"Lỗi không xác định khi highlight dòng {line_index}: {e}")
 

    def display_mp3_cover_art(self, image):
        """Hiển thị ảnh bìa và lyrics textbox, ẩn video."""
        if not hasattr(self, "mp3_cover_art_label") or not self.mp3_cover_art_label.winfo_exists():
            logging.warning("display_mp3_cover_art: mp3_cover_art_label không tồn tại.")
            return

        self.tk_image = image # Giữ tham chiếu để tránh bị garbage collected
        self.image_refs.append(image)
        if len(self.image_refs) > self.max_image_refs:
            self.image_refs.pop(0)

        try:
            # Ẩn video container
            if self.video_container.winfo_ismapped():
                 self.video_container.grid_remove()

            # Hiện ảnh bìa và lyrics textbox
            if not self.mp3_cover_art_label.winfo_ismapped():
                 self.mp3_cover_art_label.grid()
            if not self.lyrics_textbox.winfo_ismapped():
                 self.lyrics_textbox.grid()

            # Cập nhật ảnh
            self.mp3_cover_art_label.configure(image=self.tk_image, text="" if self.tk_image else "Không có ảnh")

        except Exception as e:
            logging.exception(f"Lỗi khi hiển thị ảnh bìa: {e}")


    def display_mp4_video(self, player, retry_count=0):
        """Hiển thị video container, ẩn ảnh bìa và lyrics."""
        if not hasattr(self, "video_container") or not self.video_container.winfo_exists():
             logging.warning("display_mp4_video: video_container không tồn tại.")
             return

        try:
            # Ẩn ảnh bìa và lyrics
            if self.mp3_cover_art_label.winfo_ismapped():
                 self.mp3_cover_art_label.grid_remove()
            if self.lyrics_textbox.winfo_ismapped():
                 self.lyrics_textbox.grid_remove()

            # Hiện video container
            if not self.video_container.winfo_ismapped():
                 self.video_container.grid()

            # --- Logic lấy kích thước và resize video ---
            width = player.video_get_width()
            height = player.video_get_height()

            if width == 0 or height == 0:
                if retry_count < 5:
                    # Dùng after của widget này thay vì root window nếu có thể
                    self.after(200, lambda p=player, r=retry_count+1: self.display_mp4_video(p, r))
                else:
                    logging.error("Không lấy được kích thước video sau 5 lần thử.")
                return

            aspect_ratio = width / height
            # Đợi widget ổn định kích thước trước khi lấy winfo_width
            self.update_idletasks()
            container_width = self.video_container.winfo_width()
            # Trừ padding/border nếu có (ví dụ padx=10*2)
            max_width = container_width - 20
            new_width = min(self.video_width, max_width) # Lấy min giữa default và max
            new_height = int(new_width / aspect_ratio)

            # Đảm bảo kích thước > 0
            new_width = max(1, new_width)
            new_height = max(1, new_height)

            # Cấu hình kích thước cho tk.Label chứa video
            self.mp4_video_label.config(width=new_width, height=new_height)
            logging.info(f"Video resized: {new_width}x{new_height} (aspect {aspect_ratio:.2f})")

        except Exception as e:
            logging.exception(f"Lỗi khi hiển thị video hoặc lấy size từ VLC: {e}")


    def get_video_label_id(self):
        """Lấy ID cửa sổ của tk.Label để gắn VLC vào."""
        try:
            # Đảm bảo widget tồn tại trước khi lấy ID
            if hasattr(self, 'mp4_video_label') and self.mp4_video_label.winfo_exists():
                return self.mp4_video_label.winfo_id()
            else:
                 logging.error("mp4_video_label không tồn tại khi gọi get_video_label_id")
                 return None
        except Exception as e:
             logging.exception("Lỗi khi lấy video label ID")
             return None