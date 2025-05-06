# -*- coding: utf-8 -*-
# yami/stream_server.py

import os
import threading
import logging
from flask import Flask, send_file, abort, request, Response # Thêm Response và request
from werkzeug.serving import make_server
from urllib.parse import unquote, quote # Thêm quote và unquote để xử lý đường dẫn

# --- Cấu hình Logging (giữ nguyên hoặc tùy chỉnh) ---
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
cli = logging.getLogger('flask.cli')
cli.setLevel(logging.ERROR)
app_log = logging.getLogger('flask.app')
# Đặt level INFO để thấy log phục vụ file, hoặc WARNING/ERROR để ít log hơn
app_log.setLevel(logging.INFO)

# --- Khởi tạo Flask App ---
flask_app = Flask(__name__)

# --- Biến lưu trữ tham chiếu đến Yami App ---
# Sẽ được set từ music.py khi khởi động server
yami_app_instance = None

# --- Biến lưu trữ đối tượng server để có thể dừng ---
flask_server_instance = None
server_lock = threading.Lock()

# === Hàm tiện ích để lấy đường dẫn file từ Yami ===
def _get_filepath_from_request():
    """Lấy đường dẫn file hợp lệ từ tham số URL (?index= hoặc ?path=)."""
    if not yami_app_instance:
        app_log.error("Yami application instance not set in stream_server.")
        abort(500, description="Server configuration error: Yami instance missing.")

    file_path = None
    file_index_str = request.args.get('index')
    url_encoded_path = request.args.get('path')

    if file_index_str is not None:
        try:
            file_index = int(file_index_str)
            # Giả sử Yami app có hàm này để lấy path từ index an toàn
            if hasattr(yami_app_instance, 'get_path_from_playlist'):
                file_path = yami_app_instance.get_path_from_playlist(file_index)
                if not file_path:
                    app_log.warning(f"Index {file_index} not found in Yami playlist.")
                    abort(404, description=f"Index {file_index} not found.")
                app_log.info(f"Request file by index {file_index} -> path: {file_path}")
            else:
                 app_log.error("Yami instance missing 'get_path_from_playlist' method.")
                 abort(500, description="Server configuration error.")
        except (ValueError, IndexError):
            app_log.warning(f"Invalid index parameter: {file_index_str}")
            abort(400, description="Invalid 'index' parameter.") # Bad request

    elif url_encoded_path is not None:
        try:
            # Decode đường dẫn từ URL (%20 -> space, %2F -> /, etc.)
            file_path = unquote(url_encoded_path)
            app_log.info(f"Request file by path param (decoded): {file_path}")

            # --- KIỂM TRA BẢO MẬT QUAN TRỌNG ---
            # Đảm bảo file nằm trong thư mục media được phép của Yami
            allowed_folder = getattr(yami_app_instance, 'current_folder', None)
            if not allowed_folder:
                 app_log.error("Cannot verify path safety: Yami current_folder not set.")
                 abort(500, description="Server configuration error: Media folder not set.")

            # Chuẩn hóa đường dẫn để so sánh an toàn
            abs_allowed_folder = os.path.abspath(allowed_folder)
            abs_file_path = os.path.abspath(file_path)

            # commonprefix không đủ an toàn, dùng startswith trên path đã chuẩn hóa
            if os.path.commonpath([abs_allowed_folder, abs_file_path]) != abs_allowed_folder:
            # Hoặc an toàn hơn: if not abs_file_path.startswith(abs_allowed_folder + os.sep):
                 app_log.error(f"Forbidden path access attempt: {file_path} (not inside {abs_allowed_folder})")
                 abort(403, description="Access to this file path is forbidden.") # Forbidden
            # --- KẾT THÚC KIỂM TRA BẢO MẬT ---

        except Exception as path_err:
            app_log.error(f"Error decoding/validating path parameter: {path_err}")
            abort(400, description="Invalid 'path' parameter.")
    else:
        app_log.warning("Request missing 'index' or 'path' parameter.")
        abort(400, description="Missing 'index' or 'path' parameter.")

    # Kiểm tra file tồn tại và quyền đọc cuối cùng
    if not file_path:
        abort(404, description="Could not determine file path.")
    if not os.path.exists(file_path):
        app_log.error(f"File does not exist: {file_path}")
        abort(404, description=f"Media file not found: {os.path.basename(file_path)}")
    if not os.access(file_path, os.R_OK):
         app_log.error(f"Permission denied for file: {file_path}")
         abort(403, description="Permission denied to read the media file.")

    return file_path


