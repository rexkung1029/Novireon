import io
import json
import logging
import requests
import wave

from contextlib import closing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("monster_siren")

class Monster_siren:
    def get_song_data(url:str):
        try:
            cid = url.split("/")[-1]
            logger.info(f"find data from Monster Siren, cid={cid}")
            song_response = requests.get(url=f'https://monster-siren.hypergryph.com/api/song/{cid}',)
            raw_song_data = json.loads(song_response.text)['data']
            album_response = requests.get(url=f'https://monster-siren.hypergryph.com/api/album/{int(raw_song_data['albumCid'])}/detail')
            raw_album_data =json.loads(album_response.text)['data']
            duration = get_wav_duration_robust(raw_song_data['sourceUrl'])
            data={
                "author":raw_song_data.get('artists')[0],
                "duration" : int(duration),
                "song_url" : raw_song_data['sourceUrl'],
                "title" : raw_song_data['name'],
                "thumbnail" : raw_album_data.get('coverUrl', '')
            }
            return data
        except Exception as e:
            logger.error("無法從MSR獲取歌曲資訊")
            logger.error(e)

def parse_wav_bytes(wav_bytes):
    in_memory_file = io.BytesIO(wav_bytes)
    with closing(wave.open(in_memory_file, 'rb')) as wf:
        n_frames = wf.getnframes()
        frame_rate = wf.getframerate()
        return n_frames / float(frame_rate)


def get_wav_duration_robust(url, timeout=15):
    try:
        headers = {'Range': 'bytes=0-10000'} # 請求 10000 bytes
        logger.debug("階段一：嘗試以最高效率模式 (僅下載標頭)...")
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

        if response.status_code == 206:
            logger.debug("伺服器支援部分下載，正在解析標頭...")
            try:
                duration = parse_wav_bytes(response.content)
                logger.debug("成功從標頭解析出時長！")
                return duration
            except wave.Error:
                logger.error("警告：部分標頭不足以解析，將自動降級為完整下載。")

        elif response.status_code == 200:
            logger.debug("伺服器不支援部分下載，但已回傳完整檔案。")
            duration = parse_wav_bytes(response.content)
            return duration

    except requests.exceptions.RequestException as e:
        logger.error(f"網路錯誤，無法完成請求: {e}")
        return None
    except Exception as e:
        logger.error(f"發生非預期錯誤: {e}")
        return None

    try:
        logger.debug("\n階段二：執行標準模式 (完整下載)...")
        full_response = requests.get(url, timeout=timeout*2)
        full_response.raise_for_status()
        
        duration = parse_wav_bytes(full_response.content)
        logger.debug("成功從完整檔案中解析出時長！")
        return duration

    except requests.exceptions.RequestException as e:
        logger.error(f"網路錯誤，完整下載失敗: {e}")
        return None
    except wave.Error as e:
        logger.error(f"檔案格式錯誤，無法解析此 WAV 檔案: {e}")
        return None
    except Exception as e:
        logger.error(f"發生非預期錯誤: {e}")
        return None

