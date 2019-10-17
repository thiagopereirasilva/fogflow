docker run -it --rm --name object_detector \
	-v `pwd`/test_object_detector.py:/object_detector.py \
	-v `pwd`/MobileNetSSD_deploy.caffemodel:/MobileNetSSD_deploy.caffemodel \
	-v `pwd`/MobileNetSSD_deploy.prototxt.txt:/MobileNetSSD_deploy.prototxt.txt \
	-v `pwd`/example.jpg:/example.jpg \
	mohaseeb/raspberrypi3-python-opencv \
	python /object_detector.py
