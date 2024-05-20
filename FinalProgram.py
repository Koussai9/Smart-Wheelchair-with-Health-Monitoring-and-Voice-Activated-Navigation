import time
import max30100
from RPLCD.i2c import CharLCD
import smbus2
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import pyrebase
import sounddevice as sd
import soundfile as sf
import speech_recognition as sr
import threading
import serial
import pynmea2
import requests

# Initialize devices and load the machine learning model
i2c_bus = smbus2.SMBus(1)
mx30 = max30100.MAX30100(i2c=i2c_bus)
mx30.enable_spo2()
lcd = CharLCD(i2c_expander='PCF8574', address=0x27, port=3)

# Initialize Firebase
firebaseConfig = {
    "apiKey": "",
    "authDomain": "",
    "databaseURL": "",
    "projectId": "",
    "storageBucket": "",
    "messagingSenderId": "",
    "appId": ""
}

firebase = pyrebase.initialize_app(firebaseConfig)
db = firebase.database()
child_id = "9999"  # Set the ID to "9999"

# Get Firebase Data
def get_data(child_id):
    try:
        data = db.child(child_id).get().val()
        if data is not None:
            return data
        else:
            return "No data found for ID: " + child_id
    except Exception as e:
        return "Error occurred: " + str(e)

# Machine Learning Preparation
data = pd.read_csv('Data.csv')
X = data.drop(['id', 'cardio'], axis=1)
y = data['cardio']
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)
X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)
model = LogisticRegression(random_state=42)
model.fit(X_train, y_train)

def predict_cardio_case(input_data):
    df = pd.DataFrame([input_data], columns=X.columns)
    scaled_features = scaler.transform(df)
    return model.predict(scaled_features)[0]

def record_audio(filename, duration, samplerate):
    print("Recording...")
    audio_data = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='float32')
    sd.wait()
    sf.write(filename, audio_data, samplerate)
    print("Recording finished.")

def audio_to_text(filename):
    recognizer = sr.Recognizer()
    with sr.AudioFile(filename) as source:
        audio = recognizer.record(source)
        try:
            return recognizer.recognize_google(audio, language="en-US")
        except sr.UnknownValueError:
            print("Speech recognition could not understand the audio")
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service: {e}")
    return None

def check_text_in_firebase(text):
    marked_locations = db.child("9999").child("MarkedLocations").get().val()
    if marked_locations:
        for location, data in marked_locations.items():
            if location.lower() in text.lower():
                print(f"Match found: {location}")
                return data.get("LAT"), data.get("LNG")  # Return LAT and LNG if match found
    return None, None  # Return None if no match found

def get_route(origin, destination):
    url = f'http://router.project-osrm.org/route/v1/driving/{origin[1]},{origin[0]};{destination[1]},{destination[0]}?overview=false'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if 'routes' in data and len(data['routes']) > 0:
            route = data['routes'][0]
            distance = route['distance'] / 1000  # Distance in kilometers
            duration = route['duration'] / 3600  # Duration in hours
            return distance, duration
        else:
            return None, None
    else:
        print(f"Error: {response.status_code}")
        return None, None

# Initialize variables for averaging and cardio problem detection count
readings_count = 0
total_hb = 0
total_spo2 = 0
start_time = time.time()
cardio_problem_count = 0
hr_spo2_displaying = False  # Flag to indicate whether HR and SpO2 are being displayed

