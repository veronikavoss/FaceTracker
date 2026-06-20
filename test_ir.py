"""IR 카메라 진단 - CPU 메모리 모드 + SoftwareBitmap 강제"""
import sys
import asyncio
import numpy as np
import time

import winrt.windows.media.capture as wmc
import winrt.windows.media.capture.frames as wmcf
import winrt.windows.graphics.imaging as wgi
import winrt.windows.foundation.collections as wfc

async def step_test():
    groups = await wmcf.MediaFrameSourceGroup.find_all_async()
    selected_group = None
    selected_source_info = None
    for group in groups:
        for si in group.source_infos:
            if si.source_kind == wmcf.MediaFrameSourceKind.INFRARED:
                selected_group = group
                selected_source_info = si
                break
        if selected_group:
            break
    
    if not selected_group:
        print("IR 없음", flush=True)
        return
    
    print(f"IR 발견: {selected_group.display_name}", flush=True)
    
    mc = wmc.MediaCapture()
    settings = wmc.MediaCaptureInitializationSettings()
    settings.source_group = selected_group
    settings.streaming_capture_mode = wmc.StreamingCaptureMode.VIDEO
    settings.memory_preference = wmc.MediaCaptureMemoryPreference.CPU
    
    print("초기화 중...", flush=True)
    await mc.initialize_with_settings_async(settings)
    print("초기화 완료", flush=True)
    
    source = mc.frame_sources[selected_source_info.id]
    fmt = source.current_format
    print(f"소스: {fmt.subtype}, {fmt.video_format.width}x{fmt.video_format.height}", flush=True)
    
    reader = await mc.create_frame_reader_async(source)
    status = await reader.start_async()
    print(f"리더 시작: {status}", flush=True)
    
    for i in range(50):
        fr = reader.try_acquire_latest_frame()
        if fr:
            vmf = fr.video_media_frame
            sb = vmf.software_bitmap if vmf else None
            if sb:
                w, h = sb.pixel_width, sb.pixel_height
                print(f"프레임 획득! {w}x{h}, format={sb.bitmap_pixel_format}", flush=True)
                
                buf = sb.lock_buffer(wgi.BitmapBufferAccessMode.READ)
                ref = buf.create_reference()
                
                try:
                    data = np.frombuffer(ref, dtype=np.uint8)
                    print(f"np.frombuffer 성공: len={len(data)}, min={data.min()}, max={data.max()}", flush=True)
                except TypeError:
                    raw_bytes = bytes(ref)
                    data = np.frombuffer(raw_bytes, dtype=np.uint8)
                    print(f"bytes() 변환 성공: len={len(data)}, min={data.min()}, max={data.max()}", flush=True)
                
                ref.close()
                buf.close()
                fr.close()
                break
            else:
                if i < 5:
                    print(f"  attempt {i}: software_bitmap=None", flush=True)
            fr.close()
        else:
            if i % 10 == 0:
                print(f"  attempt {i}: frame=None", flush=True)
        time.sleep(0.1)
    else:
        print("50회 시도 후에도 프레임 없음", flush=True)
    
    await reader.stop_async()
    mc.close()
    print("완료", flush=True)

asyncio.run(step_test())
