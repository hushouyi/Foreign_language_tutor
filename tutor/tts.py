"""
TTS 引擎 - 语音合成抽象与实现
"""

import abc
import asyncio
import os
import subprocess
import tempfile
import threading


class TTSProvider(abc.ABC):
    @abc.abstractmethod
    def speak(self, text: str) -> bool:
        """返回 True 表示播放成功，False 表示失败"""
        ...

    def cancel(self):
        """取消当前播放（默认空实现）"""
        pass


class EdgeTTSProvider(TTSProvider):
    """edge-tts 合成 → miniaudio 解码 → WAV → PowerShell SoundPlayer 播放"""

    def __init__(self, voice: str):
        self.voice = voice
        self._process = None
        self._proc_lock = threading.Lock()
        self._cancelled = False

    def cancel(self):
        """取消当前正在播放的语音"""
        self._cancelled = True
        with self._proc_lock:
            if self._process and self._process.poll() is None:
                try:
                    self._process.kill()
                    self._process.wait(timeout=5)
                except Exception:
                    pass
                self._process = None

    def set_voice(self, voice: str):
        """运行时切换语音"""
        self.voice = voice

    def _generate_wav(self, text: str):
        """生成音频，返回 (mp3_path, wav_path)"""
        import miniaudio
        import wave as wave_mod

        async def _gen():
            import edge_tts as _edge_tts
            communicate = _edge_tts.Communicate(text, self.voice)
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.close()
            await communicate.save(tmp.name)
            return tmp.name

        mp3_path = asyncio.run(_gen())
        wav_fd, wav_path = tempfile.mkstemp(suffix=".wav")
        os.close(wav_fd)
        decoded = miniaudio.decode_file(mp3_path, output_format=miniaudio.SampleFormat.SIGNED16)
        with wave_mod.open(wav_path, "wb") as wf:
            wf.setnchannels(decoded.nchannels)
            wf.setsampwidth(2)
            wf.setframerate(decoded.sample_rate)
            wf.writeframes(decoded.samples.tobytes())
        return mp3_path, wav_path

    def _play_wav(self, wav_path: str):
        """启动 PowerShell SoundPlayer 播放并记录进程"""
        proc = subprocess.Popen(
            ["powershell", "-c",
             f"$p = New-Object System.Media.SoundPlayer; "
             f"$p.SoundLocation = '{wav_path}'; "
             f"$p.PlaySync()"],
        )
        with self._proc_lock:
            self._process = proc
        return proc

    def speak(self, text: str) -> bool:
        """同步朗读（阻塞直到播完），可在其他线程运行"""
        mp3_path = wav_path = None
        try:
            mp3_path, wav_path = self._generate_wav(text)
            proc = self._play_wav(wav_path)
            proc.wait()
            return True
        except Exception:
            return False
        finally:
            with self._proc_lock:
                self._process = None
            for p in (mp3_path, wav_path):
                try:
                    os.unlink(p)
                except Exception:
                    pass

    def speak_segments(self, segments: list, on_before=None):
        """逐段生成+播放，播前回调。后台预生成下一段确保连续性。"""
        import queue as _queue
        import threading as _threading

        self._cancelled = False

        # 生成第一段
        mp3_path, wav_path = self._generate_wav(segments[0][0])
        try:
            os.unlink(mp3_path)
        except Exception:
            pass

        for idx in range(len(segments)):
            if self._cancelled:
                break

            # 后台预生成下一段
            next_queue = None
            if idx + 1 < len(segments):
                next_queue = _queue.Queue()
                def _gen(i, q):
                    mp3, wav = self._generate_wav(segments[i + 1][0])
                    try:
                        os.unlink(mp3)
                    except Exception:
                        pass
                    q.put(wav)
                _threading.Thread(target=_gen, args=(idx, next_queue), daemon=True).start()

            # 播前回调
            if on_before:
                on_before(idx)

            # 播放当前段
            proc = self._play_wav(wav_path)
            proc.wait()

            # 清理当前文件
            try:
                os.unlink(wav_path)
            except Exception:
                pass

            # 获取下一段音频（等待后台生成完成）
            if next_queue:
                wav_path = next_queue.get()
            else:
                wav_path = None

    def speak_async(self, text: str):
        """非阻塞朗读。返回一个 wait() 函数，调用后等待播完并清理。"""
        try:
            mp3_path, wav_path = self._generate_wav(text)
            proc = self._play_wav(wav_path)
            paths = (mp3_path, wav_path)

            def wait():
                proc.wait()
                with self._proc_lock:
                    self._process = None
                for p in paths:
                    try:
                        os.unlink(p)
                    except Exception:
                        pass
            return wait
        except Exception:
            return lambda: None


class Pyttsx3Provider(TTSProvider):
    """pyttsx3 离线 TTS"""
    def __init__(self, rate: int, volume: float):
        import pyttsx3
        engine = pyttsx3.init()
        for v in engine.getProperty("voices"):
            if "english" in v.name.lower() or "US" in v.name or "Zira" in v.name:
                engine.setProperty("voice", v.id)
                break
        engine.setProperty("rate", rate)
        engine.setProperty("volume", volume)
        self._engine = engine

    def speak(self, text: str) -> bool:
        self._engine.say(text)
        self._engine.runAndWait()
        self._engine.stop()
        return True


def create_tts_provider(config: dict) -> TTSProvider:
    engine = config["TTS_ENGINE"]
    if engine == "edge-tts":
        return EdgeTTSProvider(voice=config["lang"]["voice"])
    elif engine == "pyttsx3":
        return Pyttsx3Provider(rate=config["PYTTX3_RATE"], volume=config["PYTTX3_VOLUME"])
    else:
        raise ValueError(f"未知 TTS_ENGINE: {engine}")
