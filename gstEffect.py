import os
import gi
import random
import time
from PIL import Image
from threading import Thread, Event

gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst

Gst.init(None)
audio_file = "Wesołych_Świąt.mp3"
image_file = "input.jpg"
def get_image_resolution(image_file):
    with Image.open(image_file) as img:
        return img.size  # zwraca (width, height)

def change_color_randomly(pipeline, element_name, stop_event):
    element = pipeline.get_by_name(element_name)

    while not stop_event.is_set():
        if element is not None:
            new_hue = random.uniform(-1, 1)
            element.set_property('hue', new_hue)
            print(f"Zmiana hue na: {new_hue} dla {element_name}")

        time_to_sleep = random.uniform(0.01, 0.1)
        print(f"Zmiana koloru za {time_to_sleep:.2f} sekund.")
        stop_event.wait(time_to_sleep)

def create_pipeline(output_file, audio_file, duration=None):
    width, height = get_image_resolution(image_file)
    # Ustal, jaka rozdzielczość ma być końcowa, na przykład 640x480
    final_width = 360
    final_height = 360
    audio_filename = os.path.splitext(os.path.basename(audio_file))[0]
    pipeline_str = f"""
        multifilesrc location="{image_file}" loop=true caps="image/jpeg,framerate=30/1" ! jpegdec ! videoconvert ! videoscale ! video/x-raw,width={final_width},height={final_height} ! videoconvert ! videorate ! video/x-raw,framerate=30/1 ! videoconvert ! textoverlay text="{audio_filename}" valignment=bottom halignment=left font-desc="Sans, 24" ! timeoverlay valignment=bottom halignment=right font-desc="Sans, 24" ! videobalance name=color_effect ! compositor name=comp
        filesrc location="{audio_file}" ! decodebin ! audioconvert ! audioresample ! audio/x-raw,rate=44100 ! tee name=t
        t. ! queue ! wavescope style=color-lines shader=0 name=wavescope_effect ! videobalance name=waveform_color_effect ! alpha name=alpha_filter alpha=0.2 ! videoconvert ! video/x-raw,width={final_width},height={final_height} ! comp.sink_1
        comp. ! videoconvert ! x264enc tune=zerolatency bitrate=2000 speed-preset=superfast ! mp4mux name=mux
        t. ! queue ! audioconvert ! audioresample ! audio/x-raw,rate=44100 ! avenc_aac bitrate=128000 ! mux.
        mux. ! filesink location={output_file}
    """

    pipeline = Gst.parse_launch(pipeline_str)

    if duration:
        multifilesrc = pipeline.get_by_name("multifilesrc0")
        if multifilesrc:
            multifilesrc.set_property("num-buffers", 30 * duration)  # 30 fps * duration

    return pipeline

def run_pipeline(pipeline, duration=None):
    stop_event = Event()

    # Thread to change color for video part
    color_thread = Thread(target=change_color_randomly, args=(pipeline, "color_effect", stop_event))
    color_thread.start()

    # Thread to change color (hue) for waveform part
    waveform_color_thread = Thread(target=change_color_randomly, args=(pipeline, "waveform_color_effect", stop_event))
    waveform_color_thread.start()

    pipeline.set_state(Gst.State.PLAYING)

    start_time = time.time()
    bus = pipeline.get_bus()

    while True:
        msg = bus.timed_pop_filtered(
            100 * Gst.MSECOND,
            Gst.MessageType.ERROR | Gst.MessageType.EOS
        )

        if msg:
            if msg.type == Gst.MessageType.ERROR:
                err, debug_info = msg.parse_error()
                print(f"Błąd: {err}, {debug_info}")
            elif msg.type == Gst.MessageType.EOS:
                print("Koniec strumienia (EOS)")
            break

        if duration and time.time() - start_time >= duration:
            print(f"Osiągnięto limit czasu {duration} sekund.")
            pipeline.send_event(Gst.Event.new_eos())
            break

    # Czekaj na zakończenie przetwarzania
    pipeline.set_state(Gst.State.NULL)
    stop_event.set()
    color_thread.join()
    waveform_color_thread.join()

def process_video(output_file, audio_file):
    """ Process video with length synchronized to audio file """
    audio_duration = get_audio_duration(audio_file)
    if audio_duration is None:
        print("Nie można uzyskać długości pliku audio. Proces przerwany.")
        return

    print(f"Tworzenie wideo o długości {audio_duration} sekund.")
    pipeline = create_pipeline(output_file, audio_file, duration=audio_duration)
    run_pipeline(pipeline, duration=audio_duration)

def get_audio_duration(audio_file):
    pipeline_str = f"filesrc location={audio_file} ! decodebin ! audioconvert ! audioresample ! fakesink"
    pipeline = Gst.parse_launch(pipeline_str)

    pipeline.set_state(Gst.State.PAUSED)

    bus = pipeline.get_bus()
    bus.timed_pop_filtered(Gst.CLOCK_TIME_NONE, Gst.MessageType.ASYNC_DONE)

    success, duration_ns = pipeline.query_duration(Gst.Format.TIME)
    pipeline.set_state(Gst.State.NULL)

    if success:
        return duration_ns / Gst.SECOND  # convert nanoseconds to seconds
    else:
        print("Nie udało się uzyskać długości audio.")
        return None

def main():
    audio_file = "Wesołych_Świąt.mp3"
    image_file = "input.jpg"
    # Tworzenie wideo testowego o długości audio
    process_video("wideo.mp4", audio_file)

if __name__ == "__main__":
    main()
