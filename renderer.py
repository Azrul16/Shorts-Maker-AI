"""Vertical video renderer: CPU face camera and captions, NVENC H.264 encoding."""
from pathlib import Path
from summary import timeline, validate_spans
import math
import subprocess
import tempfile
import cv2
from captions import write_captions, write_srt
from keyframes import KeyframeCamera
from effects import punch_zoom
from story import story_plan
from framing import FaceCamera, fit_scene
from music import music_path, audio_filter
from runtime import NO_WINDOW, check_cancel, tool, probe, configure_processing


def render_clip(source, clip, transcript, destination, *, height=1920, follow=True, zoom=True, captions=True, nvenc=True, progress=None, cancel=None, framing="fill", music="off", music_level=.18, music_offset=0., normalize_audio=False, source_media=None, opening_title=None, output_size=None, preserve_frame=False):
    configure_processing()
    source, destination = Path(source).resolve(), Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.stem + ".partial.mp4")
    fps = 30
    width = 1080 if height == 1920 else 720
    if output_size is not None:
        width, height = output_size
    source_clip = clip
    spans = clip.spans or [dict(start=clip.start, end=clip.end)]
    if clip.spans:
        validate_spans(clip, (source_media or probe(source))["duration"])
    clip, transcript = timeline(clip, transcript)
    duration = clip.end - clip.start
    plan = story_plan(transcript,clip)
    total_frames = max(1, round(duration * fps))
    track = music_path(music)
    has_audio = (source_media if source_media is not None else probe(source)).get("has_audio", True)
    tracking = 'face'
    if preserve_frame:
        camera = SourceCamera()
        tracking, framing = 'source', 'source'
    elif clip.crop_keyframes:
        camera = KeyframeCamera(clip.crop_keyframes,clip.start,clip.end)
        tracking,framing = 'manual','fill'
    else:
        camera = FaceCamera(follow, zoom, mode="fill")
    dark_samples = 0
    cap = cv2.VideoCapture(str(source),cv2.CAP_FFMPEG,[cv2.CAP_PROP_N_THREADS,2])
    if not cap.isOpened():
        raise RuntimeError("Could not open video for face tracking.")
    source_fps = cap.get(cv2.CAP_PROP_FPS)
    if not math.isfinite(source_fps) or source_fps <= 0:
        cap.release()
        raise RuntimeError("The video has an invalid frame rate.")
    cap.set(cv2.CAP_PROP_POS_MSEC, spans[0]["start"] * 1000)
    process = None
    try:
        with tempfile.TemporaryDirectory(prefix="render-", dir=destination.parent) as temp:
            temp = Path(temp)
            has_overlay = captions or clip.effects=='energetic'
            if has_overlay:
                write_captions(temp / "captions.ass", transcript if captions else [], clip.start, clip.end,clip.caption_style,effects=clip.effects,title=opening_title or clip.title, output_size=(width,height))
            audio_source = source
            audio_start = source_clip.start
            if source_clip.spans and has_audio:
                if progress:
                    progress(0, 'Joining selected audio sections...')
                audio_source = temp / "joined.wav"
                prepare_audio(source, spans, audio_source, cancel)
                audio_start = 0
            command = [tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0", "-ss", str(audio_start), "-i", str(audio_source)]
            if not has_audio:
                # Keep source audio at input 1 for the common mixing path.
                command = command[:-4] + ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
            command += ['-filter_threads','2','-filter_complex_threads','2']
            if track:
                command += ["-stream_loop", "-1", "-ss", str(music_offset), "-i", str(track), "-filter_complex", audio_filter(duration, music_level,normalize_audio)]
            elif normalize_audio:
                command += ['-af','loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000']
            command += ["-map", "0:v:0", "-map", "[mixed]" if track else "1:a:0", "-t", str(duration)]
            if has_overlay:
                command += ["-vf", "ass=captions.ass"]
            if nvenc:
                command += ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "20", "-b:v", "0"]
            else:
                command += ["-c:v", "libx264", "-preset", "fast", "-crf", "20", "-threads", "4"]
            command += ["-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(partial)]
            logpath = temp / "ffmpeg.log"
            with logpath.open("wb") as log:
                process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log, cwd=temp, creationflags=NO_WINDOW)
                index = -1
                frame = None
                span_index, span_offset = 0, 0.
                totals = dict(samples=0, detections=0, body_detections=0, preserved_frames=0)
                try:
                    for n in range(total_frames):
                        check_cancel(cancel)
                        while span_index+1 < len(spans) and n/fps >= span_offset+spans[span_index]['end']-spans[span_index]['start']-1e-8:
                            span_offset += spans[span_index]['end']-spans[span_index]['start']
                            span_index += 1
                            cap.set(cv2.CAP_PROP_POS_MSEC, spans[span_index]['start']*1000)
                            index, frame = -1, None
                            if tracking == 'face':
                                for key in totals:
                                    totals[key] += getattr(camera, key)
                                camera = FaceCamera(follow, zoom, mode='fill')
                        desired = max(0, int((n/fps-span_offset) * source_fps))
                        while index < desired:
                            ok, decoded = cap.read()
                            if not ok:
                                # Container duration can include a few audio samples
                                # beyond the last video frame. Hold that frame briefly.
                                if frame is not None and n/fps-span_offset >= spans[span_index]['end']-spans[span_index]['start']-.15:
                                    index = desired
                                    break
                                raise RuntimeError("Video decoding ended before the selected clip finished.")
                            frame = decoded
                            index += 1
                        zoom_effect = punch_zoom(n/fps,duration,clip.effects,plan["punch_times"])
                        # Manual crop paths stay exact; only automatic cameras get accents.
                        cropped = camera.crop(frame, n / fps - span_offset, (width, height),effect_zoom=1. if tracking=='manual' else zoom_effect)
                        if n % fps == 0 and float(cv2.resize(cropped,(32,18)).mean()) < 5:
                            dark_samples += 1
                        if n == min(30, total_frames - 1):
                            ok, thumbnail = cv2.imencode('.jpg', cropped)
                            if ok:
                                destination.with_suffix('.jpg').write_bytes(thumbnail.tobytes())
                        process.stdin.write(memoryview(cropped))
                        if progress and n % 6 == 0:
                            progress(n / total_frames, f"{'GPU NVENC' if nvenc else 'CPU'} · frame {n + 1} / {total_frames}")
                    process.stdin.close()
                    while True:
                        check_cancel(cancel)
                        try:
                            code = process.wait(timeout=.25)
                            break
                        except subprocess.TimeoutExpired:
                            continue
                    if code:
                        raise RuntimeError(logpath.read_text(encoding="utf-8", errors="replace")[-1500:])
                except BrokenPipeError:
                    process.wait(timeout=15)
                    raise RuntimeError(logpath.read_text(encoding="utf-8", errors="replace")[-1500:]) from None
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
                    if not process.stdin.closed:
                        try:
                            process.stdin.close()
                        except BrokenPipeError:
                            pass
            if has_overlay:
                destination.with_suffix(".ass").write_bytes((temp / "captions.ass").read_bytes())
            if captions:
                write_srt(destination.with_suffix('.srt'),transcript,clip.start,clip.end)
        partial.replace(destination)
        if progress:
            progress(1, "Clip saved")
        return {"path": str(destination), "width": width, "height": height, "encoder": "h264_nvenc" if nvenc else "libx264", "dark_samples": dark_samples, "normalized_audio": normalize_audio, "caption_style": clip.caption_style, "effects": clip.effects, "face_samples": (camera.samples + totals["samples"]) if tracking == "face" else 0, "face_detections": (camera.detections + totals["detections"]) if tracking == "face" else 0, "tracking": tracking, "person_frames": (camera.body_detections + totals["body_detections"]) if tracking == "face" else 0, "framing": framing, "preserved_scene_frames": camera.preserved_frames + totals["preserved_frames"], "source_spans": source_clip.spans, "music": str(track) if track else None, "music_level": music_level if track else 0}
    finally:
        cap.release()
        if partial.exists():
            partial.unlink()


