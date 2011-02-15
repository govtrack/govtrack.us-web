import sys

class Progress(object):
    def __init__(self, step=None, total=None, stop=None):
        if not total and not step:
            raise Exception('Both step and total arguments are None')
        if total and not step:
            step = int(total / 20)
        self.step = step
        self.count = 0
        self.total = total
        self.stop = stop
    
    def tick(self):
        self.count += 1
        if not self.count % self.step:
            if self.total:
                percents = ' [%d%%]' % int((self.count / float(self.total)) * 100)
            else:
                percents = ''
            print 'Processed %d records%s' % (self.count, percents)
        if self.count == self.stop:
            print 'Reached stop value %d' % self.stop
            sys.exit()
