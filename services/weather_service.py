import os
import requests
from dotenv import load_dotenv

load_dotenv()

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

def get_weather_data(lat, lon):
    """
    Fetch real-time weather from OpenWeatherMap using latitude and longitude.
    """
    if not OPENWEATHER_API_KEY:
        raise ValueError("OPENWEATHER_API_KEY not found in environment.")

    # Using One Call API 3.0 or Current Weather Data?
    # For now, Current Weather Data API is simpler and widely available
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Rainfall handling (it might not be in the response if it's not raining)
        rainfall = 0
        if "rain" in data:
            rainfall = data["rain"].get("1h", 0)
        
        # Structure the returned data
        weather_info = {
            "temperature": data["main"]["temp"],
            "humidity": data["main"]["humidity"],
            "rainfall": rainfall,
            "wind_speed": data["wind"]["speed"],
            "weather_condition": data["weather"][0]["main"],
            "description": data["weather"][0]["description"],
            "location_name": data.get("name", "Unknown Location")
        }
        return weather_info
    except Exception as e:
        print(f"Weather API Error: {e}")
        return None

def predict_disease_risk(temp, humidity, rainfall):
    """
    Rule-based disease risk estimator for plant diseases.
    """
    risk = "LOW"
    disease = "General Maintenance"
    
    # 1. Late Blight Risk (Humidity > 80%, Temp 15-30°C, Rainfall > 0)
    if humidity > 80 and 15 <= temp <= 30 and rainfall > 0:
        risk = "HIGH"
        disease = "Late Blight"
    
    # 2. Powdery Mildew Risk (Humidity 60-80%, Temp 20-28°C, Low rainfall)
    elif 60 <= humidity <= 80 and 20 <= temp <= 28 and rainfall < 2:
        risk = "MEDIUM"
        disease = "Powdery Mildew"
    
    # 3. Leaf Spot Risk (Humidity > 75%, Temp > 24°C)
    elif humidity > 75 and temp > 24:
        # If humidity is super high, push to MEDIUM/HIGH
        risk = "HIGH" if humidity > 85 else "MEDIUM"
        disease = "Leaf Spot"
        
    return {
        "disease_risk": risk,
        "possible_disease": disease
    }
