import pr_to_mido_midi as ptmm
import sys
from queue import PriorityQueue
import signal
import time

done = False

prev_sigact=None

def quit_cmd(sn,frame):
    print("got SIGINT")
    # a better way is to make this the method of some object which is defined in
    # the above stack frame, avoids globals
    frame.f_globals['done'] = True
    signal.signal(signal.SIGINT,prev_sigact)

prev_sigact=signal.signal(signal.SIGINT,quit_cmd)

time_counter = ptmm.time_counter(0.1)
frame_stream=ptmm.test_midi_note_frame_stream(prob_on=0.01)
midi_event_queue = PriorityQueue()

frame_midi_converter = ptmm.frame_midi_converter(
raw_midi_frame_converter=frame_stream.get_frame_parser())

frame_midi_sched = ptmm.frame_midi_scheduler(
frame_stream,
time_counter,
frame_midi_converter,
midi_event_queue)

out_midi_port = ptmm.mido_midi_port(port_name='my_fluid_synth')

midi_event_player = ptmm.midi_event_player(
midi_event_queue,
time_counter,
out_midi_port)

midi_event_player.start()
frame_midi_sched.start()
# frame_midi_sched starts time_counter
time.sleep(1)
if not midi_event_player.is_alive():
    raise Exception("midi_event_player is not alive!")
if not frame_midi_sched.is_alive():
    raise Exception("frame_midi_sched is not alive!")

while not done:
    # everything happening in background threads
    time.sleep(1)

print("test/pr_to_mido_midi_test.py Quitting")

for thread in [ frame_midi_sched, midi_event_player, time_counter ]:
    midi_event_queue.queue = []
    thread.done = True
    thread.join()

print("test/pr_to_mido_midi_test.py Quit")

sys.exit(0)

