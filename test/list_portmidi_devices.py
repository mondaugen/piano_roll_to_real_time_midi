import mido
import time

MIDO_BACKEND='mido.backends.portmidi'

mido.set_backend(MIDO_BACKEND)

print(mido.get_output_names())

name = mido.get_output_names()[0]

port = mido.open_output(name)

for p in [0,2,4,5,7,9,11,12]:
    port.send(mido.Message('note_on',channel=0,note=60+p,velocity=100))
    time.sleep(0.5)
    port.send(mido.Message('note_off',channel=0,note=60+p,velocity=0))

port.close()

port.close()
