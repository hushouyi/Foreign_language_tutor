"""
TTS 引擎 - 语音合成抽象与实现
"""

import abc
import asyncio
import io
import os
import subprocess
import tempfile
import threading
import time
import queue as _queue

import miniaudio


class TTSProvider(abc.ABC):
    @abc.abstractmethod
    def speak(self, text: str) -> bool:
        """返回 True 表示播放成功，False 表示失败"""
        ...

    def cancel(self):
        """取消当前播放（默认空实现）"""
        pass


class EdgeTTSProvider(TTSProvider):
    """edge-tts 合成 → miniaudio 解码 → 裁剪静音 → miniaudio PlaybackDevice 播放

    相比旧版 PowerShell SoundPlayer 方案：
    - 去掉 ~500ms PowerShell 进程启动延迟
    - 去掉 WAV 临时文件管理
    - 裁剪 MP3 编码器带来的 ~200ms 前导静音
    - 直接 PCM 播放，无需转码到 WAV
    """

    def __init__(self, voice: str):
        self.voice = voice
        self._device = None
        self._device_lock = threading.Lock()
        self._cancelled = False

    def cancel(self):
        """取消当前正在播放的语音"""
        self._cancelled = True
        with self._device_lock:
            if self._device:
                try:
                    self._device.stop()
                except Exception:
                    pass
                try:
                    self._device.close()
                except Exception:
                    pass
                self._device = None

    def set_voice(self, voice: str):
        """运行时切换语音"""
        self.voice = voice

    # ── 音频获取 + 解码 ──────────────────────────

    def _generate_mp3(self, text: str) -> str:
        """edge-tts 生成 MP3，返回临时文件路径（调用方负责删除）"""
        async def _gen():
            import edge_tts as _edge_tts
            communicate = _edge_tts.Communicate(text, self.voice)
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.close()
            await communicate.save(tmp.name)
            return tmp.name
        return asyncio.run(_gen())

    @staticmethod
    def _trim_silence(samples, threshold=30):
        """裁剪首尾静音，返回裁剪后的 array.array"""
        start = 0
        for i in range(len(samples)):
            if abs(samples[i]) > threshold:
                start = i
                break
        end = len(samples)
        for i in range(len(samples) - 1, -1, -1):
            if abs(samples[i]) > threshold:
                end = i + 1
                break
        if start > 0 or end < len(samples):
            return samples[start:end]
        return samples

    def _generate_clean_pcm(self, text: str):
        """生成语音→MP3→解码为 PCM→裁剪静音

        返回 (samples: array.array('h'), nchannels: int, sample_rate: int)
        直接使用 mp3_read_file_s16 保持原生格式（单声道 24000Hz），
        避免 decode_file 无故升采样到立体声 44100Hz 引入额外静音。
        """
        mp3_path = self._generate_mp3(text)
        try:
            decoded = miniaudio.mp3_read_file_s16(mp3_path)
            samples = self._trim_silence(decoded.samples, threshold=30)
            return samples, decoded.nchannels, decoded.sample_rate
        finally:
            try:
                os.unlink(mp3_path)
            except Exception:
                pass

    # ── 播放 ─────────────────────────────────────

    def _play_pcm(self, samples, nchannels, sample_rate):
        """直接用 miniaudio PlaybackDevice 播放 PCM，阻塞直到播完或取消"""
        device = miniaudio.PlaybackDevice(
            output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=nchannels,
            sample_rate=sample_rate,
            buffersize_msec=100,
        )
        with self._device_lock:
            self._device = device

        gen = miniaudio.stream_raw_pcm_memory(samples.tobytes(), nchannels, 2, 4096)
        next(gen)  # prime the generator

        device.start(gen)

        # 轮询等待：等预计时长或取消
        duration = len(samples) / (sample_rate * nchannels)
        deadline = time.time() + duration + 0.3
        while time.time() < deadline:
            if self._cancelled:
                break
            time.sleep(0.05)

        with self._device_lock:
            if self._device is device:
                try:
                    device.stop()
                except Exception:
                    pass
                try:
                    device.close()
                except Exception:
                    pass
                self._device = None

    # ── Web 模式：返回 WAV 字节（给浏览器播） ────

    def _generate_wav_bytes(self, text: str) -> bytes:
        """生成音频，返回 WAV 字节（已裁剪前导静音）"""
        import wave as wave_mod

        samples, nchannels, sample_rate = self._generate_clean_pcm(text)
        buf = io.BytesIO()
        with wave_mod.open(buf, "wb") as wf:
            wf.setnchannels(nchannels)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(samples.tobytes())
        return buf.getvalue()

    # ── CLI 模式：同步接口 ──────────────────────

    def speak(self, text: str) -> bool:
        """同步朗读（阻塞直到播完），可在其他线程运行"""
        self._cancelled = False
        try:
            samples, nchannels, sample_rate = self._generate_clean_pcm(text)
            self._play_pcm(samples, nchannels, sample_rate)
            return True
        except Exception:
            return False

    def speak_segments(self, segments: list, on_before=None):
        """逐段生成+播放，播前回调。后台预生成下一段确保连续性。"""
        self._cancelled = False

        if not segments:
            return

        # 预生成第一段
        current = self._generate_clean_pcm(segments[0][0])

        for idx in range(len(segments)):
            if self._cancelled:
                break

            # 后台预生成下一段
            next_ready = None
            if idx + 1 < len(segments):
                next_ready = _queue.Queue()
                def _gen(i, q):
                    pcm = self._generate_clean_pcm(segments[i + 1][0])
                    q.put(pcm)
                threading.Thread(target=_gen, args=(idx, next_ready), daemon=True).start()

            # 播前回调
            if on_before:
                on_before(idx)

            # 播放当前段
            samples, nchannels, sample_rate = current
            self._play_pcm(samples, nchannels, sample_rate)

            # 获取下一段（等后台生成完成）
            if next_ready:
                current = next_ready.get()

    def speak_async(self, text: str):
        """非阻塞朗读。返回一个 wait() 函数，调用后等待播完并清理。"""
        samples, nchannels, sample_rate = self._generate_clean_pcm(text)
        device = miniaudio.PlaybackDevice(
            output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=nchannels,
            sample_rate=sample_rate,
            buffersize_msec=100,
        )
        gen = miniaudio.stream_raw_pcm_memory(samples.tobytes(), nchannels, 2, 4096)
        next(gen)
        device.start(gen)

        duration = len(samples) / (sample_rate * nchannels)

        def wait():
            time.sleep(duration + 0.3)
            device.stop()
            device.close()
        return wait


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
