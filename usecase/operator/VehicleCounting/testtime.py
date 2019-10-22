import datetime
import time
import urllib


def getTimestamp(url):
    resp = urllib.urlopen(url)
    data = resp.info()
    return str(data['timestamp'])



if __name__ == '__main__':
    print("oiii")
    
    url = "http://10.7.162.10:8090/timestamp"
    initial_timestamp = datetime.datetime.strptime("2019-10-21 14:48:27.243860", '%Y-%m-%d %H:%M:%S.%f')
    print(initial_timestamp)

    actual_timetamp = datetime.datetime.strptime(getTimestamp(url), '%Y-%m-%d %H:%M:%S.%f')
    print(actual_timetamp)

    processing_time = actual_timetamp - initial_timestamp
    print(processing_time.total_seconds())