class SourceCamera:
    """Keep the original composition without unnecessary subject detection."""
    def __init__(self):
        self.preserved_frames = 0

    def crop(self, frame, t, output_size, effect_zoom=1.):
        self.preserved_frames += 1
        height, width = frame.shape[:2]
        if abs(width/height-output_size[0]/output_size[1]) < .01:
            return cv2.resize(frame, output_size, interpolation=cv2.INTER_AREA)
        return fit_scene(frame, output_size)


def prepare_audio(source, spans, destination, cancel=None):
    """Decode only retained audio ranges; tiny edge fades suppress cut clicks."""
    check_cancel(cancel)
    command = [tool('ffmpeg'), '-v', 'error', '-nostdin', '-y']
    filters = []
    for i, span in enumerate(spans):
        length = span['end']-span['start']
        command += ['-threads', '1', '-ss', str(span['start']), '-t', str(length), '-i', str(source)]
        filters.append(f'[{i}:a:0]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,apad,atrim=duration={length},asetpts=PTS-STARTPTS,afade=t=in:d=0.008,afade=t=out:st={max(0,length-.008)}:d=0.008[a{i}]')
    filters.append(''.join(f'[a{i}]' for i in range(len(spans)))+f'concat=n={len(spans)}:v=0:a=1[out]')
    command += ['-filter_complex_threads','2','-filter_complex',';'.join(filters),'-map','[out]','-c:a','pcm_s16le',str(destination)]
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=errors, creationflags=NO_WINDOW)
        try:
            while process.poll() is None:
                check_cancel(cancel)
                try:
                    process.wait(timeout=.1)
                except subprocess.TimeoutExpired:
                    pass
            if process.returncode:
                errors.seek(0)
                raise RuntimeError(errors.read().decode('utf-8',errors='replace')[-1500:])
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
