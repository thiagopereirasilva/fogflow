import datetime
import time
import urllib
import json


def getTimestamp(url):
    resp = urllib.urlopen(url)
    data = resp.info()
    return str(data['timestamp'])


if __name__ == '__main__':
    url = "http://10.7.162.10:8090/timestamp"
    #initial_timestamp = datetime.datetime.strptime("2019-10-21 1448:27.243860", '%Y-%m-%d %H:%M:%S.%f')
    #now = datetime.datetime.now()

    datetimeFormat = '%Y-%m-%d_%H-%M-%S-%f'
    initial_timestamp = ''
    with open('CameraMotion.json') as json_file:
        data = json.load(json_file)

    for key, value in data.iteritems():
        if key == 'contextElements':
            for value in data['contextElements']:
                for obj in value['attributes']:
                    if(obj['name'] == 'timestamp'):
                        initial_timestamp = datetime.datetime.strptime(obj['value'], datetimeFormat)

    print("Initial: ", str(initial_timestamp))
    print(type(initial_timestamp))

    actual_timetamp = datetime.datetime.strptime(
        getTimestamp(url), datetimeFormat)
    print("Server: ", str(actual_timetamp))
    print(type(actual_timetamp))

    diff = actual_timetamp - initial_timestamp
    print("Diff: ", diff)
    print(type(diff))