# === Route chính để phục vụ file media ===
# Có thể dùng một route chung hoặc tách riêng nếu muốn xử lý khác nhau
@flask_app.route('/file')
def serve_media_file():
    """Phục vụ file media (audio/video) dựa trên tham số 'index' hoặc 'path'."""
    try:
        file_path = _get_filepath_from_request() # Lấy đường dẫn an toàn
        app_log.info(f"Attempting to send file: {file_path}")

        # send_file hỗ trợ Range Requests, MIME type, caching headers
        response = send_file(
            file_path,
            conditional=True, # Bật hỗ trợ cache (ETag, etc.) - quan trọng cho performance
            as_attachment=False, # Gợi ý trình duyệt hiển thị inline
            download_name=os.path.basename(file_path) # Đặt tên file nếu user tải về
        )
        # Đảm bảo header Accept-Ranges được đặt (send_file thường tự làm)
        response.headers['Accept-Ranges'] = 'bytes'
        app_log.info(f"Successfully sending headers: {response.headers}")
        return response

    except Exception as e:
        # Bắt các lỗi từ _get_filepath_from_request hoặc send_file
        # abort() sẽ tự raise HTTPException, không cần bắt ở đây
        # Chỉ bắt các lỗi không mong muốn khác
        app_log.exception(f"Unexpected error serving file request: {e}")
        abort(500, description="Internal server error.")


# === Hàm để truyền Yami instance vào ===
def set_yami_instance(app_instance):
    """Lưu tham chiếu đến đối tượng Yami chính."""
    global yami_app_instance
    yami_app_instance = app_instance
    if yami_app_instance:
         app_log.info("Yami application instance registered with stream_server.")
    else:
         app_log.warning("Yami application instance set to None.")


# === Hàm khởi động Flask Server trong Thread ===
def start_flask_server_thread(host='0.0.0.0', port=8080):
    """Khởi động Flask server dùng Werkzeug trong một luồng riêng biệt."""
    global flask_server_instance
    with server_lock:
        if flask_server_instance is not None and flask_server_instance.is_serving(): # Kiểm tra chính xác hơn
             print("Flask server already running.")
             app_log.warning("Attempted to start Flask server thread while already serving.")
             return

        try:
            print(f"Starting Flask file server on http://{host}:{port} ...")
            app_log.info(f"Starting Flask server on {host}:{port}")
            # Lưu instance để có thể gọi shutdown()
            flask_server_instance = make_server(host, port, flask_app, threaded=True) # threaded=True tốt cho I/O-bound như gửi file
            print(f"Flask server instance created. Serving forever in background thread...")
            # Serve forever sẽ block luồng này
            flask_server_instance.serve_forever()
            # Dòng này chỉ được thực thi sau khi server dừng
            print("Flask server has stopped serving.")
            app_log.info("Flask server has stopped serving.")

        except OSError as e:
            print(f"!!!!!!!! ERROR starting Flask server on port {port}: {e} !!!!!!!!")
            app_log.error(f"OSError starting Flask server on port {port}: {e}")
            print("Port may be in use or permission denied.")
            flask_server_instance = None # Reset nếu lỗi
        except Exception as e:
            print(f"!!!!!!!! UNEXPECTED ERROR starting Flask server: {e} !!!!!!!!")
            app_log.exception(f"Unexpected error starting Flask server: {e}")
            flask_server_instance = None # Reset nếu lỗi


