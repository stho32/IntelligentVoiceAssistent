# PyAudio API Reference

> PyAudio v0.2.14 -- Python bindings for PortAudio v19.
> Cross-platform audio I/O (Linux, macOS, Windows).
> Install: `pip install pyaudio` (requires PortAudio system library on Linux: `apt install portaudio19-dev`)

## Quick Start

```python
import pyaudio

p = pyaudio.PyAudio()

# Record from microphone
stream = p.open(
    format=pyaudio.paInt16,
    channels=1,
    rate=16000,
    input=True,
    frames_per_buffer=1024
)
data = stream.read(1024)  # returns bytes

# Playback
stream_out = p.open(
    format=pyaudio.paInt16,
    channels=1,
    rate=16000,
    output=True
)
stream_out.write(data)

# Cleanup (mandatory)
stream.stop_stream()
stream.close()
stream_out.stop_stream()
stream_out.close()
p.terminate()
```

## PyAudio Class

### Constructor

```python
p = pyaudio.PyAudio()
```

Initializes PortAudio and acquires system resources. Must be paired with `p.terminate()`.

### open() -- Create a Stream

```python
stream = p.open(
    rate=16000,                  # Sampling rate in Hz
    channels=1,                  # Number of audio channels
    format=pyaudio.paInt16,      # Sample format constant
    input=False,                 # True to enable input (microphone)
    output=False,                # True to enable output (playback)
    input_device_index=None,     # Device index (None = system default)
    output_device_index=None,    # Device index (None = system default)
    frames_per_buffer=0,         # Frames per buffer (0 = automatic)
    start=True,                  # Start streaming immediately
    stream_callback=None,        # Callback for non-blocking mode
    input_host_api_specific_stream_info=None,
    output_host_api_specific_stream_info=None,
)
```

Returns a `pyaudio.Stream` instance.

**Input stream (microphone):**

```python
stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000,
                input=True, frames_per_buffer=1024)
```

**Output stream (playback):**

```python
stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000,
                output=True)
```

**Full-duplex (simultaneous input + output):**

```python
stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000,
                input=True, output=True, frames_per_buffer=1024)
```

### Device Enumeration

```python
p.get_device_count()                    # Total number of audio devices (int)
p.get_device_info_by_index(i)           # Dict with device info for index i
p.get_default_input_device_info()       # Dict for default input device
p.get_default_output_device_info()      # Dict for default output device
```

**Device info dict keys:** `name`, `index`, `hostApi`, `maxInputChannels`, `maxOutputChannels`, `defaultSampleRate`, `defaultLowInputLatency`, `defaultHighInputLatency`, `defaultLowOutputLatency`, `defaultHighOutputLatency`.

**List all devices:**

```python
p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    print(f"{i}: {info['name']} (in={info['maxInputChannels']}, out={info['maxOutputChannels']})")
p.terminate()
```

**Select specific device:**

```python
# Find device by name
def find_device(p, name_substring, input=True):
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        channels_key = 'maxInputChannels' if input else 'maxOutputChannels'
        if name_substring.lower() in info['name'].lower() and info[channels_key] > 0:
            return i
    return None

idx = find_device(p, "USB")
stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000,
                input=True, input_device_index=idx, frames_per_buffer=1024)
```

### Format Validation

```python
p.is_format_supported(
    rate=16000,
    input_device=0,        # device index
    input_channels=1,
    input_format=pyaudio.paInt16,
    output_device=None,
    output_channels=None,
    output_format=None,
)
# Returns True or raises ValueError
```

### Host API Methods

```python
p.get_host_api_count()                  # Number of host APIs
p.get_default_host_api_info()           # Dict for default host API
p.get_host_api_info_by_index(i)         # Dict for host API at index i
```

### Helper Methods

```python
p.get_sample_size(pyaudio.paInt16)      # Returns 2 (bytes per sample)
p.get_format_from_width(2)              # Returns paInt16 (width in bytes)
p.get_format_from_width(2, unsigned=False)  # Signed variant
```

### Cleanup

```python
p.terminate()  # MUST be called for every PyAudio instance
```

## Stream Class

### Audio I/O (Blocking Mode)

```python
stream.read(num_frames, exception_on_overflow=True)
# Returns bytes. Reads num_frames audio frames from the input buffer.

stream.write(frames, num_frames=None, exception_on_underflow=False)
# Writes audio bytes to the output buffer.
# num_frames is inferred from len(frames) if omitted.
```

