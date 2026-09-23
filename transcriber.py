"""Local Whisper transcription with word timings and GPU fallback."""
from pathlib import Path
import gc
import os
from runtime import ASSETS, Cancelled, check_cancel, enable_cuda_libraries


def transcribe(video_path: str, model_size: str = "small", *, device="auto", progress=None, cancel=None, word_timestamps=False) -> list[dict]:
    if not Path(video_path).is_file():
        raise FileNotFoundError(f"Video not found: {video_path}")
    enable_cuda_libraries()
    import ctranslate2
    from faster_whisper import WhisperModel

    def report(value, message):
        if progress:
            progress(value, message)
        else:
            print(message, flush=True)

    check_cancel(cancel)
    if device == "auto":
        try:
            device = "cuda" if ctranslate2.get_cuda_device_count() else "cpu"
        except Exception:
            device = "cpu"
    devices = [device, "cpu"] if device == "cuda" else ["cpu"]
    for selected in devices:
        model = None
        try:
            report(None, f"Loading Whisper {model_size} on {selected.upper()}. First use may download the model.")
            bundled = ASSETS / "models" / model_size
            model_source = str(bundled) if (bundled / "model.bin").exists() else model_size
            model = WhisperModel(model_source, device=selected, compute_type="int8_float16" if selected == "cuda" else "int8", cpu_threads=max(1, min(8, (os.cpu_count() or 4) - 2)))
            segments, info = model.transcribe(video_path, beam_size=5, word_timestamps=word_timestamps, vad_filter=True, condition_on_previous_text=False)
            transcript = []
            for segment in segments:
                check_cancel(cancel)
                item = {"start": segment.start, "end": segment.end, "text": segment.text.strip()}
                if word_timestamps:
                    item["words"] = [{"start": w.start, "end": w.end, "word": w.word.strip()} for w in (segment.words or [])]
                transcript.append(item)
                report(min(1, segment.end / max(info.duration, 1)), f"{selected.upper()} · {info.language.upper()} · {segment.end:.0f} / {info.duration:.0f} sec")
            report(1, f"Transcribed {len(transcript)} segments on {selected.upper()}")
            return transcript
        except Cancelled:
            raise
        except Exception as exc:
            if selected != "cuda":
                raise
            report(None, f"GPU transcription unavailable ({exc}); continuing on CPU.")
        finally:
            del model
            gc.collect()
    raise RuntimeError("Transcription failed.")
