import pr_to_mido_midi as ptmm
import sys
from queue import Queue
import signal

if len(sys.argv) < 2:
    in_fd = sys.stdin
else:
    in_fd = open(sys.argv[1],'rb',buffering=0)

done = False

def quit_cmd(sn,frame):
    done = True

signal.signal(signal.SIGINT,quit_cmd)

time_counter = ptmm.time_counter(0.1)
frame_stream=ptmm.midi_note_frame_stream_fd(in_fd)
midi_event_queue = Queue()

frame_midi_sched = ptmm.frame_midi_scheduler(
frame_stream,
time_counter,
frame_stream.get_frame_parser(),
midi_event_queue)

out_midi_port = ptmm.mido_midi_port(port_name='my_fluid_synth')

midi_event_player = ptmm.midi_event_player(
midi_event_queue,
time_counter,
out_midi_port)

midi_event_player.start()
frame_midi_sched.start()
# frame_midi_sched starts time_counter

while not done:
    # everything happening in background threads
    time.sleep(1)

for thread in [ frame_midi_sched, midi_event_player, time_counter ]:
    thread.done = True
    thread.join()

if in_fd != sys.stdin:
    in_fd.close()

print("test/pr_to_mido_midi_test.py Quitting")

sys.exit(0)

