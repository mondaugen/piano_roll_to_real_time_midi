import numpy as np
import mido
from threading import Thread
from queue import Queue
import time
from struct import Struct

class time_counter(Thread):
    def __init__(self,resolution):
        """ resolution is how often to increment the time counter and by how
        much """
        self.resolution = resolution
        self.count = 0
        self.done = True
        Thread.__init__(self)
    def set_count(self,count):
        """ We might not want to start at 0 """
        self.count = count
    def run(self):
        self.done = False
        while not self.done:
            time.sleep(self.resolution)
            self.count += self.resolution

class frame_midi_scheduler(Thread):
    def __init__(self,
    # where to read frames from
    # expects it to have next_frame() method, which blocks until a frame is available
    frame_stream, 
    # something counting the time
    counter,
    # something that converts frames to a list of MIDI events
    # must return empty list if no events are to be sent
    frame_midi_converter,
    # a queue for midi_events, this will put events onto that queue.
    # must have "put" method (e.g., it could be a subclass of queue.Queue)
    midi_event_queue,
    # if an event comes in late, it is discarded
    discard_late=True
    ): 
        self.frame_stream = frame_stream
        self.counter = counter
        self.done = True
        self.frame_midi_converter = frame_midi_converter
        self.midi_event_queue = midi_event_queue
        self.discard_late = discard_late
        Thread.__init__(self)
    def run(self):
        self.done = False
        while not self.done:
            frame = self.frame_stream.next_frame()
            time_stamp = self.frame_midi_converter.raw_midi_frame_converter.time_stamp(frame)
            if not self.counter.is_alive():
                # set the intial time to the time of this frame and start the
                # counter
                self.counter.set_count(
                time_stamp)
            if self.discard_late and (time_stamp < self.counter.count):
                # discard, too late
                continue
            # get midi events from frame
            midi_events = self.frame_midi_converter(frame)
            # put midi events into queue (will do nothing if midi_events is
            # empty)
            for event in midi_events:
                self.midi_event_queue.put(event)

class midi_event_player(Thread):
    def __init__(self,
    # queue where to look for MIDI events
    midi_event_queue,
    # something counting the time
    counter,
    # something responding to the send message, which will take midi events
    midi_port):
        self.done = True
        self.midi_event_queue = midi_event_queue
        self.counter = counter
        self.midi_port = midi_port
        Thread.__init__(self)
    def run(self):
        self.done = False
        while not self.done:
            while self.counter.count > self.midi_event_queue.queue[0].time_stamp:
                # TODO in a real time context, you would use a non-blocking get,
                # and keep looping until the queue is available, but then you
                # also wouldn't send the MIDI events this way (you would queue
                # them to the hardware with a time stamp)
                ev = self.midi_event_queue.get()
                self.midi_port.send(ev)

class raw_midi_frame:
    """ Routines for converting packed bytes into a midi event """
    def __init__(self,
    # the number of notes in piano roll frame
    n_notes=88,
    # the MIDI note of the lowest frame
    transposition=21):
        self.n_notes = n_notes
        self.transposition = transposition
        self._unpacker = Struct("d%df" % (self.n_notes,))
    def time_stamp(self,frame):
        # parse the time stamp, returns a double
        dat=self._unpacker.unpack(b)
        ts = dat[0]
        return ts
    def unpack(self,b):
        """ Returns 2 numpy arrays, one containing just the time stamp, the other the frame activations """
        dat=self._unpacker.unpack(b)
        ts = np.array(dat[0],dtype='float64')
        act = np.array(dat[1:],dtype='float32')
        return (ts,act)

class note_on_midi_msg:
    def __init__(self,
    channel=0,
    pitch,
    velocity):
        self.channel = channel
        self.pitch = pitch
        self.velocity = velocity

class note_off_midi_msg:
    def __init__(self,
    channel=0,
    pitch,
    velocity):
        self.channel = channel
        self.pitch = pitch
        self.velocity = velocity

class midi_event:
    """ A very simple implementation, just a time stamp and midi message. """
    def __init__(self,
    timestamp,
    msg):
        self.timestamp = timestamp
        self.msg = msg

class frame_midi_converter:
    def __init__(self,
    # a class that converts from raw bytes to (timestamp,activations) pair by
    # calling unpack
    raw_midi_frame_converter=raw_midi_frame()):
        self.raw_midi_frame_converter = raw_midi_frame_converter
    def __call__(self,frame):
        # TODO convert the frame to some midi events, a la
        # piano_transcriber/midi.py:midi_notes_from_frames

class midi_port:
    def send(ev):
        return NotImplemented
