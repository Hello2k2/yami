# lyrics_handler.py
from pathlib import Path
import shlex
import os
import subprocess
import hashlib
import re
import logging
import lyricsgenius
import mutagen
import time # Thêm time để chuyển đổi thời gian LRC
import sys
class LyricsHandler:
    def __init__(self, genius_api_key, mxlrc_path=None):
        self.genius = lyricsgenius.Genius(genius_api_key)
        self.genius.skip_non_songs = True
        self.genius.excluded_terms = ["(Remix)", "(Live)"]
        self.cache_dir = os.path.join(os.getcwd(), "lyrics_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.mxlrc_path = mxlrc_path
        # Pattern để khớp với dòng thời gian LRC [mm:ss.xx] hoặc [mm:ss]
        self.lrc_time_pattern = re.compile(r"\[(\d{2,}):(\d{2})(?:[.,](\d{2,3}))?\](.*)")
        # Pattern để lấy đường dẫn từ output "Lyrics saved: ..." của mxlrc
        self.mxlrc_saved_pattern = re.compile(r"Lyrics saved:\s*(.*)", re.IGNORECASE)
    # --- HÀM MỚI ĐỂ PARSE LRC ---
    def _try_parse_lrc(self, lrc_path):
        """Thử đọc và parse file LRC từ đường dẫn được cung cấp.
        Trả về dữ liệu đã parse (list of tuples) nếu thành công,
        ngược lại trả về None.
        """
        if not os.path.exists(lrc_path) or not os.path.isfile(lrc_path):
             logging.warning(f"_try_parse_lrc: Đường dẫn không tồn tại hoặc không phải file: {lrc_path}")
             return None
        try:
            # Mở và đọc nội dung file LRC với encoding utf-8
            with open(lrc_path, "r", encoding="utf-8") as f:
                lrc_content = f.read()

            # Gọi hàm parse_lrc_content đã có để xử lý nội dung
            parsed_lrc = self.parse_lrc_content(lrc_content)

            # Kiểm tra xem kết quả parse có hợp lệ không
            if parsed_lrc:
                # logging.debug(f"Parse thành công file LRC: {lrc_path}")
                return parsed_lrc
            else:
                # Trường hợp file có tồn tại nhưng nội dung rỗng hoặc không parse được
                logging.warning(f"File LRC {lrc_path} không parse được (rỗng hoặc sai định dạng).")
                return None
        except Exception as e:
            # Bắt các lỗi khác có thể xảy ra khi đọc file (ví dụ: permission denied)
            logging.error(f"Lỗi khi đọc/parse file LRC {lrc_path}: {e}")
            return None
    def parse_lrc_content(self, lrc_string):
        """
        Phân tích nội dung chuỗi LRC.
        CHỈ áp dụng offset nếu có thẻ [offset:...] trong file.
        (Đã xóa bỏ logic kiểm tra lặp dòng)
        """
        print("\n--- DEBUG: Bắt đầu parse_lrc_content ---")
        lyrics_data = []
        if not isinstance(lrc_string, str) or not lrc_string.strip():
             print("DEBUG parse_lrc: Input string rỗng hoặc không phải string.")
             return lyrics_data

        lines = lrc_string.strip().splitlines()
        print(f"DEBUG parse_lrc: Số dòng đọc được: {len(lines)}")

        file_offset_ms = 0
        offset_pattern = re.compile(r"\[offset:\s*([+-]?\d+)\s*\]", re.IGNORECASE)

        # KHÔNG CẦN processed_lines nữa
        # processed_lines = []
        line_counter = 0
        for line in lines:
            line_counter += 1
            line = line.strip()
            if not line: continue

            offset_match = offset_pattern.match(line)
            if offset_match:
                try:
                    file_offset_ms = int(offset_match.group(1))
                    logging.info(f"Tìm thấy thẻ offset trong file LRC: {file_offset_ms}ms")
                except ValueError:
                    logging.warning(f"Lỗi parse offset tag: {line}")
                continue

            time_matches = list(self.lrc_time_pattern.finditer(line))
            if not time_matches:
                 continue

            # Lấy text từ group(4) của kết quả khớp cuối cùng
            try:
                lyric_text = time_matches[-1].group(4).strip()
                # Vẫn kiểm tra xem có text không, nhưng không cần line_key nữa
                if not lyric_text: continue
                # line_key = lyric_text # Bỏ
            except IndexError:
                 continue

            # --- BỎ HOÀN TOÀN KHỐI KIỂM TRA LẶP DÒNG ---
            # if line_key in processed_lines:
            #      continue
            # processed_lines.append(line_key)
            # -------------------------------------------

            # Xử lý TẤT CẢ các timestamp tìm được trên dòng cho lyric_text này
            for match in time_matches:
                try:
                    minutes = int(match.group(1))
                    seconds = int(match.group(2))
                    milli_or_centi = match.group(3)

                    if milli_or_centi:
                        milli_or_centi_str = milli_or_centi.strip()
                        if len(milli_or_centi_str) == 2: milliseconds = int(milli_or_centi_str) * 10
                        elif len(milli_or_centi_str) == 3: milliseconds = int(milli_or_centi_str)
                        else: milliseconds = 0
                    else: milliseconds = 0

                    # Tính thời gian gốc (giây) CÓ cộng offset từ thẻ [offset:...]
                    raw_total_seconds = minutes * 60 + seconds + (milliseconds + file_offset_ms) / 1000.0
                    raw_total_seconds = max(0, raw_total_seconds)

                    # Thêm tất cả các cặp (thời gian, lời)
                    lyrics_data.append((raw_total_seconds, lyric_text))

                except ValueError as e:
                    logging.warning(f"Bỏ qua timestamp lỗi '{match.group(0)}' trong dòng '{line}': {e}")
                    continue

        # Sắp xếp theo thời gian gốc
        try:
             lyrics_data.sort(key=lambda item: item[0])
        except Exception as sort_err:
             print(f"DEBUG parse_lrc: Lỗi khi sắp xếp: {sort_err}")

        final_line_count = len(lyrics_data)
        # Giờ số dòng sẽ nhiều hơn nếu có các dòng lặp lại
        print(f"--- DEBUG: Kết thúc parse_lrc_content, trả về {final_line_count} cặp (thời gian, lời) ---")
        logging.info(f"Parse xong LRC, có {final_line_count} cặp (thời gian, lời).")
        return lyrics_data

    # --- SỬA ĐỔI HÀM get_lyrics_for_song ---
    def get_lyrics_for_song(self, filepath, title=None, artist=None):
        """Tìm kiếm lời bài hát theo thứ tự ưu tiên:
           1. Cache LRC (.lrc trong lyrics_cache)
           2. Cache TXT (Genius .txt trong lyrics_cache)
           3. Tìm Online (LRC): MxLRC / SyncedLyrics Fallback
           4. Tìm Online (TXT): Genius API
        """
        if not filepath:
            return {'type': 'error', 'data': "Đường dẫn file nhạc không hợp lệ."}

        try:
            audio_stem = Path(filepath).stem
        except Exception as e:
             logging.error(f"Không thể lấy stem từ filepath '{filepath}': {e}")
             return {'type': 'error', 'data': "Lỗi xử lý đường dẫn file nhạc."}

        lrc_result = None
        txt_result = None

        # === Ưu tiên 1: Cache LRC (.lrc trong lyrics_cache) ===
        logging.debug("Kiểm tra cache LRC...")
        cached_lrc_path = os.path.join(self.cache_dir, f"{audio_stem}.lrc")
        if os.path.exists(cached_lrc_path):
            parsed_lrc = self._try_parse_lrc(cached_lrc_path) # Sử dụng hàm trợ giúp đã tạo
            if parsed_lrc:
                print(f"Sử dụng LRC từ cache: {cached_lrc_path}")
                lrc_result = {'type': 'lrc', 'data': parsed_lrc}
        if lrc_result: return lrc_result # Trả về nếu tìm thấy cache LRC

        # --- Cần lấy metadata/tên file sạch nếu phải kiểm tra cache Genius hoặc tìm online ---
        if not title or not artist:
            meta_title, meta_artist = self.get_metadata(filepath)
            title = title or meta_title
            artist = artist or meta_artist
        if not title or not artist:
             guessed_title, guessed_artist = self.guess_title_artist(filepath)
             title = title or guessed_title
             artist = artist or guessed_artist

        cleaned_title = self.clean_title(title or "")
        cleaned_artist = self.clean_artist(artist or "")

        # === Ưu tiên 2: Cache TXT (Genius .txt trong lyrics_cache) ===
        if cleaned_title: # Chỉ check cache txt nếu có title
            logging.debug("Kiểm tra cache TXT (Genius)...")
            cache_key = hashlib.md5(f"{cleaned_title}_{cleaned_artist}".encode('utf-8')).hexdigest()
            cache_path_txt = os.path.join(self.cache_dir, f"{cache_key}.txt")
            if os.path.exists(cache_path_txt):
                try:
                     with open(cache_path_txt, 'r', encoding='utf-8') as f:
                          cached_lyrics = f.read()
                          logging.info(f"Sử dụng TXT từ cache Genius: {cache_path_txt}")
                          print(f"Sử dụng TXT từ cache Genius.")
                          txt_result = {'type': 'txt', 'data': cached_lyrics}
                except Exception as cache_read_err:
                     logging.warning(f"Lỗi đọc cache file TXT {cache_path_txt}: {cache_read_err}")
                     try: os.remove(cache_path_txt) # Xóa cache lỗi
                     except OSError: pass
        if txt_result: return txt_result # Trả về nếu tìm thấy cache TXT

        # === Chỉ tìm online nếu không tìm thấy gì trong cache ===
        print(f"Không tìm thấy lời trong cache. Bắt đầu tìm online cho: Artist='{cleaned_artist}', Title='{cleaned_title}'")

        # === Ưu tiên 3: Tìm Online LRC (MxLRC / SyncedLyrics Fallback) ===
        if cleaned_title:
            # Gọi fetch_with_mxlrc (đã bao gồm fallback SyncedLyrics)
            online_lrc_path = self.fetch_with_mxlrc(cleaned_artist, cleaned_title, audio_stem)
            if online_lrc_path and isinstance(online_lrc_path, str):
                logging.info(f"Tìm thấy LRC online tại: {online_lrc_path}")
                parsed_lrc = self._try_parse_lrc(online_lrc_path)
                if parsed_lrc:
                    print(f"Sử dụng LRC tìm được online từ {online_lrc_path}")
                    lrc_result = {'type': 'lrc', 'data': parsed_lrc}
            else:
                print("Tìm kiếm LRC online (MxLRC/SyncedLyrics) không thành công.")
        else:
             print("Thiếu title, bỏ qua tìm kiếm LRC online.")

        if lrc_result: return lrc_result # Trả về nếu tìm được LRC online

        # === Ưu tiên 4: Tìm Online TXT (Genius API) ===
        if cleaned_title:
            logging.info(f"Tìm kiếm trên Genius cho: {cleaned_title} - {cleaned_artist}")
            genius_lyrics = self.get_lyrics_from_genius(cleaned_title, cleaned_artist)
            if isinstance(genius_lyrics, str):
                 if "Không tìm thấy" in genius_lyrics or "Đã xảy ra lỗi" in genius_lyrics:
                      return {'type': 'error', 'data': genius_lyrics}
                 elif "Bài hát không có lời" in genius_lyrics:
                      return {'type': 'txt', 'data': genius_lyrics}
                 else:
                      print("Sử dụng lời dạng Text từ Genius.")
                      return {'type': 'txt', 'data': genius_lyrics}
            else:
                 return {'type': 'error', 'data': "Lỗi không xác định từ Genius."}
        else:
             # Trường hợp cuối cùng: không tìm thấy gì cả
             logging.warning("Không tìm thấy lời bài hát nào.")
             return {'type': 'error', 'data': "Không tìm thấy lời bài hát."}

    # --- fetch_with_mxlrc cần sửa sau ---
    def _fetch_with_syncedlyrics(self, artist, title, audio_stem):
        """
        Sử dụng 'python3.10 -m syncedlyrics' CLI để tìm và tải file .lrc.
        Trả về đường dẫn đầy đủ tới file .lrc nếu thành công, ngược lại trả về None.
        """
        if not artist or not title or not audio_stem:
            logging.warning("_fetch_with_syncedlyrics: Thiếu thông tin artist, title hoặc audio_stem.")
            return None

        search_term = f"{artist} {title}".strip()
        output_filename = f"{audio_stem}.lrc"
        output_path = os.path.join(self.cache_dir, output_filename)

        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError as e:
                logging.warning(f"Không thể xóa file LRC cũ '{output_path}': {e}")

        try:
            # --- THAY ĐỔI CÁCH XÂY DỰNG LỆNH ---
            # Chỉ định rõ python3.10 và dùng -m
            python_executable = "python3.10" # Hoặc "python" nếu python3.10 là mặc định
            command_list = [
                python_executable, # Chỉ định trình thông dịch Python
                "-m",              # Cờ để chạy module
                "syncedlyrics",    # Tên module
                search_term,
                "-o", output_path,
                "--synced-only"   # Chỉ tìm lời có đồng bộ thời gian (.lrc)
                
            ]

            # ------------------------------------

            command_str_log = ' '.join(shlex.quote(part) for part in command_list) # Log an toàn

            print(f"Đang chạy SyncedLyrics: {command_str_log}") # Debug
            logging.info(f"Running SyncedLyrics command: {command_str_log}")

            # Chạy tiến trình (giữ nguyên)
            result = subprocess.run(
                command_list,
                capture_output=True, text=True,
                encoding='utf-8', errors='replace', timeout=45
            )

            # Xử lý kết quả (giữ nguyên)
            logging.info(f"SyncedLyrics stdout:\n{result.stdout}")
            if result.stderr: logging.warning(f"SyncedLyrics stderr:\n{result.stderr}")

            if result.returncode == 0 and os.path.exists(output_path):
                 logging.info(f"SyncedLyrics thành công, đã lưu file: {output_path}")
                 return output_path
            elif result.returncode == 0 and not os.path.exists(output_path):
                 logging.warning(f"SyncedLyrics chạy xong (code 0) nhưng không tìm thấy file output: {output_path}")
                 return None
            else:
                 logging.error(f"SyncedLyrics lỗi (code {result.returncode}): {result.stderr or result.stdout}")
                 return None

        except FileNotFoundError:
            # Lỗi này giờ có thể là do 'python3.10' không tìm thấy hoặc 'syncedlyrics' chưa cài cho python3.10
            logging.error(f"Lỗi FileNotFoundError: Không tìm thấy '{python_executable}' hoặc module 'syncedlyrics' cho trình thông dịch đó.")
            return None
        except subprocess.TimeoutExpired:
            logging.error("Lỗi timeout khi chạy SyncedLyrics.")
            return None
        except Exception as e:
            logging.exception(f"Lỗi không xác định khi gọi SyncedLyrics: {e}")
            return None

    # --- Sửa đổi hàm fetch_with_mxlrc ---
    # Thêm tham số audio_stem để có thể gọi _fetch_with_syncedlyrics
    def fetch_with_mxlrc(self, artist, title, audio_stem):
        """
        Chạy mxlrc. Nếu thành công, trả về đường dẫn file .lrc.
        Nếu thất bại (timeout hoặc lỗi khác), ghi log lỗi và thử chạy
        _fetch_with_syncedlyrics làm fallback, trả về kết quả của fallback đó.
        """
        if not self.mxlrc_path or not artist or not title: return None
        if not os.path.exists(self.mxlrc_path):
            logging.error(f"MxLRC path không tồn tại: {self.mxlrc_path}")
            # Khi path mxlrc không tồn tại, thử luôn syncedlyrics
            logging.info("MxLRC path không hợp lệ, thử fallback sang SyncedLyrics...")
            return self._fetch_with_syncedlyrics(artist, title, audio_stem)

        os.makedirs(self.cache_dir, exist_ok=True)

        try:
            # Sử dụng artist và title đã được clean (và bỏ dấu ngoặc kép) để tìm kiếm
            # (Lưu ý: Nên clean title/artist trước khi gọi hàm này)
            search_str=f"{artist},{title}"
            mxlrc_path=f"{self.mxlrc_path}"
            cache_dir=f"{self.cache_dir}"
            token="200501593b603a3fdc5c9b4a696389f6589dd988e5a1cf02dfdce1" # Xem xét đưa token ra config
            python_executable = sys.executable
            command_list = [mxlrc_path, "-s", search_str, "-o", cache_dir ,"--token",token]
            command_str_log = ' '.join([mxlrc_path, "-s", shlex.quote(search_str), "-o", cache_dir]) # Log với quote

            print(f"Đang chạy MxLRC: {' '.join(command_list)}") # Debug dùng list gốc
            logging.info(f"Running MxLRC command: {command_str_log}")

            result = subprocess.run(
                command_list, capture_output=True, text=True,
                encoding='utf-8', errors='replace', timeout=30 # Giữ timeout gốc cho mxlrc
            )

            logging.info(f"MxLRC stdout:\n{result.stdout}")
            if result.stderr: # Ghi log stderr nếu có
                 logging.warning(f"MxLRC stderr:\n{result.stderr}")

            if result.returncode != 0:
                 # MxLRC lỗi nhưng không phải timeout/exception -> thử fallback
                 logging.error(f"MxLRC lỗi (code {result.returncode}). Thử fallback sang SyncedLyrics...")
                 return self._fetch_with_syncedlyrics(artist, title, audio_stem)

            # --- Parse output để lấy đường dẫn file (Logic này giữ nguyên) ---
            saved_path = None
            if result.stdout:
                for line in result.stdout.splitlines():
                    match = self.mxlrc_saved_pattern.search(line.strip())
                    if match:
                        path_from_output = match.group(1).strip()
                        # --- Kiểm tra và chuẩn hóa đường dẫn (Giữ nguyên logic kiểm tra path) ---
                        # ... (code kiểm tra isabs, join, exists, isfile) ...
                        if os.path.isabs(path_from_output):
                            if path_from_output.startswith(os.path.abspath(self.cache_dir)) and os.path.isfile(path_from_output):
                                saved_path = path_from_output
                                break
                        else:
                            potential_path = os.path.join(self.cache_dir, path_from_output)
                            if os.path.isfile(potential_path):
                                saved_path = potential_path
                                break

            if saved_path:
                 logging.info(f"MxLRC thành công, đã lưu file: {saved_path}")
                 return saved_path # Trả về đường dẫn thành công từ MxLRC
            else:
                 # MxLRC chạy xong (code 0) nhưng không parse/xác nhận được file -> thử fallback
                 logging.warning("MxLRC chạy xong nhưng không xác nhận được file đã lưu. Thử fallback sang SyncedLyrics...")
                 return self._fetch_with_syncedlyrics(artist, title, audio_stem)

        except subprocess.TimeoutExpired:
            # --- Xử lý Timeout: Ghi log và gọi Fallback ---
            logging.error("Lỗi timeout khi chạy MxLRC. Thử fallback sang SyncedLyrics...")
            return self._fetch_with_syncedlyrics(artist, title, audio_stem) # Gọi fallback
        except Exception as e:
            # --- Xử lý Lỗi Khác: Ghi log và gọi Fallback ---
            logging.exception(f"Lỗi khi gọi MxLRC: {e}. Thử fallback sang SyncedLyrics...")
            return self._fetch_with_syncedlyrics(artist, title, audio_stem) # Gọi fallback
    # ... (Các hàm khác như get_metadata, guess_title_artist, clean_*, get_lyrics_from_genius giữ nguyên) ...

    def get_metadata(self, song_path):
        try:
            audio = mutagen.File(song_path, easy=True)
            if not audio: return None, None
            title = audio.get('title', [None])[0]
            artist = audio.get('artist', [None])[0]
            # print(f"Metadata: Title='{title}', Artist='{artist}'") # Debug
            return title, artist
        except Exception as e:
            logging.warning(f"Lỗi khi đọc metadata từ '{os.path.basename(song_path)}': {e}")
            return None, None

    def guess_title_artist(self, filepath):
        base = os.path.basename(filepath)
        name = os.path.splitext(base)[0]
        # Thử tách bằng " - " trước
        parts = name.split(" - ", 1) # Chỉ tách 1 lần
        if len(parts) == 2:
            artist = parts[0].strip()
            title = parts[1].strip()
            # Bỏ các tag phổ biến ở cuối title (Remix), (Live), etc.
            title = re.sub(r"\s*\(.*?\)\s*$", "", title).strip()
            title = re.sub(r"\s*\[.*?\]\s*$", "", title).strip()
        else: # Nếu không có " - ", thử tách bằng "-" (ít tin cậy hơn)
             parts = name.split("-", 1)
             if len(parts) == 2:
                  artist = parts[0].strip()
                  title = parts[1].strip()
                  title = re.sub(r"\s*\(.*?\)\s*$", "", title).strip()
                  title = re.sub(r"\s*\[.*?\]\s*$", "", title).strip()
             else: # Nếu không tách được, coi cả tên file là title
                  artist = "" # Không đoán nghệ sĩ
                  title = name.strip()
        # print(f"Guessed: Title='{title}', Artist='{artist}'") # Debug
        return title, artist

    def clean_title(self, title):
        if not title: return ""
        cleaned = title
        # Bỏ dấu ngoặc kép
        cleaned = cleaned.replace('"', '')
        # Bỏ dấu ngoặc đơn/vuông trừ khi chứa remix/lofi/live/cover/acoustic
        exclude_keywords = r"(remix|lofi|live|cover|acoustic)"
        cleaned = re.sub(r"\[(?!.*?" + exclude_keywords + r").*?\]", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\((?!.*?" + exclude_keywords + r").*?\)", "", cleaned, flags=re.IGNORECASE)
        # Bỏ feat./ft./with và phần sau
        cleaned = re.sub(r"(?i)\s+(?:feat\.?|ft\.?|with)\s+.*", "", cleaned)
        # Bỏ các hậu tố phổ biến khác
        cleaned = re.sub(r"(?i)\s*[-\s]*(official\s+)?(music\s+video|lyric\s+video|audio|video|visualizer)\s*$", "", cleaned)
        return cleaned.strip()

    def clean_artist(self, artist):
        if not artist: return ""
        cleaned = artist
        # Bỏ dấu ngoặc kép
        cleaned = cleaned.replace('"', '')
        # Chỉ lấy tên nghệ sĩ chính, bỏ feat./ft./with, /, &
        # Sửa regex để xử lý cả dấu /
        cleaned = re.split(r"(?i)\s*(?:feat\.?|ft\.?|with|,|&|/)\s+", cleaned, 1)[0]
        # Bỏ các nhóm nhạc chung chung nếu đứng một mình
        if cleaned.lower() in ['various artists', 'va', 'unknown artist']: return ""
        return cleaned.strip()
    def get_lyrics_from_genius(self, song_title, artist):
        if not song_title: return "Không có tiêu đề bài hát để tìm kiếm."
        try:
            cleaned_title = self.clean_title(song_title)
            cleaned_artist = self.clean_artist(artist or "") # Đảm bảo artist không phải None
            logging.info(f"Genius search: Title='{cleaned_title}', Artist='{cleaned_artist}'")

            cache_key = hashlib.md5(f"{cleaned_title}_{cleaned_artist}".encode('utf-8')).hexdigest()
            cache_path = os.path.join(self.cache_dir, f"{cache_key}.txt")

            if os.path.exists(cache_path):
                try:
                     with open(cache_path, 'r', encoding='utf-8') as f:
                          cached_lyrics = f.read()
                          logging.info(f"Lấy lời bài hát từ cache: {cache_path}")
                          return cached_lyrics
                except Exception as cache_read_err:
                     logging.warning(f"Lỗi đọc cache file {cache_path}: {cache_read_err}")
                     # Xóa cache lỗi nếu đọc không được
                     try: os.remove(cache_path)
                     except OSError: pass

            # --- Tìm kiếm trên Genius ---
            song = None
            if cleaned_artist: # Ưu tiên tìm có nghệ sĩ
                song = self.genius.search_song(cleaned_title, cleaned_artist)
            if not song: # Nếu không thấy hoặc không có nghệ sĩ, tìm chỉ theo title
                 song = self.genius.search_song(cleaned_title)

            # Xử lý trường hợp không tìm thấy
            if not song:
                logging.warning(f"Không tìm thấy bài hát trên Genius: Title='{cleaned_title}', Artist='{cleaned_artist}'")
                # Có thể thử tìm kiếm rộng hơn (dùng genius.search()) nhưng có thể không chính xác
                return "Không tìm thấy lời bài hát trên Genius."

            # Lấy lời và làm sạch cơ bản
            raw_lyrics = song.lyrics if hasattr(song, 'lyrics') else ""
            # Loại bỏ dòng [Verse], [Chorus], ... và các dòng thừa ở đầu/cuối
            lyrics = re.sub(r'^.*\d+ Contributors.*Lyrics\s*', '', raw_lyrics).strip() # Bỏ header của Genius
            lyrics = re.sub(r'\[(Verse.*|Chorus|Intro|Outro|Bridge|Pre-Chorus|Interlude|Instrumental.*)\]', '', lyrics) # Bỏ tag section
            lyrics = re.sub(r'\n{3,}', '\n\n', lyrics) # Giảm số dòng trắng liên tiếp
            lyrics = lyrics.strip()


            if not lyrics or lyrics.lower() == "[instrumental]":
                 logging.info("Bài hát là instrumental hoặc không có lời.")
                 return "Bài hát không có lời (instrumental)."

            # Lưu vào cache
            try:
                with open(cache_path, 'w', encoding='utf-8') as f:
                    f.write(lyrics) # Lưu lời đã làm sạch cơ bản
                logging.info(f"Lưu lời bài hát vào cache: {cache_path}")
            except Exception as cache_write_err:
                logging.error(f"Lỗi ghi cache file {cache_path}: {cache_write_err}")

            return lyrics
        except Exception as e:
            logging.exception(f"Lỗi khi tìm lời với Genius: {e}")
            return "Đã xảy ra lỗi khi tìm lời bài hát trên Genius."

    # Hàm save_lyrics không được dùng trong luồng chính, có thể bỏ đi hoặc giữ lại nếu cần sau này
    # def save_lyrics(self, filepath, lyrics): ...