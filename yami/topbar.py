import logging
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox # Thêm messagebox
import os
from pathlib import Path
import subprocess # Dùng Popen và PIPE
import sys
import threading # Dùng threading
from queue import Queue, Empty # Dùng Queue
import re # Dùng regex
import shlex # Dùng để quote argument khi log

import customtkinter as ctk
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from util import BUTTON_WIDTH
# Giả sử file util.py có định nghĩa SUPPORTED_FORMATS
# Nếu không có, bạn có thể định nghĩa trực tiếp ở đây:
try:
    from util import SUPPORTED_FORMATS
except ImportError:
    logging.warning("Không tìm thấy util.py, sử dụng định dạng mặc định.")
    SUPPORTED_FORMATS = (".mp3", ".wav", ".ogg", ".flac", ".mp4", ".avi", ".mkv")


class TopBar(ctk.CTkFrame):
    """Holds Download And Open Buttons"""

    def __init__(self, parent):
        super().__init__(parent, fg_color="#121212")
        self.parent = parent
        self.result_queue = Queue() # Queue để giao tiếp thread
        self.last_spotdl_output_lines = [] # Lưu trữ output cuối (tùy chọn)
        logging.info("TopBar: Khởi tạo...")

        # Khởi tạo Spotipy
        self.client_id = "5f573c9620494bae87890c0f08a60293"
        self.client_secret = "212476d9b0f3472eaa762d90b19b0ba8"
        try:
            self.sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
                client_id=self.client_id,
                client_secret=self.client_secret
            ))
            logging.info("TopBar: Khởi tạo Spotipy thành công.")
        except Exception as e:
            logging.exception("TopBar: Lỗi khi khởi tạo Spotipy!")
            print(f"LỖI NGHIÊM TRỌNG: Không thể khởi tạo Spotipy - {e}")
            self.sp = None
            messagebox.showerror("Lỗi Khởi Tạo", f"Không thể khởi tạo Spotipy: {e}\nChức năng download sẽ không hoạt động.")

        # --- WIDGETS ---
        # Lấy các icon từ parent (MusicPlayer)
        folder_icon_image = getattr(parent, 'folder_icon', None)
        music_icon_image = getattr(parent, 'music_icon', None)
        # Tạo icon cho nút refresh (có thể dùng lại folder_icon hoặc tạo mới)
        # Giả sử có self.refresh_icon được load trong music.py
        refresh_icon_image = getattr(parent, 'refresh_icon', folder_icon_image)
        lyrics_icon_image = getattr(parent, 'lyrics_icon', music_icon_image) # Từ lần sửa trước
        load_lrc_icon_image = getattr(parent, 'load_lrc_icon', None)
        stream_icon_image = getattr(parent, 'stream_icon', None)
        # <<< THÊM CÁC WIDGET OFFSET VÀO ĐÂY >>>
        self.offset_label_text = ctk.CTkLabel(self, text="Offset(s):", font=("roboto", 10))
        self.offset_slider = ctk.CTkSlider(
            self,
            from_=-5, # Giới hạn dưới -5 giây
            to=5,     # Giới hạn trên +5 giây
            number_of_steps=100, # 10 giây / 100 bước = 0.1 giây mỗi bước
            width=120,
            # Sửa command để gọi hàm trong ControlBar (nếu cần) hoặc định nghĩa lại trong TopBar
            # command=self.parent.control_bar.slider_offset_changed # Cách 1: Gọi qua parent.control_bar
            command=self.slider_offset_changed_topbar # Cách 2: Định nghĩa hàm mới trong TopBar (xem bên dưới)
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
            command=self.parent.save_current_song_offset # Gọi hàm lưu trong MusicPlayer (đảm bảo self.parent là MusicPlayer)
        )
        self.open_folder = ctk.CTkButton(
            self,
            command=self.choose_folder,
            text="Open",
            font=("roboto", 15),
            width=70,
            image=folder_icon_image,
        )

        # --- NÚT REFRESH MỚI ---
        self.refresh_button = ctk.CTkButton(
            self,
            command=self.refresh_playlist, # Gọi hàm mới sẽ tạo ở bước 2
            text="Refresh",
            font=("roboto", 15),
            width=70,
            image=refresh_icon_image, # Sử dụng icon refresh
        )
        # -------------------------
        self.load_lrc_button = ctk.CTkButton(
            self,
            command=self.parent.prompt_load_external_lrc, # Gọi hàm từ parent (MusicPlayer)
            text="load_lyrics",
            font=("roboto", 15),
            width=70,
            # --- SỬ DỤNG BIẾN ĐÃ LẤY TỪ PARENT ---
            image=load_lrc_icon_image,
            # ------------------------------------
        )

        self.music_downloader = ctk.CTkButton(
            self,
            text="Download",
            font=("roboto", 15),
            width=70,
            image=music_icon_image,
            command=self.prompt_download,
        )
        
        self.yami = ctk.CTkButton(
            self,
            text="About",
            font=("roboto", 15),
            width=70,
            image=music_icon_image,
            # command=self.show_about
        )
        
        self.lan_stream_button = ctk.CTkButton(
            self,
            command=self.parent.toggle_lan_sharing, # Gọi phương thức mới trong MusicPlayer
            text="LAN", # Hoặc dùng biểu tượng (icon)
            font=("roboto", 15),
            width=70,
            image=stream_icon_image,
        )
        # Thêm vào grid, ví dụ: bên cạnh nút 'About'
        

        # --- WIDGET PLACEMENT (Cập nhật thứ tự cột) ---
        self.open_folder.grid(row=0, column=1, sticky="w", pady=5, padx=(10,5)) # Giảm padx phải
        self.refresh_button.grid(row=0, column=2, sticky="w", pady=5, padx=5) # Chèn nút refresh vào cột 2
        self.load_lrc_button.grid(row=0, column=3, sticky="nsew", padx=5, pady=10)
        self.music_downloader.grid(row=0, column=4, sticky="w", pady=5, padx=5) # Dịch chuyển cột
        self.yami.grid(row=0, column=5, sticky="w", pady=5, padx=(5,10)) # Dịch chuyển cột
        self.lan_stream_button.grid(row=0, column=6, sticky="w", pady=5, padx=(5,10))
        # <<< THÊM GRID CHO CÁC WIDGET OFFSET >>>
        # Đặt chúng vào cùng hàng 0, bắt đầu từ cột 6
        self.offset_label_text.grid(row=0, column=7, sticky="e", padx=(10, 2), pady=5) # Thêm padx trái
        self.offset_slider.grid(row=0, column=8, sticky="ew", padx=2, pady=5)
        self.offset_value_label.grid(row=0, column=9, sticky="w", padx=(2, 5), pady=5)
        self.save_offset_button.grid(row=0, column=10, sticky="w", padx=5, pady=5)
        # <<< KẾT THÚC THÊM GRID OFFSET >>>
        # --- BINDINGS ---
        try:
            # Đảm bảo parent là một widget có thể bind
            if isinstance(self.parent, (tk.Tk, tk.Toplevel, ctk.CTk)):
                 self.parent.bind("<Control-o>", self.choose_folder)
            else:
                 logging.warning("TopBar: parent không phải là cửa sổ chính, không thể bind <Control-o>.")
        except Exception as e:
             logging.error(f"TopBar: Không thể bind <Control-o>: {e}")

        logging.info("TopBar: Khởi tạo hoàn tất.")

    def choose_folder(self, _event=None):
        """
        Mở hộp thoại để chọn thư mục chứa nhạc, quét các file hỗ trợ,
        cập nhật playlist nội bộ và giao diện PlaylistFrame.
        """
        print("--- Bắt đầu chọn thư mục ---")
        selected_folder = filedialog.askdirectory(
            title="Select Music Folder"
        )
        if not selected_folder:
            print("--- Chọn thư mục bị hủy ---")
            return

        # --- Kiểm tra Thư mục ---
        if not os.path.isdir(selected_folder):
            messagebox.showerror("Lỗi Thư Mục", f"Đường dẫn không hợp lệ:\n{selected_folder}", parent=self.parent)
            return
        # Kiểm tra quyền đọc (và ghi nếu cần cho cache hoặc tải về sau này)
        if not os.access(selected_folder, os.R_OK):
             messagebox.showerror("Lỗi Quyền", f"Không có quyền đọc thư mục:\n{selected_folder}", parent=self.parent)
             return
        # Thêm kiểm tra quyền ghi nếu cần
        # if not os.access(selected_folder, os.W_OK):
        #     messagebox.showwarning("Cảnh báo Quyền", f"Có thể không có quyền ghi vào thư mục:\n{selected_folder}\nChức năng tải về có thể bị ảnh hưởng.", parent=self.parent)

        self.parent.current_folder = selected_folder
        print(f"Đã chọn thư mục: {self.parent.current_folder}")
        logging.info(f"Thư mục được chọn: {self.parent.current_folder}")

        # --- Xóa và Chuẩn bị Playlist Mới ---
        print("Xóa playlist cũ và chuẩn bị cập nhật...")
        playlist_frame = getattr(self.parent, 'playlist_frame', None)
        playlist_list = getattr(self.parent, 'playlist', None)

        # Kiểm tra sự tồn tại của các đối tượng cần thiết
        if not playlist_frame or not hasattr(playlist_frame, 'song_list') or not hasattr(playlist_frame, 'set_original_playlist'):
            logging.error("choose_folder: Thiếu playlist_frame hoặc các thành phần cần thiết của nó.")
            messagebox.showerror("Lỗi Giao Diện", "Không thể truy cập thành phần danh sách phát.", parent=self.parent)
            return
        if not isinstance(playlist_list, list):
            logging.warning("choose_folder: parent.playlist không tồn tại hoặc không phải list. Sẽ tạo mới.")
            # Cố gắng tạo lại nếu chưa có
            setattr(self.parent, 'playlist', [])
            playlist_list = self.parent.playlist # Gán lại sau khi tạo

        # Xóa listbox UI (được thực hiện trong set_original_playlist)
        # playlist_frame.song_list.delete(0, tk.END) # Không cần xóa ở đây nữa

        # Xóa list nội bộ
        playlist_list.clear()

        # --- Quét File Nhạc ---
        music_files_paths = []
        print("Bắt đầu quét file nhạc...")
        try:
            for root, _, files in os.walk(self.parent.current_folder):
                for file in files:
                    # Kiểm tra định dạng hỗ trợ (không phân biệt hoa thường)
                    if file.lower().endswith(SUPPORTED_FORMATS):
                        try:
                            file_path = os.path.join(root, file)
                            # Kiểm tra file có tồn tại và đọc được không
                            if os.path.isfile(file_path) and os.access(file_path, os.R_OK):
                                music_files_paths.append(file_path)
                            # else:
                                # logging.debug(f"Bỏ qua file không đọc được hoặc không phải file: {file_path}")
                        except Exception as file_err:
                             logging.warning(f"Lỗi khi xử lý file '{file}': {file_err}")

        except Exception as e:
             logging.exception(f"Lỗi khi quét thư mục: {self.parent.current_folder}")
             print(f"LỖI: Không thể quét thư mục {self.parent.current_folder} - {e}")
             messagebox.showerror("Lỗi Quét Thư Mục", f"Không thể quét thư mục:\n{e}", parent=self.parent)
             return # Dừng lại nếu không quét được

        print(f"Tìm thấy {len(music_files_paths)} file nhạc/video.")

        # --- Sắp xếp và Cập nhật Playlist ---
        # Sắp xếp theo tên file
        music_files_paths.sort(key=lambda path: Path(path).name.lower())
        print("Đã sắp xếp danh sách file.")

        print("Cập nhật playlist nội bộ và giao diện...")
        # Cập nhật playlist nội bộ của MusicPlayer (danh sách các đường dẫn đầy đủ)
        playlist_list.extend(music_files_paths)

        # Cập nhật PlaylistFrame với dữ liệu gốc để nó tự hiển thị và quản lý lọc
        # Hàm set_original_playlist sẽ lưu trữ danh sách này và cập nhật Listbox
        playlist_frame.set_original_playlist(music_files_paths)

        print(f"--- Chọn thư mục và cập nhật playlist hoàn tất ({len(playlist_list)} mục) ---")

    def refresh_playlist(self, _event=None):
        """
        Quét lại thư mục hiện tại (self.parent.current_folder) và cập nhật playlist.
        """
        current_folder = getattr(self.parent, 'current_folder', None)
        print(f"--- Bắt đầu làm mới playlist cho thư mục: {current_folder} ---")

        if not current_folder or not os.path.isdir(current_folder):
            print("Chưa có thư mục nào được chọn hoặc thư mục không hợp lệ. Không thể làm mới.")
            # Có thể hiển thị thông báo cho người dùng nếu muốn
            # messagebox.showinfo("Thông báo", "Vui lòng chọn một thư mục trước khi làm mới.", parent=self.parent)
            return

        # Lấy các đối tượng cần thiết (tương tự choose_folder)
        playlist_frame = getattr(self.parent, 'playlist_frame', None)
        playlist_list = getattr(self.parent, 'playlist', None)

        if not playlist_frame or not hasattr(playlist_frame, 'set_original_playlist') or not isinstance(playlist_list, list):
            logging.error("refresh_playlist: Thiếu playlist_frame, hàm set_original_playlist hoặc playlist_list không hợp lệ.")
            messagebox.showerror("Lỗi", "Không thể làm mới danh sách phát do lỗi cấu hình.", parent=self.parent)
            return

        # --- Xóa và Chuẩn bị Playlist Mới ---
        print("Xóa playlist cũ và chuẩn bị cập nhật...")
        playlist_list.clear() # Xóa danh sách nội bộ cũ

        # --- Quét Lại File Nhạc (Logic tương tự choose_folder) ---
        music_files_paths = []
        print("Bắt đầu quét lại file nhạc/video...")
        try:
            for root, _, files in os.walk(current_folder):
                for file in files:
                    if file.lower().endswith(SUPPORTED_FORMATS):
                        try:
                            file_path = os.path.join(root, file)
                            if os.path.isfile(file_path) and os.access(file_path, os.R_OK):
                                music_files_paths.append(file_path)
                        except Exception as file_err:
                             logging.warning(f"Lỗi khi xử lý file '{file}' trong quá trình làm mới: {file_err}")
        except Exception as e:
             logging.exception(f"Lỗi khi quét lại thư mục: {current_folder}")
             messagebox.showerror("Lỗi Quét Thư Mục", f"Không thể quét lại thư mục:\n{e}", parent=self.parent)
             return

        print(f"Tìm thấy {len(music_files_paths)} file sau khi làm mới.")

        # --- Sắp xếp và Cập nhật Playlist ---
        music_files_paths.sort(key=lambda path: Path(path).name.lower())
        print("Đã sắp xếp danh sách file.")

        print("Cập nhật playlist nội bộ và giao diện...")
        playlist_list.extend(music_files_paths) # Cập nhật danh sách nội bộ
        playlist_frame.set_original_playlist(music_files_paths) # Cập nhật giao diện

        # Reset ô tìm kiếm nếu có nội dung
        if hasattr(playlist_frame, 'search_entry'):
            playlist_frame.search_entry.delete(0, tk.END)

        print(f"--- Làm mới playlist hoàn tất ({len(playlist_list)} mục) ---")
        # Có thể thêm thông báo thành công nếu muốn
        # self.parent.control_bar.show_notification("🔄 Đã làm mới danh sách phát") # Gọi qua control_bar nếu có hàm show_notification
    def prompt_download(self):
        print("--- Bắt đầu quy trình tải nhạc ---")
        current_folder = getattr(self.parent, 'current_folder', None)

        if not current_folder:
            print("Thư mục chưa được chọn, yêu cầu chọn thư mục...")
            self.choose_folder()
            current_folder = getattr(self.parent, 'current_folder', None)
            if not current_folder:
                print("Vẫn chưa chọn thư mục, hủy tải.")
                return

        print(f"Thư mục hiện tại để tải về: {current_folder}")
        search_query = simpledialog.askstring(
            "Download Music", "Nhập tên bài hát hoặc link Spotify:", parent=self.parent
        )
        if search_query:
            search_query = search_query.strip()
            if not search_query:
                 print("Người dùng nhập chuỗi rỗng.")
                 return

            print(f"Người dùng nhập: '{search_query}'")
            logging.info(f"Yêu cầu tải: {search_query}")

            if not self.sp:
                 print("LỖI: Spotipy chưa được khởi tạo, không thể tìm kiếm/tải.")
                 logging.error("Spotipy chưa được khởi tạo trong prompt_download.")
                 messagebox.showerror("Lỗi Spotipy", "Spotipy chưa sẵn sàng. Không thể tải nhạc.", parent=self.parent)
                 return

            print("Tạo luồng (thread) để chạy _run_spotdl_with_live_output...")
            # Clear output cũ và bắt đầu chạy thread mới
            self.last_spotdl_output_lines = [] # Reset output lưu trữ
            download_thread = threading.Thread(
                target=self._run_spotdl_with_live_output, # Gọi hàm mới chạy Popen
                args=(search_query, self.result_queue),
                daemon=True # Thoát cùng chương trình chính
            )
            download_thread.start()
            print("Đã bắt đầu luồng download. Theo dõi output và chờ kết quả...")
            # Thông báo cho người dùng (tùy chọn)
            messagebox.showinfo("Đang Tải", f"Đang xử lý '{search_query[:50]}...'\nTheo dõi terminal để xem tiến trình.", parent=self.parent)
            # Bắt đầu kiểm tra queue định kỳ
            self.parent.after(100, self.check_download_result)
        else:
            print("Người dùng đã hủy nhập.")
        print("--- Kết thúc prompt_download ---")

    def _read_subprocess_output(self, stream, queue):
        """Đọc từng dòng từ stream và đưa vào queue. Chạy trong thread riêng."""
        print("[_read_subprocess_output] Luồng đọc bắt đầu.")
        try:
            # iter(stream.readline, '') đọc từng dòng cho đến khi stream đóng (process kết thúc)
            for line in iter(stream.readline, ''):
                # Gửi dòng output về luồng chính qua queue
                queue.put({"type": "output", "line": line.strip()})
        except Exception as e:
             # Gửi lỗi nếu có vấn đề khi đọc stream
             logging.exception("Lỗi trong luồng đọc output subprocess")
             try:
                 queue.put({"type": "error", "line": f"Lỗi đọc output: {e}"})
             except Exception: # Nếu queue cũng lỗi thì chịu
                  pass
        finally:
            # Đảm bảo stream được đóng khi kết thúc
            try:
                stream.close()
            except Exception as close_err:
                logging.error(f"Lỗi khi đóng stream: {close_err}")
            print("[_read_subprocess_output] Luồng đọc kết thúc.")


    def _run_spotdl_with_live_output(self, query_or_url, result_queue):
        """
        Chạy spotdl bằng Popen, đọc output live và gửi kết quả cuối cùng vào queue.
        Chạy trong một thread riêng.
        """
        print(f"--- [Thread] Bắt đầu _run_spotdl_with_live_output cho: '{query_or_url}' ---")
        process = None
        reader_thread = None
        full_final_path = None
        return_code = -1
        final_error = None
        stdout_capture = [] # Lưu toàn bộ output để tìm file sau

        current_folder = getattr(self.parent, 'current_folder', '.') # Lấy thư mục hiện tại an toàn
        if not os.path.isdir(current_folder):
             final_error = f"Thư mục tải về không hợp lệ: {current_folder}"
             print(f"[Thread] {final_error}")
             result_queue.put({"type": "done", "status": "error", "message": final_error, "returncode": -1})
             return


        try:
            python_executable = sys.executable
            print(f"[Thread] Sử dụng Python executable: {python_executable}")

            command_base = [python_executable, "-m", "spotdl"]
            # Thêm các tùy chọn bạn muốn cho spotdl
            command_options = [
                "--bitrate", "320k",
                # "--log-level", "INFO", # Để xem thêm output từ spotdl
                # "--output", "{artist} - {title}.{output-ext}" # Tùy chỉnh tên file
            ]
            command = command_base + [query_or_url] + command_options

            log_command_parts = command_base + [shlex.quote(query_or_url)] + command_options
            command_str_for_log = ' '.join(log_command_parts)

            print(f"[Thread] Chuẩn bị chạy lệnh Popen: {' '.join(command)}")
            logging.info(f"Running spotdl command (Popen): {command_str_for_log}")

            # Khởi chạy tiến trình
            process = subprocess.Popen(
                command,
                cwd=current_folder, # Dùng thư mục đã kiểm tra
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Gộp stderr vào stdout
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1 # Line-buffered
            )

            # Tạo và bắt đầu luồng đọc output (phải làm sau khi Popen chạy)
            reader_thread = threading.Thread(
                target=self._read_subprocess_output,
                args=(process.stdout, result_queue),
                daemon=True
            )
            reader_thread.start()
            print("[Thread] Đã bắt đầu luồng đọc output.")

            # Chờ tiến trình kết thúc
            print("[Thread] Đang chờ tiến trình spotdl kết thúc...")
            # Có thể thêm timeout nếu muốn: process.wait(timeout=300)
            return_code = process.wait()
            print(f"[Thread] Tiến trình spotdl đã kết thúc với mã: {return_code}")

            # Chờ luồng đọc kết thúc để đảm bảo đọc hết output
            if reader_thread:
                 print("[Thread] Đang chờ luồng đọc output kết thúc...")
                 reader_thread.join(timeout=5)
                 if reader_thread.is_alive(): print("[Thread] Cảnh báo: Luồng đọc output không kết thúc kịp thời.")
                 else: print("[Thread] Luồng đọc output đã kết thúc.")


            # --- Xử lý kết quả ---
            # Lấy output đã lưu từ queue (cần sửa check_download_result để làm điều này)
            # Tạm thời, chúng ta sẽ tìm file dựa trên việc quét lại thư mục
            # hoặc cần sửa để lấy output đã lưu trong self.last_spotdl_output_lines

            if return_code == 0:
                print("[Thread] spotdl thành công (return code 0). Tìm file đã tải...")
                # Gọi hàm tìm file (truyền vào output đã lưu nếu có, hoặc title)
                # Giả sử last_spotdl_output_lines được cập nhật đúng bởi check_download_result
                stdout_str = "\n".join(self.last_spotdl_output_lines)
                full_final_path = self.find_downloaded_file_from_output(stdout_str, query_or_url) # Truyền query gốc nếu title ko chắc chắn

                if not full_final_path:
                     print("[Thread] Không tìm thấy file từ output đã lưu. Thử quét thư mục...")
                     # Fallback: Tìm file mới nhất trong thư mục (cần cẩn thận)
                     try:
                          files = [os.path.join(current_folder, f) for f in os.listdir(current_folder) if f.lower().endswith(('.mp3', '.m4a', '.flac', '.ogg', '.opus'))]
                          if files:
                               latest_file = max(files, key=os.path.getctime)
                               print(f"[Thread] Tìm thấy file mới nhất (fallback): {latest_file}")
                               # Có thể thêm kiểm tra thời gian tạo file để chắc chắn hơn
                               full_final_path = latest_file
                          else:
                               final_error = "Spotdl chạy xong nhưng không tìm thấy file mp3/audio nào trong thư mục."
                     except Exception as scan_err:
                          final_error = f"Lỗi khi quét thư mục tìm file fallback: {scan_err}"

                # Kiểm tra lại lần nữa
                if not full_final_path and not final_error:
                     final_error = "Spotdl chạy xong nhưng không xác định được file đã tải."

            else: # return_code != 0
                final_error = f"Spotdl thất bại với mã lỗi {return_code}."
                logging.error(final_error + f" (Query: {query_or_url})")


        except FileNotFoundError:
             final_error = f"Lỗi FileNotFoundError: Không tìm thấy '{python_executable}'."
             print(f"[Thread] {final_error}")
             logging.error(final_error)
             return_code = 127

        except Exception as e:
             final_error = f"Lỗi Exception khi chạy Popen/spotdl: {e}"
             print(f"[Thread] {final_error}")
             logging.exception(final_error)
             if process: return_code = process.poll() if process.poll() is not None else -1
             else: return_code = -1

        finally:
            # --- Gửi kết quả cuối cùng vào Queue ---
            result_data = {"type": "done", "returncode": return_code}
            if full_final_path and not final_error: # Ưu tiên thành công nếu có file
                result_data["status"] = "success"
                result_data["filepath"] = full_final_path
            else:
                result_data["status"] = "error"
                result_data["message"] = final_error if final_error else "Lỗi không xác định sau khi chạy spotdl."

            result_queue.put(result_data)
            print(f"--- [Thread] Kết thúc _run_spotdl_with_live_output cho: '{query_or_url}' ---")


    def check_download_result(self):
        """Kiểm tra queue từ luồng chính Tkinter và cập nhật UI."""
        try:
            while True: # Xử lý hết queue
                 result = self.result_queue.get_nowait()
                 msg_type = result.get("type")

                 if msg_type == "output":
                     line = result.get("line", "")
                     print(f"SPOTDL_LIVE: {line}") # In ra terminal
                     # --- CẬP NHẬT GUI LIVE OUTPUT (VÍ DỤ) ---
                     # if hasattr(self.parent, 'download_status_label'):
                     #    self.parent.download_status_label.configure(text=line)
                     # elif hasattr(self.parent, 'download_output_textbox'):
                     #    self.parent.download_output_textbox.insert(tk.END, line + "\n")
                     #    self.parent.download_output_textbox.see(tk.END) # Cuộn xuống cuối
                     # -----------------------------------------
                     # Lưu lại các dòng output (nếu cần cho việc tìm file sau)
                     self.last_spotdl_output_lines.append(line)
                     if len(self.last_spotdl_output_lines) > 100: # Giới hạn bộ nhớ
                          self.last_spotdl_output_lines.pop(0)

                 elif msg_type == "error": # Lỗi từ luồng đọc
                      error_line = result.get("line", "Lỗi không rõ từ luồng đọc")
                      print(f"--- LỖI LUỒNG ĐỌC OUTPUT: {error_line} ---")
                      logging.error(f"Lỗi luồng đọc output: {error_line}")

                 elif msg_type == "done":
                     status = result.get("status")
                     returncode = result.get("returncode")
                     print(f"--- KẾT QUẢ CUỐI CÙNG (Từ Thread) ---")
                     print(f"Status: {status}, Return Code: {returncode}")

                     if status == "error":
                         error_msg = result.get("message", "Lỗi không rõ")
                         print(f"Lỗi: {error_msg}")
                         logging.error(f"Lỗi tải nhạc từ thread (done): {error_msg}")
                         messagebox.showerror("Lỗi Tải Nhạc", error_msg, parent=self.parent)

                     elif status == "success":
                         downloaded_file_path = result.get("filepath")
                         print(f"Thành công: {downloaded_file_path}")
                         logging.info(f"Tải thành công từ thread (done): {downloaded_file_path}")

                         # Cập nhật Playlist UI
                         playlist_list = getattr(self.parent, 'playlist', None)
                         playlist_frame = getattr(self.parent, 'playlist_frame', None)
                         if isinstance(playlist_list, list) and playlist_frame and hasattr(playlist_frame, 'song_list'):
                             print(f"Chuẩn bị thêm file '{downloaded_file_path}' vào playlist...")
                             playlist_list.append(downloaded_file_path)
                             file_stem = Path(downloaded_file_path).stem
                             print(f"Thêm '{file_stem}' vào Listbox UI...")
                             playlist_frame.song_list.insert("end", f"• {file_stem}")
                             logging.info("Saved at %s", downloaded_file_path)
                             print(f"----> Tải xuống hoàn tất và đã cập nhật playlist cho: {file_stem}!")
                             messagebox.showinfo("Tải Thành Công", f"Đã tải xong: {file_stem}", parent=self.parent)
                         else:
                              logging.error("check_download_result: Không thể cập nhật UI do thiếu đối tượng.")
                              print("LỖI: Không thể cập nhật playlist UI sau khi tải.")
                              messagebox.showwarning("Lỗi Cập Nhật UI", "Đã tải xong nhưng không thể cập nhật danh sách phát.", parent=self.parent)

                     # Dừng kiểm tra queue vì đã xong việc download này
                     print("--- Đã xử lý kết quả 'done', dừng kiểm tra queue cho lần tải này ---")
                     return # <--- Dừng gọi after

        except Empty:
            # Queue rỗng, kiểm tra lại sau nếu chưa nhận được tín hiệu 'done'
            # (Cần cơ chế phức tạp hơn để biết thread chính xác đã xong chưa nếu chỉ dựa vào Empty)
            # Tạm thời vẫn gọi lại after, nhưng hàm done sẽ return để dừng nó.
            self.parent.after(200, self.check_download_result)
            return

        except Exception as e:
            print(f"Lỗi nghiêm trọng khi kiểm tra kết quả download: {e}")
            logging.exception("Lỗi trong check_download_result")
            # Xem xét có nên dừng hẳn hay không
            # self.parent.after(200, self.check_download_result)


    # Hàm tìm file (phiên bản đã sửa)
    def find_downloaded_file_from_output(self, spotdl_stdout_str, expected_title):
        print("[find_downloaded_file] Bắt đầu tìm file từ output string...")
        if not spotdl_stdout_str: print("[find_downloaded_file] Output rỗng."); return None
        # Ưu tiên pattern "Downloaded"
        downloaded_pattern = re.compile(r'Downloaded\s+"([^"]+)"\s*:', re.IGNORECASE)
        # Pattern "Saved"
        saved_pattern = re.compile(r"Saved:\s*['\"]?(.*?)['\"]?\s*$", re.IGNORECASE)
        # Pattern đường dẫn file trực tiếp
        path_pattern = re.compile(r"^(?:[a-zA-Z]:\\|/).*\.(?:mp3|m4a|opus|flac|ogg)$")

        found_path = None
        lines = spotdl_stdout_str.splitlines()
        potential_files_from_output = []

        for line in lines:
            line = line.strip()
            match_downloaded = downloaded_pattern.search(line)
            if match_downloaded:
                filename_base = match_downloaded.group(1).strip()
                print(f"[find_downloaded_file] Tìm thấy pattern 'Downloaded': '{filename_base}'")
                for ext in [".mp3", ".m4a", ".flac", ".ogg", ".opus"]: potential_files_from_output.append(f"{filename_base}{ext}")
                continue # Đã xử lý, không cần check pattern khác cho dòng này

            match_saved = saved_pattern.search(line)
            if match_saved:
                 potential_file = match_saved.group(1).strip()
                 print(f"[find_downloaded_file] Tìm thấy pattern 'Saved': '{potential_file}'")
                 potential_files_from_output.append(potential_file)
                 continue

            match_path = path_pattern.match(line)
            if match_path:
                 potential_file = line
                 print(f"[find_downloaded_file] Tìm thấy pattern đường dẫn file: '{potential_file}'")
                 potential_files_from_output.append(potential_file)
                 continue

        print(f"[find_downloaded_file] Các tên file tiềm năng từ output: {potential_files_from_output}")
        current_folder = getattr(self.parent, 'current_folder', '.')
        for potential_filename in potential_files_from_output:
             full_path = None
             # Xử lý đường dẫn tuyệt đối / tương đối
             if os.path.isabs(potential_filename):
                  # Kiểm tra xem có nằm trong thư mục đích không
                  # Dùng commonpath để xử lý các trường hợp như /a/b và /a/b/c
                  try:
                     common = os.path.commonpath([current_folder, potential_filename])
                     if common == os.path.normpath(current_folder):
                          full_path = potential_filename
                     else:
                          print(f"[find_downloaded_file] Cảnh báo: Đường dẫn tuyệt đối '{potential_filename}' không nằm trong '{current_folder}'. Bỏ qua.")
                          continue
                  except ValueError: # Nếu không có đường dẫn chung (ví dụ khác ổ đĩa trên Windows)
                       print(f"[find_downloaded_file] Cảnh báo: Không thể so sánh đường dẫn tuyệt đối '{potential_filename}' với '{current_folder}'. Bỏ qua.")
                       continue
             else:
                  # Ghép với thư mục hiện tại
                  full_path = os.path.join(current_folder, potential_filename)

             # Kiểm tra sự tồn tại của file
             print(f"[find_downloaded_file] Đang kiểm tra sự tồn tại của: {full_path}")
             if full_path and os.path.exists(full_path) and os.path.isfile(full_path): # Thêm isfile
                 print(f"[find_downloaded_file] ----> Xác nhận file tồn tại: {full_path}")
                 found_path = full_path
                 break # Ưu tiên file đầu tiên tìm thấy và tồn tại

        if not found_path:
            print("[find_downloaded_file] Không tìm thấy file hợp lệ nào từ output hoặc file không tồn tại.")

        return found_path
    def slider_offset_changed_topbar(self, value):
        """Xử lý sự kiện slider offset thay đổi ngay trong TopBar"""
        # Cập nhật label hiển thị (label này giờ thuộc TopBar)
        self.current_offset_var.set(f"{value:.1f}s")
        # Gọi hàm trong MusicPlayer để áp dụng offset mới
        # Đảm bảo self.parent trỏ đúng đến MusicPlayer instance
        if hasattr(self.parent, 'update_current_offset'):
             # self.parent ở đây chính là MusicPlayer instance đã được truyền vào khi khởi tạo TopBar
             self.parent.update_current_offset(value)
        else:
             print("Lỗi: self.parent không có hàm update_current_offset")
             # Sử dụng logging nếu bạn đã cấu hình nó
             if 'logging' in globals():
                 logging.error("Lỗi: self.parent trong TopBar không có hàm update_current_offset")