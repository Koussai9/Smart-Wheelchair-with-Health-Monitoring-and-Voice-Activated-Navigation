import pyrebase
import serial
import pynmea2

firebaseConfig={
  "apiKey": "",
  "authDomain": "",
  "databaseURL": "",
  "projectId": "",
  "storageBucket": "",
  "messagingSenderId": "",
  "appId": ""
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
