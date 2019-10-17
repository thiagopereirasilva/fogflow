docker run -it --rm --name opencv \
       mohaseeb/raspberrypi3-python-opencv \
       python -c "import cv2; print(cv2.__version__)"
