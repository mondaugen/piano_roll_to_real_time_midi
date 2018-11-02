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
    raw_midi_frame_converter=raw_midi_frame(),
    program=0,
    transposition=0,
    n_pitches=88,
    velocity_scalar=100,
    channel=0):
        self.raw_midi_frame_converter = raw_midi_frame_converter
        self.transposition = transposition
        self.velocity_scalar = velocity_scalar
        # each row of _notes is (start_time,end_time,velocity,pitch)
        self._notes = np.full((n_pitches,4),0,dtype='float32')
        self._notes[:,-1]=np.arange(n_pitches)
        self._last_active = np.full(n_pitches,0,dtype='int32')
        self.channel = channel
    
    def _note_ons_from_notes(self,notes):
        ret = []
        for note in notes:
            ret.append(
            note_on_midi_msg(
            channel=self.channel,
            pitch=int(self.transposition + note[3]),
            velocity=0))
        return ret

    def _note_offs_from_notes(self,notes):
        ret = []
        for note in notes:
            ret.append(
            note_off_midi_msg(
            channel=self.channel,
            pitch=int(self.transposition + note[3]),
            velocity=0))
        return ret
            
    def __call__(self,frame):
        # where to hold result     
        events=[]
        # unpack timestamp and piano roll activations slice
        timestamp,pr_slice = self.raw_midi_frame_converter.unpack(frame)
        # find those that are active currently
        now_active = (pr_slice > 0).astype('int32')
        # new notes are ones that weren't active before
        new_notes = (self._last_active - now_active) < 0
        # off notes are ones that were active before and are now off
        off_notes = (self._last_active - now_active) > 0
        # store the time they went off using the timestamp
        self._notes[off_notes,1] = timestamp
        # make into midi note events
        events += self._note_offs_from_notes(self._notes[off_notes])
        # now turn them off
        self._last_active[off_notes] = 0
        # TODO timestamp not currently used, but available
        # mido doesn't have that precise of scheduling capabilities
        self._notes[new_notes,0] = timestamp
        self._notes[new_notes,2] = pr_slice[new_notes]
        # make the new notes
        events += self._note_ons_from_notes(self._notes[new_notes])
        self._last_active[new_notes] = 1
        return events

class midi_port:
    def send(ev):
        return NotImplemented
