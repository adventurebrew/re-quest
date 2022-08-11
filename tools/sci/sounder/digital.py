import wave

import av
import pyaudio

from utils import logger


def play_wave(wave):
    if wave:
        audio = pyaudio.PyAudio()
        stream = audio.open(format=audio.get_format_from_width(1),
                            channels=1,
                            rate=wave['freq'],
                            output=True)
        stream.write(wave['data'])
        stream.stop_stream()
        stream.close()
        audio.terminate()


def save_wave(wave_dict, input_file, save_file):
    if wave_dict:
        if not save_file:
            save_file = input_file + ".wav"

        with wave.open(save_file, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(1)
            w.setframerate(wave_dict['freq'])
            w.writeframes(wave_dict['data'])
        logger.info(f'Saved {save_file}')


def read_wav_file(input_digital):
    result = {}
    with wave.open(input_digital, 'rb') as w:
        if w.getnchannels() != 1:
            assert ValueError("wave file must have 1 channel (mono)")
        if w.getsampwidth() != 1:
            assert ValueError("wave file must be 8-bit")
        if w.getcomptype() != 'NONE':
            assert ValueError("wave file must be uncompressed")
        result['freq'] = w.getframerate()
        result['data'] = w.readframes(w.getnframes())
        if len(result['data']) > 0xffff:
            result['data'] = result['data'][:0xfff0]
            logger.info(
                f"Wave file is too big ({w.getnframes() / result['freq']:.1f} sec), slicing it to {len(result['data']) / result['freq']:.1f} sec")
    return result


def convert_audio_to_low_wav(input_file, output_file, layout='mono'):
    input_container = av.open(input_file)

    if input_container.streams.audio[0].codec_context.rate >= 22000:
        rate = 22000
    else:
        rate = 11000

    output_container = av.open(output_file, 'w')
    output_stream = output_container.add_stream('pcm_u8', rate, layout=layout)

    resampler = av.audio.resampler.AudioResampler('u8p', layout, rate)

    for frame in input_container.decode(audio=0):
        out_frames = resampler.resample(frame)
        for out_frame in out_frames:
            for packet in output_stream.encode(out_frame):
                output_container.mux(packet)

    # Flush stream
    for packet in output_stream.encode():
        output_container.mux(packet)

    output_container.close()
    return output_file
