# rate limited bot

from telegram import Bot
from telegram.utils.request import Request
from time import time, sleep
from threading import Lock

from config import TOKEN, WORKERS



class Delayed:
    '''
        I want my return code back
        Do not be afraid, we have more than enough threads.
    '''

    def __init__(self, burst_limit=30, time_limit_ms=1000):
        self.burst_limit = burst_limit
        self.time_limit = time_limit_ms / 1000
        self._times = []
        self._lock = Lock()
    def __call__(self, func, *args, **kwargs):
        try:
            self._lock.acquire()
            # delay routine
            now = time()
            t_delta = now - self.time_limit  # calculate early to improve perf.
            if self._times and t_delta > self._times[-1]:
                # if last call was before the limit time-window
                # used to impr. perf. in long-interval calls case
                self._times = [now]
            else:
                # collect last in current limit time-window
                self._times = [t for t in self._times if t >= t_delta]
                self._times.append(now)
        finally:
            self._lock.release()  # to prevent dead lock
        if len(self._times) >= self.burst_limit:  # if throughput limit was hit
            sleep(self._times[1] - t_delta)
        return func(*args, **kwargs)
    def delayed(self, func):
        '''
            @Delayed().delayed
        '''
        def wrapped(*args, **kwargs):
            return self(func, *args, **kwargs)
        return wrapped

class DelayedMessage:
    def __init__(self,
                 all_burst_limit=30,
                 all_time_limit_ms=1000,
                 group_burst_limit=20,
                 group_time_limit_ms=60000):
        self._all_delay = Delayed(all_burst_limit, all_time_limit_ms)
        self._group_delay = Delayed(group_burst_limit, group_time_limit_ms)

    def delayed(self, func):
        '''
            @DelayedMessage().delayed
        '''
        def wrapped(*args, **kwargs):
            dl = self._group_delay if kwargs.pop('isgroup', True) else self._all_delay
            return dl(func, *args, **kwargs)
        return wrapped

delayed_message = DelayedMessage()
delayed_actions = Delayed(burst_limit=10, time_limit_ms=10000)
class MQBot(Bot):
    '''A subclass of Bot which delegates send method handling to MQ'''
    def __init__(self, *args, **kwargs):
        super(MQBot, self).__init__(*args, **kwargs)

    @delayed_message.delayed
    def send_message(self, *args, **kwargs):
        '''Wrapped method would accept new `queued` and `isgroup`
        OPTIONAL arguments'''
        return super(MQBot, self).send_message(*args, **kwargs)

    @delayed_actions.delayed
    def kick_chat_member(self, *args, **kwargs):
        return super(MQBot, self).kick_chat_member(*args, **kwargs)

    @delayed_actions.delayed
    def restrict_chat_member(self, *args, **kwargs):
        return super(MQBot, self).restrict_chat_member(*args, **kwargs)

    @delayed_actions.delayed
    def delete_message(self, *args, **kwargs):
        return super(MQBot, self).delete_message(*args, **kwargs)

mqbot = MQBot(TOKEN, request=Request(con_pool_size=WORKERS+4))
