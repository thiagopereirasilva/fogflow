FROM mohaseeb/raspberrypi3-python-opencv

RUN mkdir /task
ADD main.py /task
ADD requirements.txt  /task
ADD MobileNetSSD_deploy.caffemodel /task
ADD MobileNetSSD_deploy.prototxt.txt /task
WORKDIR /task

RUN pip install -r requirements.txt

CMD ["python", "./main.py"]
