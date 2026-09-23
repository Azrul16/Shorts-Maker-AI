"""Vertical video renderer: CPU face camera and captions, NVENC H.264 encoding."""
from pathlib import Path
import math
import subprocess
import tempfile
import cv2
from captions import write_captions
from framing import FaceCamera
from runtime import Cancelled, NO_WINDOW, check_cancel, tool


def render_clip(source, clip, transcript, destination, *, height=1920, follow=True, zoom=True, captions=True, nvenc=True, progress=None, cancel=None):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.stem + ".partial.mp4")
    fps = 30
    width = 1080 if height == 1920 else 720
    duration = clip.end - clip.start
    total_frames = max(1, round(duration * fps))
    camera = FaceCamera(follow, zoom)
    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        raise RuntimeError("Could not open video for face tracking.")
    source_fps = cap.get(cv2.CAP_PROP_FPS)
    if not math.isfinite(source_fps) or source_fps <= 0:
        cap.release()
        raise RuntimeError("The video has an invalid frame rate.")
    cap.set(cv2.CAP_PROP_POS_MSEC, clip.start * 1000)
    process = None
    try:
        with tempfile.TemporaryDirectory(prefix="render-", dir=destination.parent) as temp:
            temp = Path(temp)
            if captions:
                write_captions(temp / "captions.ass", transcript, clip.start, clip.end)
            command = [tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0", "-ss", str(clip.start), "-i", str(source), "-map", "0:v:0", "-map", "1:a:0", "-t", str(duration)]
            if captions:
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
                try:
                    for n in range(total_frames):
                        check_cancel(cancel)
                        desired = int(n * source_fps / fps)
                        while index < desired:
                            ok, decoded = cap.read()
                            if not ok:
                                raise RuntimeError("Video decoding ended before the selected clip finished.")
                            frame = decoded
                            index += 1
                        cropped = camera.crop(frame, n / fps, (width, height))
                        if n == min(30, total_frames - 1):
                            cv2.imwrite(str(destination.with_suffix(".jpg")), cropped)
                        process.stdin.write(cropped.tobytes())
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
            if captions:
                destination.with_suffix(".ass").write_bytes((temp / "captions.ass").read_bytes())
        partial.replace(destination)
        if progress:
            progress(1, "Clip saved")
        return {"path": str(destination), "encoder": "h264_nvenc" if nvenc else "libx264", "face_samples": camera.samples, "face_detections": camera.detections}
    finally:
        cap.release()
        if partial.exists():
            partial.unlink()
