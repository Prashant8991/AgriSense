# 🌾 AgriSense Pro — AI Crop Disease Detection & Smart Agriculture Platform

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Framework-Flask-black.svg?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![CNN Model](https://img.shields.io/badge/ML-CNN_Classification-emerald.svg)](https://keras.io/)
[![Groq API](https://img.shields.io/badge/AI-Groq_LLM_API-purple.svg)](https://groq.com/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**AgriSense Pro** is an AI-powered smart agriculture platform designed for real-time crop disease detection, field health analytics, and AI-assisted agronomy recommendations. Combining Deep Learning (**Convolutional Neural Networks**) for leaf image analysis with high-speed **Groq LLM API** inference, AgriSense Pro helps farmers diagnose plant diseases with 90%+ accuracy and receive immediate, actionable treatment protocols.

---

## ✨ Key Features

- 🔬 **CNN Leaf Disease Classifier**: Deep CNN model trained on agricultural datasets achieving **90%+ classification accuracy** across 10+ disease categories (Early Blight, Late Blight, Yellow Leaf Curl, Bacterial Spot, Rust, Healthy leaves, etc.).
- 🤖 **Groq AI Agron-Consultant**: Integrated Groq LLM API delivering real-time, context-aware treatment protocols, organic remedies, and fungicide dosage guidelines tailored to the diagnosed disease.
- 📡 **NDVI Vegetation Monitoring**: Satellite remote sensing analytics calculating Normalized Difference Vegetation Index (NDVI) values to assess plot health & moisture stress.
- 📊 **Farmer Analytics Dashboard**: PostgreSQL-persisted disease log tracking 1,000+ historical diagnostic records, interactive heatmaps, and trend analytics.
- ⛅ **Microclimate Weather Alerts**: Real-time localized weather data integration calculating fungal & bacterial disease outbreak risk scores based on humidity and ambient temperature.

---

## 🛠️ Tech Stack & Architecture

- **Backend**: Python 3.10, Flask REST Framework
- **Machine Learning**: TensorFlow / Keras (CNN Classification), OpenCV (Image Preprocessing & Grad-CAM Heatmaps)
- **Generative AI**: Groq LLM API (`llama3-70b`) for agronomy insights
- **Database**: PostgreSQL (Production) / SQLite (Development Fallback)
- **Frontend**: Responsive HTML5, Tailwind CSS, JavaScript (Vanilla ES6+), Chart.js
- **Deployment**: Gunicorn, Procfile (Heroku / Render ready)

---

## 📁 Repository Structure

```
AgriSensePro/
├── app.py                     # Main Flask application entry point
├── main.py                    # Server configuration & CLI launcher
├── database.py                # PostgreSQL connection pooling & schema migrations
├── auth_dep.py                # User authentication & session dependency handlers
├── classes.json               # Index mapping for 10+ crop disease categories
├── Procfile                   # Web server execution profile
├── requirements.txt           # Python dependency manifest
├── models/
│   └── disease_classifier.py  # CNN inference engine & Grad-CAM visualization pipeline
├── routes/
│   ├── auth.py                # User registration & login endpoints
│   ├── dashboard.py           # Farmer analytics dashboard routes
│   ├── detection.py          # AI disease upload & Groq LLM treatment advice routes
│   ├── farm.py                # Plot management & field tracking
│   ├── history.py             # Diagnostic history & report generation
│   ├── pages.py               # Public landing pages
│   └── report.py              # PDF export & summary routes
├── services/
│   ├── ndvi_service.py        # Satellite NDVI vegetation index processor
│   └── weather_service.py     # Microclimate weather API integration
├── static/
│   ├── css/style.css          # Custom styling & dark themes
│   └── js/app.js              # Client-side UI & image upload logic
└── templates/
    └── index.html             # Main application UI template
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- **Python 3.10+** installed
- **PostgreSQL** database (optional for local SQLite fallback)
- **Groq API Key** (Get free API key at [console.groq.com](https://console.groq.com/))

### 2. Clone & Setup Environment

```bash
git clone https://github.com/Prashant8991/AgriSense.git
cd AgriSense
```

### 3. Create Virtual Environment & Install Dependencies

```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
FLASK_ENV=development
SECRET_KEY=your_secret_key_here
GROQ_API_KEY=your_groq_api_key_here
DATABASE_URL=postgresql://user:password@localhost:5432/agrisense
```

### 5. Run Application

```bash
python app.py
```

Open your browser and navigate to `http://127.0.0.1:5000` to launch the AgriSense Pro portal.

---

## 👤 Author & Maintainer

**Prashant Singh**
- 🎓 Computer Science & Engineering (Cyber Security) @ VIT Chennai
- 💼 Software Engineer & Systems Developer
- 🌐 Portfolio: [prashant8991.github.io/portfolio](https://prashant8991.github.io/portfolio/)
- 🐙 GitHub: [@Prashant8991](https://github.com/Prashant8991)
- 📧 Email: [singhprashant.globe@gmail.com](mailto:singhprashant.globe@gmail.com)

---

## 📜 License

This project is open-source and available under the [MIT License](LICENSE).