# === Hàm dừng Flask Server ===
def stop_flask_server():
    """Yêu cầu Werkzeug server dừng lại một cách an toàn."""
    global flask_server_instance
    stopped = False
    with server_lock:
        if flask_server_instance:
            print("Attempting to stop Flask server...")
            app_log.info("Attempting to stop Flask server...")
            try:
                flask_server_instance.shutdown() # Yêu cầu dừng serve_forever
                stopped = True
                # Không nên đặt instance = None ngay lập tức ở đây,
                # hãy để serve_forever kết thúc và reset trong luồng của nó hoặc kiểm tra is_serving()
            except Exception as e:
                print(f"Error during Flask server shutdown: {e}")
                app_log.exception(f"Error during Flask server shutdown: {e}")
        else:
            print("Flask server not running or already stopped.")
            app_log.info("Stop request ignored, Flask server not running.")

    if stopped:
         print("Flask server shutdown requested successfully.")
         app_log.info("Flask server shutdown requested successfully.")


# --- Code chạy thử nghiệm (có thể bỏ đi khi tích hợp) ---
if __name__ == '__main__':
    print("Running stream_server.py directly for testing...")
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s')

    # --- Mô phỏng Yami App instance và playlist ---
    class MockYami:
        def __init__(self):
            # !!! THAY ĐỔI THƯ MỤC NÀY thành thư mục chứa nhạc/video của bạn !!!
            self.current_folder = "/media/phattan/demo1/music"
            self.playlist = []
            if os.path.isdir(self.current_folder):
                 print(f"Scanning mock folder: {self.current_folder}")
                 try:
                      # Quét các file hỗ trợ đơn giản
                      supported_ext = ('.mp3', '.flac', '.wav', '.ogg', '.opus', '.m4a', '.mp4', '.mkv', '.avi')
                      for fname in os.listdir(self.current_folder):
                           if fname.lower().endswith(supported_ext):
                                self.playlist.append(os.path.join(self.current_folder, fname))
                      print(f"Found {len(self.playlist)} media files.")
                 except Exception as scan_err:
                      print(f"Error scanning mock folder: {scan_err}")
            else:
                 print(f"WARNING: Mock folder not found: {self.current_folder}")
                 print("Please edit stream_server.py and set self.current_folder correctly for testing.")

        def get_path_from_playlist(self, index):
            if 0 <= index < len(self.playlist):
                return self.playlist[index]
            return None

    mock_yami = MockYami()
    set_yami_instance(mock_yami) # Đăng ký instance giả lập

    # --- Khởi động server ---
    flask_thread = None
    try:
        print("\nStarting Flask server for testing in background thread.")
        flask_thread = threading.Thread(target=start_flask_server_thread, args=('0.0.0.0', 8080), daemon=True)
        flask_thread.start()
        print("Server thread started.")
        if mock_yami.playlist:
             test_index = 0
             test_path_encoded = quote(mock_yami.playlist[test_index]) # Mã hóa đường dẫn cho URL
             print("\n--- Example URLs to test ---")
             print(f"By Index: http://<your-lan-ip>:8080/file?index={test_index}")
             print(f"By Path:  http://<your-lan-ip>:8080/file?path={test_path_encoded}")
             print("----------------------------")
        else:
             print("\nNo media files found in mock folder to generate test URLs.")

        print("(Replace <your-lan-ip> with the actual IP of this machine)")
        input("Press Enter to stop the server...\n")
    except KeyboardInterrupt:
        print("\nCtrl+C detected.")
    finally:
        stop_flask_server()
        if flask_thread and flask_thread.is_alive():
             print("Waiting for server thread to stop...")
             flask_thread.join(timeout=2)
        print("Test finished.")