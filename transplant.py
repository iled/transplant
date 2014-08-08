from subprocess import Popen
import tempfile
import zmq


"""Transplant is a Python client for remote code execution

It can start and connect Matlab servers and send them messages. All
messages are JSON-encoded strings. All messages are dictionaries with
at least one key: 'type'.

Depending on the message type, other keys may or may not be set.

These message types are implemented:
- 'eval': the server evaluates the content of the message.
- 'die': the server closes its 0MQ session and quits.
- 'put': saves the 'value' as a global variable called 'name'.
- 'get': retrieves the global variable 'name'.
- 'call': call function 'name' with 'args' and 'nargout'.

These response types are implemented:
- 'ack': the server received the message successfully.
- 'error': there was an error while handling the message.
- 'value': returns a value.

"""


class Matlab:
    """An instance of Matlab, running in its own process."""

    def __init__(self):
        """Starts a Matlab instance and opens a communication channel."""
        self.ipcfile = tempfile.NamedTemporaryFile()
        self.context = zmq.Context.instance()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.bind('ipc://' + self.ipcfile.name)
        self.process = Popen(['matlab', '-nodesktop', '-nosplash',
                              '-r', "transplant {}".format('ipc://' + self.ipcfile.name)])

    def eval(self, string):
        """Send some code to Matlab to execute."""
        self.send_message('eval', string=string)

    def put(self, name, value):
        """Save a named variable."""
        self.send_message('put', name=name, value=value)

    def get(self, name):
        """Retrieve a named variable."""
        response = self.send_message('get', name=name)
        return response['value']

    def call(self, name, args, nargout=-1):
        """Call a Matlab function."""
        args.append('dummy') # force non-numeric
        response = self.send_message('call', name=name, args=args,
                                     nargout=nargout)
        if response['type'] == 'value':
            return response['value']

    def __del__(self):
        """Close the connection, and kill the process."""
        self.send_message('die')
        self.process.terminate()

    def send_message(self, msg_type, **kwargs):
        """Send a message and return the response"""
        self.socket.send_json(dict(kwargs, type=msg_type))
        response = self.socket.recv_json()
        if response['type'] == 'error':
            # Create a pretty backtrace almost like Python's:
            trace = 'Traceback (most recent call last):\n'
            for frame in reversed(response['stack']):
                trace += '  File "{file}", line {line}, in {name}\n'.format(**frame)
                trace += '    ' + open(frame['file'], 'r').readlines()[frame['line']-1].strip(' ')
            raise RuntimeError('{message} ({identifier})\n'.format(**response) + trace)
        return response


if __name__ == '__main__':
    m = Matlab()
    m.put('name', 'Matlab')
    m.eval("disp(['Hello, ' name '!'])")
    print('size([1 2 3]) = ', m.call('size', [[1, 2, 3]]))
    print('deal(1, 2) = ', m.call('deal', [1, 2], nargout=2))
    print('max([1 2 3]) = ', m.call('max', [[1, 2, 3]]), '(no nargout)')
    print('max([1 2 3]) = ', m.call('max', [[1, 2, 3]], nargout=0), '(nargout = 0)')
    print('max([1 2 3]) = ', m.call('max', [[1, 2, 3]], nargout=1), '(nargout = 1)')
    print('max([1 2 3]) = ', m.call('max', [[1, 2, 3]], nargout=2), '(nargout = 2)')
    m.eval("plot(randn(100,1)); drawnow();")
