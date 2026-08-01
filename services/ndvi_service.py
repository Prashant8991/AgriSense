import ee
import datetime

# Attempt to initialize Earth Engine
try:
    ee.Initialize()
except Exception as e:
    # If not initialized, try to authenticate or just handle the error
    # In a real server, credentials should be handled via Service Account
    print(f"Earth Engine Initialization Error: {e}")

def get_ndvi_data(lat, lon):
    """
    Calculate NDVI for a specific location using Sentinel-2 satellite imagery.
    """
    try:
        # 1. Define point and buffer (approx 500m)
        point = ee.Geometry.Point([lon, lat])
        roi = point.buffer(250) # 250m radius = 500m diameter

        # 2. Load Sentinel-2 Surface Reflectance collection
        # Filtering for low cloud cover and recent images
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=60) # Look back 2 months for cloud-free
        
        collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                      .filterBounds(roi)
                      .filterDate(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
                      .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
                      .sort('system:time_start', False)) # Most recent first

        image = collection.first()
        
        if not image:
            return {"error": "No recent satellite imagery found for this location."}

        # 3. Calculate NDVI: (B8 - B4) / (B8 + B4)
        # B8 is NIR, B4 is Red
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')

        # 4. Reduce to region (get mean NDVI value)
        stats = ndvi.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=roi,
            scale=10,
            maxPixels=1e9
        ).getInfo()

        ndvi_value = stats.get('NDVI')
        
        if ndvi_value is None:
            return {"error": "Could not calculate NDVI for this region."}

        # 5. Classification
        interpretation = "Unknown"
        if ndvi_value < 0.2:
            interpretation = "Very Poor Vegetation"
        elif 0.2 <= ndvi_value < 0.4:
            interpretation = "Weak Crop Growth"
        elif 0.4 <= ndvi_value < 0.6:
            interpretation = "Moderate Vegetation"
        elif 0.6 <= ndvi_value < 0.8:
            interpretation = "Healthy Crops"
        elif ndvi_value >= 0.8:
            interpretation = "Excellent Crop Health"

        return {
            "ndvi_value": round(ndvi_value, 3),
            "crop_health": interpretation,
            "date": image.get('system:index').getInfo()[:8] # YYYYMMDD
        }

    except Exception as e:
        print(f"NDVI Service Error: {e}")
        return {"error": str(e)}
