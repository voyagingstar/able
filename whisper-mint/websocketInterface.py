import asyncio
import websockets
import time,os
import numpy as np
import sounddevice as sd
from timer import Timer
import soundfile as sf
from transcribe import model

import ffmpeg
import numpy as np

ws=None

def transcription():
    try:
        # This launches a subprocess to decode audio while down-mixing and resampling as necessary.
        # Requires the ffmpeg CLI and `ffmpeg-python` package to be installed.
        out, _ = (
            ffmpeg.input('action.wav', threads=0)
            .output("-", format="s16le", acodec="pcm_s16le", ac=1, ar=16000)
            .run(capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as e:
        raise RuntimeError(f"Failed to load audio: {e.stderr.decode()}") from e

    arr = np.frombuffer(out, np.int16).flatten().astype(np.float32) / 32768.0
    result = model.transcribe(arr)
    os.remove("action.wav")
    print(result["text"])
    asyncio.run(send_message('stt:' + result["text"]))
    # send_message('stt:' + result["text"])

async def record_buffer(**kwargs):
    print('Start Listening ...')
 
    # loop = asyncio.get_event_loop()
    event = asyncio.Event()
    idx = 0
    idy = 0
    threshold = 10
    listening_initialized = False
    timer = Timer()
    prefix_indata = np.empty((100_000_000, 1), dtype='float32')
    buffer = np.empty((100_000_000, 1), dtype='float32')
    # q = queue.Queue()

    def callback(indata, frame_count, time_info, status):
        # print(np.concatenate(indata, axis=0))
        nonlocal idx, idy, listening_initialized
        nonlocal buffer, prefix_indata, threshold

        # print(prefix_indata.size , prefix_indata.size - idy ,indata.sie)

        if prefix_indata.size - idy < indata.size:
            prefix_indata = np.empty((100_000_000, 1), dtype='float32')
            idy = 0

        else:
            prefix_indata[idy: idy + len(indata)] = indata

            idy += len(indata)

        # calc abs of samples -> x
        x = np.absolute(indata)

        # calc volume -> y
        y = np.sum(x)

        # volume control y > threshold
        if y > threshold:
            # print(y)

            if listening_initialized:
                # print('add highs to listening')
                buffer[idx:idx + len(indata)] = indata
                idx += len(indata)
                timer.stop()
            else:
                # print('Start Listening')

                listening_initialized = True
                threshold = 5

                # here idx is 0
                buffer[idx:100] = prefix_indata[-101:-1]

                buffer[101:101 + len(indata)] = indata
                idx += len(indata)
        else:
            if listening_initialized:
                if timer.is_running():
                    if timer.is_timeout():
                        threshold = 10

                        buffer = buffer[0:idx]

                        with sf.SoundFile('./action.wav', mode='x', samplerate=16000,
                                          channels=1) as file:
                            file.write(buffer)
                            file.close()
                   

                        # asyncio.create_task()
                        transcription()

                        listening_initialized = False
                        timer.stop()
                        idx = 0
                        buffer = np.empty((100_000_000, 1), dtype='float32')
                        prefix_indata = np.empty(
                            (100_000_000, 1), dtype='float32')

                        # loop.call_soon_threadsafe(event.set)
                        # stream.abort()
                        # raise sd.CallbackStop
                    else:
                        # print('await timer')

                        buffer[idx:idx + len(indata)] = indata
                        idx += len(indata)
                else:
                    # print('add lows to listening')

                    timer.start()
                    buffer[idx:idx + len(indata)] = indata
                    idx += len(indata)
            else:
                # print('stop timer')

                timer.stop()

    stream = sd.InputStream(callback=callback, dtype=buffer.dtype,
                            channels=1, samplerate=16000, **kwargs)
    with stream:
        await event.wait()


async def connectWebSocket(uri):
    global ws
    another_task = None

    while True:
        try:
            async with websockets.connect(uri) as websocket:
                # Send and receive messages using the WebSocket connection
                ws=websocket
                await send_message("sttpid:"+str(os.getpid()))

                if not another_task:
                    another_task = asyncio.create_task(record_buffer())
                    print("Started another task")

                # Wait for the connection to close
                await websocket.wait_closed()

                # Handle the connection close event
                print("Connection closed")
                if another_task:
                    another_task.cancel()
                    another_task = None
                    print("Stopped another task")
        except:
            print("Connection error. Retrying in 1 second.")
            if another_task:
                another_task.cancel()
                another_task = None
                print("Stopped another task. Retrying...")
            time.sleep(1)

async def send_message(message):
    await ws.send(message)
    # print(f"Sent message to server: {message}")

