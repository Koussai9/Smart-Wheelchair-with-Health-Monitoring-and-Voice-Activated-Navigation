import pyrebase
import serial
import pynmea2

firebaseConfig={
  "apiKey": "AIzaSyCiBYgnFxAXKBRIgxO-rUEJyMDTFbH5PHs",
  "authDomain": "wheel-f5238.firebaseapp.com",
  "databaseURL": "https://wheel-f5238-default-rtdb.firebaseio.com",
  "projectId": "wheel-f5238",
  "storageBucket": "wheel-f5238.appspot.com",
  "messagingSenderId": "851756482678",
  "appId": "1:851756482678:web:28cfcdbeb18eeab3b1df57"
    }

firebase=pyrebase.initialize_app(firebaseConfig)
db=firebase.database()
#id = "{:04d}".format(random.randint(0, 9999))
id = "9999"
#password = "1111"
#userlogin = {"Pass" : password}
#db.child(id).update(userlogin)

print(id)
#print(password)
while True:
        port="/dev/ttyAMA0"
        ser=serial.Serial(port, baudrate=9600, timeout=0.5)
        dataout = pynmea2.NMEAStreamReader()
        newdata=ser.readline()
        n_data = newdata.decode('latin-1')
        if n_data[0:6] == '$GPRMC':
                newmsg=pynmea2.parse(n_data)
                lat=newmsg.latitude
                lng=newmsg.longitude
                gps = "Latitude=" + str(lat) + " and Longitude=" + str(lng)
                print(gps)
                data = {"LAT": lat, "LNG": lng}
                db.child(id).update(data)
                print("Data sent")
