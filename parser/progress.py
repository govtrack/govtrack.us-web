import sys

class Progress(object):
    def __init__(self, step=None, total=None, stop=None, name='items'):
        if not total and not step:
            raise Exception('Both step and total arguments are None')
        if total and not step:
            step = int(total / 20)
        self.step = step
        self.count = 0
        self.total = total
        self.stop = stop
        self.name = name
    
    def tick(self):
        self.count += 1
        if not self.count % self.step:
            if self.total:
                percents = ' [%d%%]' % int((self.count / float(self.total)) * 100)
            else:
                percents = ''
            print 'Processed %d %s%s' % (self.count, self.name, percents)
        if self.count == self.stop:
            print 'Reached stop value %d' % self.stop
            sys.exit()
