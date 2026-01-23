from picamera2 import Picamera2
import time
import json

print("Init Picamera2")
p = Picamera2()
config = p.create_video_configuration(main={'size':(1296,972), 'format':'YUV420'})
p.configure(config)
p.start()
print('Started')

try:
    print("Controls keys:", list(p.camera_controls.keys())[:5])
    print("Properties keys:", list(p.camera_properties.keys())[:5])
    print("Sensor modes:", p.sensor_modes)
except Exception as e:
    print(f"Error: {e}")

p.stop()
p.close()
