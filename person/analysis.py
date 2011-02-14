import os

def load_data(person):
    image = 'data/us/112/stats/person/sponsorshipanalysis/%d.png' % person.pk
    if os.path.exists(image):
        image = '/' + image
    else:
        image = None

    data = {'image': image}

    fnames = [
        'data/us/112/stats/sponsorshipanalysis_h.txt',
        'data/us/112/stats/sponsorshipanalysis_s.txt',
    ]
    alldata = open(fnames[0]).read() + open(fnames[1]).read()
    for line in alldata.splitlines():
        chunks = [x.strip() for x in line.strip().split(',')]
        if chunks[0] == str(person.pk):
            data['ideology'] = chunks[1]
            data['leadership'] = chunks[2]
            data['name'] = chunks[3]
            data['party'] = chunks[4]
            data['description'] = chunks[5]
            return data
    return None
