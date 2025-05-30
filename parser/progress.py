import sys
import logging

class Progress(object):
    def __init__(self, step=None, total=None, stop=None, name='items'):
        if not total and not step:
            raise Exception('Both step and total arguments are None/zero')
        if total and not step:
            step = max(int(total / 20), 1)
        self.step = step
        self.count = 0
        self.total = total
        self.stop = stop
        self.name = name
    
    def tick(self, x=None, y=None):
        self.count += 1
        if not self.count % self.step:
            if self.total:
                percents = ' [%d%%]' % int(round((self.count / float(self.total)) * 100))
            elif x and y:
                percents = ' [%d%%]' % int(round((x / float(y)) * 100))
            else:
                percents = ''
            logging.info('Processed %d %s%s' % (self.count, self.name, percents))
        if self.count == self.stop:
            logging.info('Reached stop value %d' % self.stop)
            sys.exit()
