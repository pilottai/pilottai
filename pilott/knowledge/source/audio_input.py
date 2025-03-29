import asyncio
import os
import tempfile
from typing import Any, Optional
from datetime import datetime, timedelta


from pilott.knowledge.source.base_input import BaseInputSource


class AudioInput(BaseInputSource):
    """
    Input source for processing audio files.
    Extracts and processes speech from audio files using speech-to-text technology.
    """

    def __init__(
        self,
        name: str,
        file_path: Optional[str] = None,
        file_content: Optional[bytes] = None,
        speech_to_text: bool = True,
        detect_language: bool = True,
        segment_speakers: bool = False,
        metadata_only: bool = False,
        **kwargs
    ):
        super().__init__(name=name, **kwargs)
        self.file_path = file_path
        self.file_content = file_content
        self.speech_to_text = speech_to_text
        self.detect_language = detect_language
        self.segment_speakers = segment_speakers
        self.metadata_only = metadata_only

        # Storage
        self.text_content = None
        self.audio_metadata = None
        self.detected_language = None
        self.speaker_segments = []
        self.temp_files = []  # Track temporary files for cleanup

    async def connect(self) -> bool:
        """Check if the audio file is accessible and get basic metadata"""
        try:
            # Handle binary content
            if self.file_content is not None:
                # Save to a temporary file
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                temp_file.write(self.file_content)
                temp_file.close()
                self.temp_files.append(temp_file.name)
                self.file_path = temp_file.name

            # Check file path
            if not self.file_path:
                self.logger.error("No audio file path provided")
                self.is_connected = False
                return False

            if not os.path.exists(self.file_path):
                self.logger.error(f"Audio file not found: {self.file_path}")
                self.is_connected = False
                return False

            if not os.access(self.file_path, os.R_OK):
                self.logger.error(f"Audio file not readable: {self.file_path}")
                self.is_connected = False
                return False

            # Get audio metadata
            await self._get_audio_metadata()
            self.is_connected = self.audio_metadata is not None
            return self.is_connected

        except Exception as e:
            self.logger.error(f"Connection error: {str(e)}")
            self.is_connected = False
            return False

    async def query(self, query: str) -> Any:
        """Search for query in the processed text content"""
        if not self.is_connected or not self.text_content:
            if not await self.process_audio():
                raise ValueError("Could not process audio content")

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

                # Find speaker if available
                speaker = self._find_speaker_for_position(idx)

                result = {
                    "match": self.text_content[idx:idx + len(query)],
                    "context": context,
                    "position": idx
                }

                if timestamp:
                    result["timestamp"] = timestamp

                if speaker:
                    result["speaker"] = speaker

                results.append(result)

                start_idx = idx + len(query)

        return results

    async def validate_content(self) -> bool:
        """Validate that audio content is accessible and can be processed"""
        if not self.is_connected:
            if not await self.connect():
                return False

        # Check that we have basic metadata
        if not self.audio_metadata:
            return False

        # If metadata only, we're done
        if self.metadata_only:
            return True

        # For full processing, check that required tools are available
        if self.speech_to_text:
            if not self._check_speech_to_text_available():
                self.logger.warning("Speech-to-text capability not available")
                return False

        return True

    async def _get_audio_metadata(self) -> None:
        """Extract metadata from audio file using FFmpeg"""
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
                self.logger.error(f"Error getting audio metadata: {stderr.decode()}")
                return

            import json
            metadata = json.loads(stdout.decode())

            # Extract useful information
            self.audio_metadata = {
                'format': metadata.get('format', {}),
                'duration': float(metadata.get('format', {}).get('duration', 0)),
                'size': int(metadata.get('format', {}).get('size', 0)),
                'bitrate': int(metadata.get('format', {}).get('bit_rate', 0)),
                'streams': []
            }

            # Process audio streams
            for stream in metadata.get('streams', []):
                stream_type = stream.get('codec_type')
                if stream_type == 'audio':
                    self.audio_metadata['streams'].append({
                        'codec': stream.get('codec_name'),
                        'channels': stream.get('channels'),
                        'sample_rate': stream.get('sample_rate'),
                        'bit_depth': stream.get('bits_per_sample')
                    })

        except Exception as e:
            self.logger.error(f"Error processing audio metadata: {str(e)}")

    async def process_audio(self) -> bool:
        """Process audio content by converting speech to text"""
        try:
            if not self.is_connected:
                if not await self.connect():
                    return False

            # If metadata only, just format the metadata as text
            if self.metadata_only:
                self.text_content = self._format_metadata_as_text()
                return True

            results = []

            # Process with speech-to-text if enabled
            if self.speech_to_text:
                # Detect language if requested
                if self.detect_language:
                    await self._detect_audio_language()

                # Segment speakers if requested
                if self.segment_speakers:
                    await self._segment_speakers()
                    transcript = self._format_speaker_segments()
                else:
                    transcript = await self._speech_to_text()

                if transcript:
                    results.append(f"=== AUDIO TRANSCRIPT ===\n{transcript}")

            # Add language detection results if available
            if self.detected_language:
                results.append(f"=== DETECTED LANGUAGE ===\n{self.detected_language}")

            # Add metadata
            metadata_text = self._format_metadata_as_text()
            results.append(f"=== AUDIO METADATA ===\n{metadata_text}")

            # Combine all results
            self.text_content = "\n\n".join(results)
            return bool(self.text_content)

        except Exception as e:
            self.logger.error(f"Error processing audio: {str(e)}")
            return False
        finally:
            # Clean up temporary files
            self._cleanup_temp_files()

    async def _speech_to_text(self) -> Optional[str]:
        """Convert speech to text using an available speech recognition library"""
        try:
            # Placeholder implementation using SpeechRecognition
            import speech_recognition as sr

            recognizer = sr.Recognizer()
            with sr.AudioFile(self.file_path) as source:
                audio_data = recognizer.record(source)

                # Use appropriate recognition based on detected language
                if self.detected_language:
                    # For non-English languages, use a language-specific recognizer if available
                    if self.detected_language.lower() != 'en':
                        try:
                            text = recognizer.recognize_google(
                                audio_data,
                                language=self.detected_language
                            )
                        except Exception:
                            # Fallback to default if language-specific fails
                            text = recognizer.recognize_google(audio_data)
                    else:
                        text = recognizer.recognize_google(audio_data)
                else:
                    # No language detected, use default
                    text = recognizer.recognize_google(audio_data)

                return text

        except ImportError:
            self.logger.error("SpeechRecognition library not available")
            return "Speech-to-text processing not available"
        except Exception as e:
            self.logger.error(f"Error in speech-to-text: {str(e)}")
            return "Error in speech-to-text processing"

    async def _detect_audio_language(self) -> None:
        """Detect the language spoken in the audio"""
        try:
            # This is a placeholder that should be implemented with a proper language detection system
            # For example, using Google Cloud Speech-to-Text, Azure Speech, etc.

            # Placeholder implementation
            import speech_recognition as sr

            recognizer = sr.Recognizer()
            with sr.AudioFile(self.file_path) as source:
                audio_data = recognizer.record(source)

                # Sample 10 seconds for language detection
                # This is a simplified approach and not accurate
                sample = audio_data  # In a real implementation, get a shorter sample

                # Detect language (Google's API doesn't directly support this,
                # so this is a placeholder)
                self.detected_language = 'en'  # Default to English

        except ImportError:
            self.logger.error("Language detection libraries not available")
        except Exception as e:
            self.logger.error(f"Error in language detection: {str(e)}")

    async def _segment_speakers(self) -> None:
        """Segment audio by different speakers"""
        try:
            # This is a placeholder that should be implemented with a proper speaker diarization system
            # For example, using pyannote.audio, resemblyzer, etc.

            # Placeholder implementation
            self.speaker_segments = [
                {
                    'speaker': 'Speaker 1',
                    'start': 0.0,
                    'end': self.audio_metadata.get('duration', 0),
                    'text': await self._speech_to_text()
                }
            ]

        except Exception as e:
            self.logger.error(f"Error in speaker segmentation: {str(e)}")

    def _format_speaker_segments(self) -> str:
        """Format speaker segments as readable text"""
        if not self.speaker_segments:
            return ""

        lines = []

        for segment in self.speaker_segments:
            start_time = str(timedelta(seconds=int(segment.get('start', 0))))
            end_time = str(timedelta(seconds=int(segment.get('end', 0))))
            speaker = segment.get('speaker', 'Unknown')
            text = segment.get('text', '')

            lines.append(f"[{start_time} - {end_time}] {speaker}: {text}")

        return "\n\n".join(lines)

    def _format_metadata_as_text(self) -> str:
        """Format audio metadata as readable text"""
        if not self.audio_metadata:
            return "No metadata available"

        lines = [
            f"Duration: {timedelta(seconds=int(self.audio_metadata.get('duration', 0)))}",
            f"Size: {self._format_size(self.audio_metadata.get('size', 0))}",
            f"Bitrate: {int(self.audio_metadata.get('bitrate', 0) / 1000)} kbps"
        ]

        for stream in self.audio_metadata.get('streams', []):
            stream_info = []
            if stream.get('codec'):
                stream_info.append(stream.get('codec'))
            if stream.get('channels'):
                stream_info.append(f"{stream.get('channels')} channels")
            if stream.get('sample_rate'):
                stream_info.append(f"{stream.get('sample_rate')} Hz")
            if stream.get('bit_depth'):
                stream_info.append(f"{stream.get('bit_depth')} bit")

            lines.append(f"Audio: {' '.join(stream_info)}")

        return "\n".join(lines)

    def _format_size(self, size_bytes: int) -> str:
        """Format size in bytes to human-readable form"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} PB"

    def _estimate_timestamp(self, position: int) -> Optional[str]:
        """Estimate audio timestamp based on text position"""
        # This is a rough estimation and would need to be improved in a real implementation
        if not self.text_content or not self.audio_metadata:
            return None

        if position < 0 or position >= len(self.text_content):
            return None

        # Simple linear mapping
        text_percentage = position / len(self.text_content)
        estimated_seconds = text_percentage * self.audio_metadata.get('duration', 0)

        return str(timedelta(seconds=int(estimated_seconds)))

    def _find_speaker_for_position(self, position: int) -> Optional[str]:
        """Find which speaker was talking at the given text position"""
        # This requires more sophisticated matching between transcript and diarization
        # This is a simplified placeholder implementation
        if not self.speaker_segments or len(self.speaker_segments) == 1:
            return self.speaker_segments[0].get('speaker') if self.speaker_segments else None

        # In a real implementation, would need to map text positions to timestamps
        # and timestamps to speaker segments
        return None

    def _check_speech_to_text_available(self) -> bool:
        """Check if speech-to-text capabilities are available"""
        try:
            import speech_recognition
            return True
        except ImportError:
            return False

    def _cleanup_temp_files(self) -> None:
        """Clean up temporary files"""
        for path in self.temp_files:
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except Exception as e:
                self.logger.error(f"Error cleaning up temp file {path}: {str(e)}")

    async def _process_content(self) -> None:
        """Process audio content and chunk it"""
        if not self.text_content:
            if not await self.process_audio():
                return

        self.chunks = self._chunk_text(self.text_content)
        source_desc = self.file_path if self.file_path else "audio data"
        self.logger.info(f"Created {len(self.chunks)} chunks from audio {source_desc}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._cleanup_temp_files()
