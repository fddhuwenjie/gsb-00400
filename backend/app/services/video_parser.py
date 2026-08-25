import subprocess
import json
from pathlib import Path
from typing import Dict, List
import tempfile
import os

class VideoParser:
    """视频解析服务：语音转文字、分段、关键帧"""
    
    def __init__(self, model_size: str = "base"):
        self.model = None
        self.model_size = model_size
        self._whisper_available = None
    
    def _check_whisper(self):
        if self._whisper_available is None:
            try:
                import whisper
                self._whisper_available = True
            except ImportError:
                self._whisper_available = False
        return self._whisper_available
    
    def _load_model(self):
        if not self._check_whisper():
            raise ImportError("whisper not installed. Run: pip install openai-whisper")
        if self.model is None:
            import whisper
            self.model = whisper.load_model(self.model_size)
    
    async def extract_audio(self, video_path: str, output_path: str) -> bool:
        """从视频提取音频"""
        try:
            cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
                   "-ar", "16000", "-ac", "1", "-y", output_path]
            subprocess.run(cmd, capture_output=True, check=True)
            return True
        except Exception:
            return False
    
    async def transcribe(self, video_path: str, segment_duration: int = 30) -> Dict:
        """视频语音转文字（whisper不可用时降级为文件名信息）"""
        chunks = []
        metadata = {"duration": 0, "language": ""}
        
        if not self._check_whisper():
            # 降级处理：whisper不可用时，用文件名生成基本信息，不报错
            filename = Path(video_path).stem
            chunks.append({
                "index": 0,
                "content": f"视频文件：{filename}（语音转文字服务未安装，仅记录文件信息）",
                "type": "fallback",
                "start": 0,
                "end": 0
            })
            return {"chunks": chunks, "metadata": metadata}

        try:
            self._load_model()
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                audio_path = tmp.name
            
            if not await self.extract_audio(video_path, audio_path):
                # 音频提取失败也降级处理
                filename = Path(video_path).stem
                chunks.append({
                    "index": 0,
                    "content": f"视频文件：{filename}（音频提取失败，仅记录文件信息）",
                    "type": "fallback",
                    "start": 0,
                    "end": 0
                })
                return {"chunks": chunks, "metadata": metadata}
            
            result = self.model.transcribe(audio_path, language="zh")
            metadata["language"] = result.get("language", "unknown")
            
            segments = result.get("segments", [])
            for seg in segments:
                chunks.append({
                    "index": seg["id"],
                    "content": seg["text"].strip(),
                    "type": "transcript",
                    "start": seg["start"],
                    "end": seg["end"]
                })
            
            if segments:
                metadata["duration"] = segments[-1]["end"]
            
            os.unlink(audio_path)
        except Exception as e:
            # 异常也降级，不返回error
            filename = Path(video_path).stem
            chunks.append({
                "index": 0,
                "content": f"视频文件：{filename}（转写异常：{str(e)[:100]}）",
                "type": "fallback",
                "start": 0,
                "end": 0
            })
        
        return {"chunks": chunks, "metadata": metadata}
    
    async def extract_keyframes(self, video_path: str, output_dir: str, interval: int = 60) -> List[str]:
        """提取关键帧"""
        frames = []
        try:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            output_pattern = str(Path(output_dir) / "frame_%04d.jpg")
            cmd = ["ffmpeg", "-i", video_path, "-vf", f"fps=1/{interval}", "-y", output_pattern]
            subprocess.run(cmd, capture_output=True, check=True)
            frames = sorted(Path(output_dir).glob("frame_*.jpg"))
            frames = [str(f) for f in frames]
        except Exception:
            pass
        return frames