# Function to continuously monitor cardio data
def cardio_monitor():
    global readings_count, total_hb, total_spo2, start_time, cardio_problem_count, hr_spo2_displaying
    while True:
        mx30.read_sensor()
        hb = int(mx30.ir / 100)
        spo2 = int((mx30.red / 100) - 30)
        spo2 = max(0, min(spo2, 99))
        if spo2 < 0:
            spo2 = 0
        if spo2 > 100:
            spo2 = 99
        data = {"heart_rate": hb, "SpO2": spo2}
        db.child(child_id).update(data)

        # Display real-time heart rate and SpO2
        lcd.clear()
        lcd.write_string("HR: {} bpm".format(hb))
        lcd.cursor_pos = (1, 0)
        lcd.write_string("SpO2: {}%".format(spo2))
        hr_spo2_displaying = True  # Set flag to indicate HR and SpO2 are being displayed

        # Accumulate data
        total_hb += hb
        total_spo2 += spo2
        readings_count += 1

        # Check if 5 minutes have passed
        if time.time() - start_time >= 30:  # 300 seconds = 5 minutes
            average_hb = total_hb / readings_count
            average_spo2 = total_spo2 / readings_count

            # Reset for next average calculation
            total_hb = 0
            total_spo2 = 0
            readings_count = 0
            start_time = time.time()

            # Prepare input for the model
            child_data = get_data(child_id)
            if isinstance(child_data, dict):
                input_data = {
                    'gender': child_data.get("Gender"),
                    'Age': child_data.get("Age"),
                    'height': child_data.get("Height"),
                    'weight': child_data.get("Weight"),
                    'heart_rate': average_hb,
                    'SpO2': average_spo2,
                    'cholesterol': child_data.get("Cholesterol"),
                    'Diabetic': child_data.get("Diabetic"),
                    'smoke': child_data.get("Smoke"),
                    'alco': child_data.get("Alcohol"),
                    'KidneyDisease': child_data.get("KidneyDisease"),
                    'Asthma': child_data.get("Asthma")
                }
                print(input_data)
            else:
                print(child_data)
            condition = predict_cardio_case(input_data)

            if condition == 1:
                cardio_problem_count += 1
                if cardio_problem_count >= 10:
                    # Update the database to indicate a cardio problem
                    db.child(child_id).update({"cardio": 1})
                    print("Cardio problem detected 10 times. Updated database.")
                    cardio_problem_count = 0  # Reset the count after updating the database
                lcd.cursor_pos = (2, 0)
                lcd.write_string("!!!Check Cardio!!!")
                print("ATTENTION: Cardiovascular Issue Detected")
            else:
                # Reset the count if a non-problem case is detected
                cardio_problem_count = 0
                # Update the database to indicate no cardio problem
                db.child(child_id).update({"cardio": 0})

        time.sleep(1.6)

# Start the cardio monitoring thread
cardio_thread = threading.Thread(target=cardio_monitor)
cardio_thread.start()

# Function to continuously send GPS data to Firebase and update the current location
def send_gps_data():
    while True:
        port = "/dev/ttyAMA0"
        ser = serial.Serial(port, baudrate=9600, timeout=0.5)
        dataout = pynmea2.NMEAStreamReader()
        newdata = ser.readline()
        n_data = newdata.decode('latin-1')
        if n_data[0:6] == '$GPRMC':
            newmsg = pynmea2.parse(n_data)
            global current_lat, current_lng
            current_lat = newmsg.latitude
            current_lng = newmsg.longitude
            gps = "Latitude=" + str(current_lat) + " and Longitude=" + str(current_lng)
            print(gps)
            data = {"LAT": current_lat, "LNG": current_lng}
            db.child(child_id).update(data)
            print("Data sent")
            time.sleep(10)  

# Start the GPS data sending thread
gps_thread = threading.Thread(target=send_gps_data)
gps_thread.start()

# Continuously record voice and process it
while True:
    if input() == 'k':
        record_audio("recorded_audio.wav", duration=4, samplerate=44100)
        try:
            audio_text = audio_to_text("recorded_audio.wav")
            if audio_text:
                print("Recognized text:", audio_text)
                lat, lng = check_text_in_firebase(audio_text)
                if lat is not None and lng is not None:
                    print(f"Next Location coordinates: Latitude={lat}, Longitude={lng}")
                    # Get current location coordinates from GPS
                    current_location = (current_lat, current_lng)
                    # Calculate route from current location to next location
                    distance, duration = get_route(current_location, (lat, lng))
                    if distance is not None and duration is not None:
                        print(f"Distance to Next Location: {distance:.2f} km")
                        print(f"Estimated Duration: {duration:.2f} hours")
                        # Display route information on LCD
                        lcd.clear()
                        lcd.write_string("Next Location:")
                        lcd.cursor_pos = (1, 0)
                        lcd.write_string("Distance: {:.2f} km".format(distance))
                        lcd.cursor_pos = (2, 0)
                        lcd.write_string("Duration: {:.2f} hrs".format(duration))
                        last_display_time = time.time()  # Update the last display time
                    else:
                        print("Error calculating route.")
                else:
                    print("No match found in the Firebase database.")
        except Exception as e:
            print("An error occurred:", e)
    
    # Check if it's time to clear the display
    if not hr_spo2_displaying and time.time() - last_display_time >= display_duration:
        lcd.clear()
