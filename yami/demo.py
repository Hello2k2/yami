from spotdl import Spotdl
import subprocess

# Kiểm tra FFmpeg
def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("FFmpeg không được cài đặt hoặc không tìm thấy! Vui lòng cài FFmpeg.")
        return False

# Khởi tạo Spotdl với client_id và client_secret
client_id = "5f573c9620494bae87890c0f08a60293"
client_secret = "212476d9b0f3472eaa762d90b19b0ba8"
client = Spotdl(client_id=client_id, client_secret=client_secret)

# Nhập tên bài hát
song_name = input("Nhập tên bài hát: ")

# Kiểm tra FFmpeg trước khi tải
if not check_ffmpeg():
    exit(1)

# Tìm kiếm bài hát
songs = client.search([song_name])

if not songs:
    print("Không tìm thấy bài hát!")
else:
    # Lấy URL của bài hát đầu tiên
    song_url = songs[0]
    
    # In thông tin bài hát (dùng tên người dùng nhập)
    print(f"Đang tải: {song_name}")
    
    # Tải bài hát
    try:
        client.download(song_url)
        print("Tải xuống hoàn tất!")
    except Exception as e:
        print(f"Lỗi khi tải: {str(e)}")