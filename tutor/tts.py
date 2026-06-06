"""
TTS 引擎 - 语音合成抽象与实现
"""

import abc
import asyncio
import os
import subprocess
import tempfile


class TTSProvider(abc.ABC):
    @abc.abstractmethod
    def speak(self, text: str) -> None:
        ...


class EdgeTTSProvider(TTSProvider):
    """edge-tts 合成 → miniaudio 解码 → WAV → PowerShell SoundPlayer 播放"""
    def __init__(self, voice: str):
        self.voice = voice

    def set_voice(self, voice: str):
        """运行时切换语音"""
        self.voice = voice

    def speak(self, text: str) -> None:
        import miniaudio
        import wave as wave_mod

        async def _gen():
            import edge_tts as _edge_tts
            communicate = _edge_tts.Communicate(text, self.voice)
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.close()
            await communicate.save(tmp.name)
            return tmp.name

        mp3_path = None
        wav_path = None
        try:
            mp3_path = asyncio.run(_gen())
            wav_fd, wav_path = tempfile.mkstemp(suffix=".wav")
            os.close(wav_fd)
            decoded = miniaudio.decode_file(mp3_path, output_format=miniaudio.SampleFormat.SIGNED16)
            with wave_mod.open(wav_path, "wb") as wf:
                wf.setnchannels(decoded.nchannels)
                wf.setsampwidth(2)
                wf.setframerate(decoded.sample_rate)
                wf.writeframes(decoded.samples.tobytes())
            subprocess.run(
                ["powershell", "-c",
                 f"$p = New-Object System.Media.SoundPlayer; "
                 f"$p.SoundLocation = '{wav_path}'; "
                 f"$p.PlaySync()"],
                capture_output=True, timeout=120,
            )
        except Exception as e:
            print(f"⚠ 语音播放失败: {e}")
        finally:
            for p in (mp3_path, wav_path):
                if p:
                    try:
                        os.unlink(p)
                    except Exception:
                        pass


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

    def speak(self, text: str) -> None:
        self._engine.say(text)
        self._engine.runAndWait()
        self._engine.stop()


def create_tts_provider(config: dict) -> TTSProvider:
    engine = config["TTS_ENGINE"]
    if engine == "edge-tts":
        return EdgeTTSProvider(voice=config["lang"]["voice"])
    elif engine == "pyttsx3":
        return Pyttsx3Provider(rate=config["PYTTX3_RATE"], volume=config["PYTTX3_VOLUME"])
    else:
        raise ValueError(f"未知 TTS_ENGINE: {engine}")
