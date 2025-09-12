import io
import json
import logging
import os
import requests
from urllib.parse import urlparse
from pydub import AudioSegment
import soundfile as sf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("monster_siren")


class Monster_siren:
    def get_song_data(page_url: str):
        try:
            logger.info(f"正在從頁面 URL 獲取歌曲資訊...")
            cid = page_url.split("/")[-1]

            song_response = requests.get(
                url=f"https://monster-siren.hypergryph.com/api/song/{cid}"
            )
            song_response.raise_for_status()
            raw_song_data = song_response.json()["data"]

            album_cid = raw_song_data.get("albumCid")
            if not album_cid:
                raise ValueError("API 回應中未找到專輯 ID (albumCid)")

            album_response = requests.get(
                url=f"https://monster-siren.hypergryph.com/api/album/{album_cid}/detail"
            )
            album_response.raise_for_status()
            raw_album_data = album_response.json()["data"]
            logger.info("成功獲取 API 元數據！")

            audio_url = raw_song_data.get("sourceUrl")
            calculated_duration = None
            if audio_url:
                calculated_duration = calculate_duration_from_audio_url(audio_url)
            else:
                logger.warning("API 回應中未提供音檔 URL (sourceUrl)。")

            data = {
                "title": raw_song_data.get("name", "N/A"),
                "author": ", ".join(raw_song_data.get("artists", ["N/A"])),
                "duration": calculated_duration,
                "song_url": audio_url,
                "thumbnail": raw_album_data.get("coverUrl", ""),
            }
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"API 請求失敗: {e}")
        except (KeyError, json.JSONDecodeError):
            logger.error("解析 API 回應失敗，可能是無效的 URL 或 API 結構已變更。")
        except Exception as e:
            # 使用 exc_info=True 可以自動附上完整的錯誤追蹤訊息，非常適合除錯
            logger.error(f"發生非預期錯誤: {e}", exc_info=True)
        return None


def calculate_duration_from_audio_url(audio_url: str, timeout=15):
    """
    智能分析音檔時長。
    - 如果是 WAV 檔，優先使用 HEAD 和 Range 請求結合標頭解析來計算總時長。
    - 如果是其他格式或高效模式失敗，則降級為完整下載並用 pydub 解析。
    """
    logger.info(f"開始分析 URL: {audio_url[:50]}...")

    path = urlparse(audio_url).path
    file_extension = os.path.splitext(path)[1].strip(".").lower()

    # --- 策略一：針對 WAV 檔案的超高效路徑 ---
    if file_extension == "wav":
        try:
            logger.info("偵測到 WAV 檔案，嘗試部份下載模式...")

            head_response = requests.head(audio_url, timeout=timeout)
            head_response.raise_for_status()
            content_length = int(head_response.headers["Content-Length"])

            headers = {"Range": "bytes=0-1023"}
            range_response = requests.get(audio_url, headers=headers, timeout=timeout)
            range_response.raise_for_status()

            with sf.SoundFile(io.BytesIO(range_response.content)) as audio_file:
                samplerate = audio_file.samplerate
                channels = audio_file.channels
                subtype = audio_file.subtype
                if "PCM_16" in subtype:
                    bits_per_sample = 16
                elif "PCM_24" in subtype:
                    bits_per_sample = 24
                elif "PCM_32" in subtype:
                    bits_per_sample = 32
                elif "FLOAT" in subtype:
                    bits_per_sample = 32
                else:
                    raise ValueError(f"未知的 WAV subtype: {subtype}")

                byte_rate = samplerate * channels * (bits_per_sample / 8)
                if byte_rate == 0:
                    raise ValueError("計算出的位元率為 0")

                header_approx_size = 100
                duration = (content_length - header_approx_size) / byte_rate

                logger.info("成功使用部份下載模式計算出時長！")
                return duration
        except Exception as e:
            logger.warning(
                f"部份下載失敗 ({type(e).__name__}: {e})，將降級為完整下載。"
            )

    # --- 策略二：針對 MP3 或其他格式，以及失敗的 WAV 的可靠路徑 ---
    try:
        logger.info("執行標準模式 (完整下載)...")
        full_response = requests.get(audio_url, timeout=timeout * 2)
        full_response.raise_for_status()

        if not file_extension:
            raise ValueError("無法從 URL 判斷檔案格式")

        audio_bytes = io.BytesIO(full_response.content)
        audio = AudioSegment.from_file(audio_bytes, format=file_extension)

        logger.info("成功從完整檔案中解析出時長！")
        return audio.duration_seconds
    except Exception as e:
        logger.error(f"完整下載解析失敗: {e}")
        return None
