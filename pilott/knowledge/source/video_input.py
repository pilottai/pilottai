import asyncio
import os
import tempfile
from typing import Any, List, Optional
from datetime import datetime, timedelta

from pilott.knowledge.source.base_input import BaseInputSource


class VideoInput(BaseInputSource):
    """
    Input source for processing video files.
    Extracts audio track and/or frames from videos, then processes them for knowledge extraction.
    """

    def __init__(
        self,
        name: str,
        file_path: Optional[str] = None,
        file_content: Optional[bytes] = None,
        extract_audio: bool = True,
        extract_frames: bool = False,
        frame_interval: float = 5.0,  # Extract one frame every 5 seconds
        audio_speech_to_text: bool = True,
        frame_ocr: bool = False,
        metadata_only: bool = False,
        **kwargs
    ):
        super().__init__(name=name, **kwargs)
        self.file_path = file_path
        self.file_content = file_content
        self.extract_audio = extract_audio
        self.extract_frames = extract_frames
        self.frame_interval = frame_interval
        self.audio_speech_to_text = audio_speech_to_text
        self.frame_ocr = frame_ocr
        self.metadata_only = metadata_only

        # Storage
        self.text_content = None
        self.video_metadata = None
        self.extracted_frames = []
        self.audio_content = None
        self.temp_files = []  # Track temporary files for cleanup

    async def connect(self) -> bool:
        """Check if the video is accessible and get basic metadata"""
        try:
            # Handle binary content
            if self.file_content is not None:
                # Save to a temporary file
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                temp_file.write(self.file_content)
                temp_file.close()
                self.temp_files.append(temp_file.name)
                self.file_path = temp_file.name

            # Check file path
            if not self.file_path:
                self.logger.error("No video file path provided")
                self.is_connected = False
                return False

            if not os.path.exists(self.file_path):
                self.logger.error(f"Video file not found: {self.file_path}")
                self.is_connected = False
                return False

            if not os.access(self.file_path, os.R_OK):
                self.logger.error(f"Video file not readable: {self.file_path}")
                self.is_connected = False
                return False

            # Get video metadata
            await self._get_video_metadata()
            self.is_connected = self.video_metadata is not None
            return self.is_connected

        except Exception as e:
            self.logger.error(f"Connection error: {str(e)}")
            self.is_connected = False
            return False

    async def query(self, query: str) -> Any:
        """Search for query in the processed content"""
        if not self.is_connected or not self.text_content:
            if not await self.process_video():
                raise ValueError("Could not process video content")

        self.access_count += 1
        self.last_access = datetime.now()

        # Simple search implementation
        results = []
        if query.lower() in self.text_content.lower():
            context_size = 200  # Characters before and after match

            # Find all occurrences
            start_idx = 0
            query_lower = query.lower()
            text_lower = self.text_content.lower()

            while True:
                idx = text_lower.find(query_lower, start_idx)
                if idx == -1:
                    break

                # Get context around the match
                context_start = max(0, idx - context_size)
                context_end = min(len(self.text_content), idx + len(query) + context_size)
                context = self.text_content[context_start:context_end]

                # Estimate timestamp if possible
                timestamp = self._estimate_timestamp(idx)

                results.append({
                    "match": self.text_content[idx:idx + len(query)],
                    "context": context,
                    "position": idx,
                    "timestamp": timestamp
                })

                start_idx = idx + len(query)

        return results

    async def validate_content(self) -> bool:
        """Validate that video content is accessible and can be processed"""
        if not self.is_connected:
            if not await self.connect():
                return False

        # Check that we have basic metadata
        if not self.video_metadata:
            return False

        # If metadata only, we're done
        if self.metadata_only:
            return True

        # For full processing, check that required tools are available
        if self.extract_audio and self.audio_speech_to_text:
            if not self._check_speech_to_text_available():
                self.logger.warning("Speech-to-text capability not available")
                return False

        if self.extract_frames and self.frame_ocr:
            if not self._check_ocr_available():
                self.logger.warning("OCR capability not available")
                return False

        return True

    async def _get_video_metadata(self) -> None:
        """Extract metadata from video file using FFmpeg"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                self.file_path
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                self.logger.error(f"Error getting video metadata: {stderr.decode()}")
                return

            import json
            metadata = json.loads(stdout.decode())

            # Extract useful information
            self.video_metadata = {
                'format': metadata.get('format', {}),
                'duration': float(metadata.get('format', {}).get('duration', 0)),
                'size': int(metadata.get('format', {}).get('size', 0)),
                'bitrate': int(metadata.get('format', {}).get('bit_rate', 0)),
                'streams': []
            }

            # Process streams (audio, video)
            for stream in metadata.get('streams', []):
                stream_type = stream.get('codec_type')
                if stream_type:
                    self.video_metadata['streams'].append({
                        'type': stream_type,
                        'codec': stream.get('codec_name'),
                        'width': stream.get('width') if stream_type == 'video' else None,
                        'height': stream.get('height') if stream_type == 'video' else None,
                        'fps': eval(stream.get('r_frame_rate', '0/1')) if stream_type == 'video' else None,
                        'channels': stream.get('channels') if stream_type == 'audio' else None,
                        'sample_rate': stream.get('sample_rate') if stream_type == 'audio' else None
                    })

        except Exception as e:
            self.logger.error(f"Error processing video metadata: {str(e)}")

    async def process_video(self) -> bool:
        """Process video content by extracting audio and/or frames"""
        try:
            if not self.is_connected:
                if not await self.connect():
                    return False

            # If metadata only, just format the metadata as text
            if self.metadata_only:
                self.text_content = self._format_metadata_as_text()
                return True

            results = []

            # Extract and process audio
            if self.extract_audio:
                audio_text = await self._extract_and_process_audio()
                if audio_text:
                    results.append(f"=== AUDIO TRANSCRIPT ===\n{audio_text}")

            # Extract and process frames
            if self.extract_frames:
                frames_text = await self._extract_and_process_frames()
                if frames_text:
                    results.append(f"=== VISUAL CONTENT ===\n{frames_text}")

            # Add metadata
            metadata_text = self._format_metadata_as_text()
            results.append(f"=== VIDEO METADATA ===\n{metadata_text}")

            # Combine all results
            self.text_content = "\n\n".join(results)
            return bool(self.text_content)

        except Exception as e:
            self.logger.error(f"Error processing video: {str(e)}")
            return False
        finally:
            # Clean up temporary files
            self._cleanup_temp_files()

    async def _extract_and_process_audio(self) -> Optional[str]:
        """Extract audio from video and convert to text"""
        try:
            # Extract audio to temporary file
            audio_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            audio_temp.close()
            self.temp_files.append(audio_temp.name)

            cmd = [
                'ffmpeg',
                '-i', self.file_path,
                '-q:a', '0',
                '-map', 'a',
                '-y',  # Overwrite output file if it exists
                audio_temp.name
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                self.logger.error(f"Error extracting audio: {stderr.decode()}")
                return None

            # Store audio path
            self.audio_content = audio_temp.name

            # Process with speech-to-text if enabled
            if self.audio_speech_to_text:
                return await self._speech_to_text(audio_temp.name)

            return f"Audio extracted to {audio_temp.name}"

        except Exception as e:
            self.logger.error(f"Error processing audio: {str(e)}")
            return None

    async def _extract_and_process_frames(self) -> Optional[str]:
        """Extract frames from video and process them"""
        try:
            # Create temporary directory for frames
            frames_dir = tempfile.mkdtemp()
            self.temp_files.append(frames_dir)

            # Calculate frame extraction rate
            if not self.video_metadata or 'duration' not in self.video_metadata:
                self.logger.error("Video duration unknown, cannot extract frames")
                return None

            duration = self.video_metadata['duration']
            frame_count = int(duration / self.frame_interval)

            if frame_count < 1:
                frame_count = 1  # At least one frame

            # Extract frames
            cmd = [
                'ffmpeg',
                '-i', self.file_path,
                '-vf', f'fps=1/{self.frame_interval}',
                '-y',  # Overwrite output files if they exist
                f'{frames_dir}/frame_%04d.jpg'
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                self.logger.error(f"Error extracting frames: {stderr.decode()}")
                return None

            # Get list of extracted frames
            frames = sorted([
                os.path.join(frames_dir, f)
                for f in os.listdir(frames_dir)
                if f.startswith('frame_') and f.endswith('.jpg')
            ])

            self.extracted_frames = frames

            # Process frames with OCR if enabled
            if self.frame_ocr:
                return await self._process_frames_with_ocr(frames)

            return f"Extracted {len(frames)} frames to {frames_dir}"

        except Exception as e:
            self.logger.error(f"Error processing frames: {str(e)}")
            return None

    async def _speech_to_text(self, audio_file: str) -> Optional[str]:
        """Convert speech to text using an available speech recognition library"""
        try:
            # This is a placeholder that should be implemented with a proper speech-to-text system
            # For example, using Google's Speech Recognition, Whisper, etc.

            # Placeholder implementation using SpeechRecognition
            import speech_recognition as sr

            recognizer = sr.Recognizer()
            with sr.AudioFile(audio_file) as source:
                audio_data = recognizer.record(source)
                text = recognizer.recognize_google(audio_data)
                return text

        except ImportError:
            self.logger.error("SpeechRecognition library not available")
            return "Speech-to-text processing not available"
        except Exception as e:
            self.logger.error(f"Error in speech-to-text: {str(e)}")
            return "Error in speech-to-text processing"

    async def _process_frames_with_ocr(self, frames: List[str]) -> Optional[str]:
        """Process frames with OCR to extract text"""
        try:
            # Import libraries for OCR
            import pytesseract
            from PIL import Image

            results = []

            for i, frame_path in enumerate(frames):
                # Calculate timestamp
                timestamp = i * self.frame_interval
                formatted_time = str(timedelta(seconds=int(timestamp)))

                # Extract text from frame
                try:
                    img = Image.open(frame_path)
                    text = pytesseract.image_to_string(img)

                    if text.strip():
                        results.append(f"[{formatted_time}] {text.strip()}")
                except Exception as e:
                    self.logger.error(f"Error processing frame {frame_path}: {str(e)}")

            return "\n\n".join(results)

        except ImportError:
            self.logger.error("OCR libraries not available")
            return "OCR processing not available"
        except Exception as e:
            self.logger.error(f"Error in OCR processing: {str(e)}")
            return "Error in OCR processing"

    def _format_metadata_as_text(self) -> str:
        """Format video metadata as readable text"""
        if not self.video_metadata:
            return "No metadata available"

        lines = [
            f"Duration: {timedelta(seconds=int(self.video_metadata.get('duration', 0)))}",
            f"Size: {self._format_size(self.video_metadata.get('size', 0))}",
            f"Bitrate: {int(self.video_metadata.get('bitrate', 0) / 1000)} kbps"
        ]

        for stream in self.video_metadata.get('streams', []):
            if stream.get('type') == 'video':
                lines.append(
                    f"Video: {stream.get('codec')} {stream.get('width')}x{stream.get('height')} @ {stream.get('fps'):.2f} fps")
            elif stream.get('type') == 'audio':
                lines.append(
                    f"Audio: {stream.get('codec')} {stream.get('channels')} channels @ {stream.get('sample_rate')} Hz")

        return "\n".join(lines)

    def _format_size(self, size_bytes: int) -> str:
        """Format size in bytes to human-readable form"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} PB"

    def _estimate_timestamp(self, position: int) -> Optional[str]:
        """Estimate video timestamp based on text position"""
        # This is a rough estimation and would need to be improved in a real implementation
        if not self.text_content or not self.video_metadata:
            return None

        if position < 0 or position >= len(self.text_content):
            return None

        # Simple linear mapping
        text_percentage = position / len(self.text_content)
        estimated_seconds = text_percentage * self.video_metadata.get('duration', 0)

        return str(timedelta(seconds=int(estimated_seconds)))

    def _check_speech_to_text_available(self) -> bool:
        """Check if speech-to-text capabilities are available"""
        try:
            import speech_recognition
            return True
        except ImportError:
            return False

    def _check_ocr_available(self) -> bool:
        """Check if OCR capabilities are available"""
        try:
            import pytesseract
            from PIL import Image
            return True
        except ImportError:
            return False

    def _cleanup_temp_files(self) -> None:
        """Clean up temporary files and directories"""
        for path in self.temp_files:
            try:
                if os.path.isdir(path):
                    import shutil
                    shutil.rmtree(path)
                elif os.path.exists(path):
                    os.unlink(path)
            except Exception as e:
                self.logger.error(f"Error cleaning up temp file {path}: {str(e)}")

    async def _process_content(self) -> None:
        """Process video content and chunk it"""
        if not self.text_content:
            if not await self.process_video():
                return

        self.chunks = self._chunk_text(self.text_content)
        source_desc = self.file_path if self.file_path else "video data"
        self.logger.info(f"Created {len(self.chunks)} chunks from video {source_desc}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._cleanup_temp_files()