### Stream Control

```python
stream.start_stream()      # Begin streaming (called automatically if start=True)
stream.stop_stream()       # Pause streaming
stream.close()             # Close the stream and release resources
stream.is_active()         # True if stream is currently processing audio
stream.is_stopped()        # True if stream is stopped
```

### Buffer Status

```python
stream.get_read_available()    # Frames available to read without blocking
stream.get_write_available()   # Frames available to write without blocking
```

### Stream Info

```python
stream.get_input_latency()     # Input latency in seconds (float)
stream.get_output_latency()    # Output latency in seconds (float)
stream.get_time()              # Stream time (float)
stream.get_cpu_load()          # CPU load (float, always 0.0 in blocking mode)
```

## Non-Blocking Mode (Callbacks)

```python
def callback(in_data, frame_count, time_info, status_flags):
    """
    Args:
        in_data: Recorded audio bytes (None if output-only stream)
        frame_count: Number of frames to process
        time_info: Dict with timing information
        status_flags: PortAudio status flags

    Returns:
        (out_data, flag) where flag is one of:
            pyaudio.paContinue  (0) -- keep streaming
            pyaudio.paComplete  (1) -- finish after this buffer
            pyaudio.paAbort     (2) -- stop immediately
    """
    # Example: pass-through
    return (in_data, pyaudio.paContinue)

stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000,
                input=True, output=True, frames_per_buffer=1024,
                stream_callback=callback)
# Stream runs in a separate thread. Do NOT call stream.read() or stream.write().
```

## Format Constants

| Constant          | Bytes/Sample | Description             |
|-------------------|-------------|-------------------------|
| `pyaudio.paFloat32` | 4         | 32-bit floating point   |
| `pyaudio.paInt32`   | 4         | 32-bit signed integer   |
| `pyaudio.paInt24`   | 3         | 24-bit signed integer   |
| `pyaudio.paInt16`   | 2         | 16-bit signed integer   |
| `pyaudio.paInt8`    | 1         | 8-bit signed integer    |
| `pyaudio.paUInt8`   | 1         | 8-bit unsigned integer  |

**Most common:** `paInt16` for recording/speech, `paFloat32` for processing/ML.

## Module-Level Functions

```python
pyaudio.get_sample_size(format)          # Bytes per sample for format constant
pyaudio.get_format_from_width(width, unsigned=True)  # Width (1-4 bytes) -> format
pyaudio.get_portaudio_version()          # PortAudio version number (int)
pyaudio.get_portaudio_version_text()     # PortAudio version string
```

## Context Manager Support

**PyAudio does NOT natively implement `__enter__` / `__exit__`.** Neither `PyAudio` nor `Stream` can be used with `with` statements out of the box. Always use explicit cleanup:

```python
p = pyaudio.PyAudio()
stream = None
try:
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000,
                    input=True, frames_per_buffer=1024)
    # ... use stream ...
finally:
    if stream is not None:
        stream.stop_stream()
        stream.close()
    p.terminate()
```

Note: The fork `pyaudiowpatch` adds context manager support, but the standard `pyaudio` package does not.

## Complete Examples

### Record 5 Seconds to WAV File

```python
import wave
import pyaudio

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
RECORD_SECONDS = 5

p = pyaudio.PyAudio()
stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                input=True, frames_per_buffer=CHUNK)

frames = []
for _ in range(0, RATE // CHUNK * RECORD_SECONDS):
    data = stream.read(CHUNK)
    frames.append(data)

stream.stop_stream()
stream.close()
p.terminate()

with wave.open("output.wav", "wb") as wf:
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(pyaudio.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b"".join(frames))
```

### Play a WAV File

```python
import wave
import pyaudio

CHUNK = 1024

with wave.open("output.wav", "rb") as wf:
    p = pyaudio.PyAudio()
    stream = p.open(
        format=p.get_format_from_width(wf.getsampwidth()),
        channels=wf.getnchannels(),
        rate=wf.getframerate(),
        output=True,
    )
    while len(data := wf.readframes(CHUNK)):
        stream.write(data)

    stream.close()
    p.terminate()
```

## Sources

- [PyAudio Documentation](https://people.csail.mit.edu/hubert/pyaudio/docs/)
- [PyAudio Homepage](https://people.csail.mit.edu/hubert/pyaudio/)
- [PyAudio on PyPI](https://pypi.org/project/PyAudio/)
