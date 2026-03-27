import os
import json
import logging
import mysql.connector
import io
import time
import base64
from PIL import Image
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
from fpdf import FPDF
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import google.generativeai as genai
from medical_engine import MedicalEngine

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("careai-app")

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

# Configure Gemini AI
if API_KEY:
    genai.configure(api_key=API_KEY)
    logger.info("✅ Google GenAI SDK Configured")
else:
    logger.error("❌ API Key Missing! Check .env file.")

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASS = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "careai_db")

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
CORS(app)

engine = MedicalEngine()

def get_db_connection():
    return mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME)

def init_db():
    try:
        # Connect to MySQL Server (No DB selected yet)
        conn = mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASS)
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        conn.close()
        
        # Connect to the created DB and setup tables
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY, 
            email VARCHAR(255) UNIQUE, 
            password VARCHAR(255), 
            phone VARCHAR(20), 
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Updated History Table Schema (Includes medicine & diet columns)
        cursor.execute('''CREATE TABLE IF NOT EXISTS history (
            id INT AUTO_INCREMENT PRIMARY KEY, 
            user_id INT, 
            disease VARCHAR(255), 
            description TEXT, 
            medicine TEXT, 
            diet TEXT, 
            date DATETIME, 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )''')
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e: 
        logger.error(f"DB Init: {e}")

init_db()

# --- DYNAMIC MODEL SELECTOR ---
def get_available_model():
    """Auto-detects the best available model for your API Key"""
    try:
        print("🔍 Scanning available AI models...")
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Priority List based on your successful logs
        priorities = [
            'models/gemini-2.0-flash',       # Latest stable
            'models/gemini-2.0-flash-exp',   # Fast experimental
            'models/gemini-1.5-flash',       # Standard
            'models/gemini-pro'              # Fallback
        ]
        
        for p in priorities:
            if p in available_models:
                print(f"✅ Found Compatible Model: {p}")
                return p
        
        if available_models:
            print(f"⚠️ Using Fallback Model: {available_models[0]}")
            return available_models[0]
            
    except Exception as e:
        print(f"❌ Model Scan Error: {e}")
    
    return "models/gemini-pro" # Ultimate default

# Cache the model name so we don't scan every time
ACTIVE_MODEL_NAME = get_available_model()

def generate_ai_content(sys_prompt, user_prompt):
    if not API_KEY: 
        print("❌ ERROR: API Key is missing in .env")
        return None

    try:
        print(f"⏳ Sending request to {ACTIVE_MODEL_NAME}...")
        
        model = genai.GenerativeModel(
            model_name=ACTIVE_MODEL_NAME, 
            system_instruction=sys_prompt
        )
        
        safety = {
            "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
            "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
            "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE"
        }
        
        response = model.generate_content(user_prompt, safety_settings=safety)
        
        if response.text:
            print("✅ AI Response Received")
            return response.text
            
    except Exception as e:
        print(f"❌ AI Error: {e}")
        # Fallback for models that don't support system_instruction
        if "system_instruction" in str(e) or "404" in str(e):
            try:
                print("⚠️ Retrying with simple prompt...")
                model = genai.GenerativeModel(ACTIVE_MODEL_NAME)
                combined_prompt = f"SYSTEM: {sys_prompt}\n\nUSER: {user_prompt}"
                response = model.generate_content(combined_prompt)
                return response.text
            except: pass
            
    return None

def save_history(user_id, disease, description, medicine, diet):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = "INSERT INTO history (user_id, disease, description, medicine, diet, date) VALUES (%s, %s, %s, %s, %s, %s)"
        val = (user_id, disease, description, medicine, diet, datetime.now())
        cursor.execute(sql, val)
        conn.commit()
        cursor.close()
        conn.close()
        print(f"✅ History Saved for User {user_id}")
    except Exception as e: 
        print(f"❌ DB Save Error: {e}")

# --- ROUTES ---

@app.route("/")
def index(): return render_template("landing.html")
@app.route("/dashboard")
def dashboard(): return render_template("home.html", active_page='home')
@app.route("/ai-chat")
def chat_page(): return render_template("chat.html", active_page='chat')
@app.route("/locate")
def locate_page(): return render_template("maps.html", active_page='maps')
@app.route("/records")
def records_page(): return render_template("history.html", active_page='history')

@app.route('/auth/login', methods=['POST'])
def login():
    d = request.json
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, password FROM users WHERE email = %s", (d['email'],))
        u = cursor.fetchone()
        cursor.close()
        conn.close()
        if u and check_password_hash(u['password'], d['password']): 
            return jsonify({"message": "OK", "user_id": u['id']}), 200
    except: pass
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/auth/register', methods=['POST'])
def register():
    d = request.json
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (email, password, phone) VALUES (%s, %s, %s)", (d['email'], generate_password_hash(d['password']), d.get('phone')))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": "Registered"}), 201
    except: return jsonify({"error": "Email exists"}), 409

@app.route("/recommend", methods=["POST"])
def recommend():
    d = request.json
    symptoms = d.get("symptoms", [])
    vitals = d.get("vitals", {})
    history = d.get("history", [])
    age = d.get("age", 30)
    gender = d.get("gender", "Not Specified")
    lang_name = d.get("language", "English")
    
    # 1. EMERGENCY CHECK (Local Engine)
    is_emergency, keyword, severity = engine.detect_emergency(symptoms)
    if is_emergency:
        return jsonify({
            "disease": f"⚠️ EMERGENCY: {keyword.upper()} DETECTED",
            "description": f"Please call emergency services immediately. {keyword} can be life-threatening.",
            "medicine": "Do not take medication without doctor approval.",
            "diet": "N/A", 
            "workouts": "Rest immediately.", 
            "precautions": "Go to the nearest hospital.",
            "side_effects": "Critical condition.",
            "is_emergency": True
        })

    # 2. LOCAL ANALYSIS (Vitals & Herbs)
    vital_warnings = engine.analyze_vitals(vitals)
    herbal_remedies = engine.get_herbal_remedy(symptoms)
    
    vital_text = " ".join(vital_warnings) if vital_warnings else "Normal"
    herbal_text = " | ".join(herbal_remedies) if herbal_remedies else "None"
    history_text = ", ".join(history) if history else "None"

    final = {
        "disease": "Analysis Incomplete", 
        "description": "AI connection failed. Please check internet.", 
        "medicine": "Consult Doctor", 
        "diet": "Healthy Diet", 
        "workouts": "Rest", 
        "precautions": "See a doctor", 
        "is_emergency": False
    }

    # 3. GEMINI API CALL
    if API_KEY:
        sys_prompt = f"You are a medical AI. User speaks {lang_name}. Output strict JSON."
        
        user_prompt = f"""
                Patient: {age}yrs, {gender}. History: {history_text}.
                Symptoms: {symptoms}. Vitals: {vital_text}.
                
                Act as a doctor. Return a JSON object.
                
                CRITICAL FORMATTING RULES:
                1. Use bullet points (•) for lists.
                2. **BOLD** ONLY the specific name of the medicine or ingredient to buy. 
                - GOOD: "Take **Paracetamol** 500mg"
                - BAD: "Take **Paracetamol 500mg**" (Do not bold dosage)
                3. For Diet, **BOLD** the specific food items to buy (e.g., "**Spinach**", "**Almonds**").
                
                JSON KEYS:
                {{
                    "disease": "Condition Name",
                    "description": "Brief explanation.",
                    "medicine": "• **Medicine Name**: Dosage\\n• **Supplement Name**: Dosage",
                    "precautions": "• Precaution 1\\n• Precaution 2",
                    "workouts": "• Exercise 1\\n• Exercise 2",
                    "diet": "• Eat: **Food Item**, **Food Item**\\n• Avoid: Food Item"
                }}
                """
        
        ai_text = generate_ai_content(sys_prompt, user_prompt)
        
        if ai_text:
            try:
                clean_text = ai_text.replace("```json", "").replace("```", "").strip()
                ai_data = json.loads(clean_text)
                final.update(ai_data)
            except Exception as e:
                print(f"JSON Parse Error: {e}")

    # Append Local Context
    if vital_warnings: final['description'] += f"\n\n⚠️ VITALS ALERT: {vital_text}"
    if herbal_remedies: final['medicine'] += f"\n\n🌿 HERBAL OPTIONS: {herbal_text}"
    if history: final['description'] += f"\n\nℹ️ NOTE: Advice adjusted for history: {history_text}"

    # Save to DB
    if d.get("user_id"):
        meds_to_save = final.get("medicine", "")
        save_history(
            d.get("user_id"), 
            final["disease"], 
            final["description"], 
            meds_to_save,
            final.get("diet", "")
        )
    
    return jsonify(final)
@app.route("/chat", methods=["POST"])
def chat():
    d = request.json
    query = d.get("query")
    image_data = d.get("image")
    lang = d.get("language", "English")
    history = d.get("history", []) # Conversation History

    # 1. Format History for AI Context
    history_text = "No previous context."
    if history:
        history_text = ""
        for h in history:
            # Clean up HTML tags from history if present
            prev_ai = h.get('ai', '').replace('<b>', '').replace('</b>', '')
            history_text += f"User asked: {h.get('user')}\nAI answered: {prev_ai}\n"

    # 2. VISION MODE (Image Analysis)
    if image_data:
        sys_prompt = f"""
        You are an expert AI Doctor. Language: {lang}.
        TASK: Analyze the medical image.
        
        CRITICAL FORMATTING INSTRUCTION:
        Return valid JSON where the values for "medical" and "herbal" are single MARKDOWN STRINGS, NOT nested objects.
        
        JSON STRUCTURE:
        {{
            "medical": "• **Observation**: [Describe image]\\n• **Diagnosis**: [Likely condition]\\n• **Advice**: [Recommendation]",
            "herbal": "• **Ayurvedic Remedy**: [Home remedy]\\n• **Diet**: [What to eat]"
        }}
        """
        try:
            image_bytes = base64.b64decode(image_data.split(',')[1])
            image = Image.open(io.BytesIO(image_bytes))
            
            # USE THE DYNAMIC MODEL (Safe)
            print(f"⏳ Processing Image with {ACTIVE_MODEL_NAME}...")
            model = genai.GenerativeModel(ACTIVE_MODEL_NAME)
            
            response = model.generate_content([sys_prompt, "User Query: " + (query or "Analyze this"), image])
            
            if response.text:
                print(f"📸 Raw Vision Output: {response.text[:100]}...") # Debug Print
                
                # Clean Markdown (```json ... ```)
                clean_text = response.text.replace("```json", "").replace("```", "").strip()
                
                # Ensure it's valid JSON
                if "{" in clean_text:
                    clean_text = clean_text[clean_text.find("{"):clean_text.rfind("}")+1]
                
                # PARSING CHECK: Ensure values are strings
                data = json.loads(clean_text)
                
                # Fallback: If AI still returns an object/list, convert it to string to prevent crash
                if isinstance(data.get('medical'), (dict, list)):
                    data['medical'] = str(data['medical'])
                if isinstance(data.get('herbal'), (dict, list)):
                    data['herbal'] = str(data['herbal'])

                return jsonify(data)
                
        except Exception as e:
            print(f"Vision Error: {e}")
            return jsonify({
                "medical": f"Error: {str(e)}. Please try a different image.", 
                "herbal": "N/A"
            })

    # 3. TEXT CHAT MODE (Conversational)
    else:
        # SYSTEM INSTRUCTION
        sys_instruction = f"You are a helpful AI Doctor. Language: {lang}. Response must be valid JSON."

        # USER PROMPT WITH CONTEXT
        user_prompt = f"""
        [HISTORY OF CONVERSATION]
        {history_text}
        
        [CURRENT USER QUESTION]
        "{query}"
        
        [INSTRUCTIONS]
        1. If the user asks a follow-up question (e.g., "Which tablet?", "How much?"), USE THE HISTORY to find the context.
           - Example: If history mentions "Headache", and user asks "Which tablet?", suggest "Ibuprofen" or "Paracetamol".
        2. Return valid JSON with two keys: "medical" and "herbal".
        3. Use bullet points (•).
        
        [JSON FORMAT]
        {{
            "medical": "• Specific medicine name\\n• Dosage instruction",
            "herbal": "• Specific herbal remedy"
        }}
        """
        
        ai_text = generate_ai_content(sys_instruction, user_prompt)
        
        response = {"medical": "I couldn't process that.", "herbal": "No advice available."}
        
        if ai_text:
            try:
                # Cleanup Markdown
                clean_text = ai_text.replace("```json", "").replace("```", "").strip()
                # Cleanup Text before/after JSON
                if "{" in clean_text:
                    clean_text = clean_text[clean_text.find("{"):clean_text.rfind("}")+1]
                
                response = json.loads(clean_text)
            except Exception as e:
                print(f"JSON Error: {e}")
                response["medical"] = ai_text.replace('"', "'") # Fallback to raw text

        return jsonify(response)
    
@app.route("/history", methods=["GET"])
def get_history():
    uid = request.args.get('user_id')
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT disease, description, medicine, diet, DATE_FORMAT(date, '%d %b %Y, %h:%i %p') as formatted_date FROM history WHERE user_id = %s ORDER BY id DESC", (uid,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(rows)
    except: return jsonify([])

@app.route("/doctors", methods=["POST"])
def doctors():
    spec = request.json.get('specialty')
    lat, lon = request.json.get('lat'), request.json.get('lon')
    loc = request.json.get('location')
    results = []
    
    if lat and lon:
        url = "http://overpass-api.de/api/interpreter"
        q = f"""[out:json];(node["amenity"~"hospital|clinic|doctors|pharmacy"](around:10000,{lat},{lon}););out center;"""
        try:
            r = requests.get(url, params={'data': q}, timeout=15)
            if r.status_code == 200:
                for el in r.json().get('elements', [])[:15]:
                    results.append({
                        "name": el.get('tags', {}).get('name', 'Clinic'), 
                        "address": "Nearby", 
                        "rating": "📍 Verified", 
                        "lat": el.get('lat'), 
                        "lon": el.get('lon')
                    })
        except: pass
    
    if not results:
        sys_prompt = "You are a location finder. Return valid JSON array."
        user_prompt = f"Find 5 real {spec} near {loc}. JSON Format: [{{'name': 'X', 'address': 'Y', 'rating': '4.5'}}]"
        ai_text = generate_ai_content(sys_prompt, user_prompt)
        if ai_text:
            try:
                results = json.loads(ai_text.replace("```json", "").replace("```", "").strip())
            except: pass
            
    return jsonify({"result": results})

# --- PDF GENERATION ---
class MedicalReportPDF(FPDF):
    def header(self):
        self.set_fill_color(37, 99, 235) # Blue Header
        self.rect(0, 0, 210, 40, 'F')
        self.set_y(15)
        self.set_font('Arial', 'B', 20)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, 'Care AI Health Report', 0, 1, 'C')
        self.ln(20)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, 'Disclaimer: AI-generated advice. Consult a doctor.', 0, 0, 'C')

@app.route('/download_report', methods=['POST'])
def download_report():
    d = request.json
    try:
        pdf = MedicalReportPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        def clean(t): 
            if not t: return "N/A"
            t = t.replace('**', '').replace('*', '').replace('•', '\n- ')
            return str(t).encode('latin-1', 'ignore').decode('latin-1')

        # 1. Disease Header
        pdf.set_font("Arial", "B", 16)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 10, f"Diagnosis: {clean(d.get('disease'))}", 0, 1)
        pdf.ln(5)
        
        # 2. Sections (6-Point Grid Structure)
        sections = [
            ("Overview / Description", d.get('description')),
            ("Medications & Remedies", d.get('medicine')),
            ("Dietary Plan", d.get('diet')),
            ("Recommended Activity / Workout", d.get('workouts')),
            ("Precautions & Safety", d.get('precautions'))
        ]
        
        for title, text in sections:
            # Blue Section Title
            pdf.set_font("Arial", "B", 12)
            pdf.set_text_color(37, 99, 235)
            pdf.cell(0, 8, title, 0, 1)
            
            # Gray Body Text
            pdf.set_font("Arial", "", 11)
            pdf.set_text_color(50, 50, 50)
            pdf.multi_cell(0, 6, clean(text))
            pdf.ln(4)
            
        return send_file(
            io.BytesIO(pdf.output(dest='S').encode('latin-1')), 
            mimetype='application/pdf', 
            as_attachment=True, 
            download_name=f"CareAI_Report_{datetime.now().strftime('%Y%m%d')}.pdf"
        )
    except Exception as e: 
        return jsonify({"error": str(e)}), 500
    
@app.route("/clear_history", methods=["POST"])
def clear_history():
    d = request.json
    uid = d.get('user_id')
    if not uid: return jsonify({"error": "User ID missing"}), 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Delete all records for this specific user
        cursor.execute("DELETE FROM history WHERE user_id = %s", (uid,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": "History cleared"})
    except Exception as e:
        logger.error(f"Clear History Error: {e}")
        return jsonify({"error": "Database error"}), 500
    
# --- APPOINTMENT BOOKING ---
@app.route("/book_appointment", methods=["POST"])
def book_appointment():
    d = request.json
    uid = d.get('user_id')
    doc_name = d.get('doctor_name')
    date_str = d.get('date') # Format: YYYY-MM-DDTHH:MM
    
    if not uid or not doc_name or not date_str:
        return jsonify({"error": "Missing details"}), 400

    try:
        # 1. Save to Database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO appointments (user_id, doctor_name, appointment_date, reason) VALUES (%s, %s, %s, %s)", 
                       (uid, doc_name, date_str, "General Checkup"))
        conn.commit()
        cursor.close()
        conn.close()

        # 2. Email Logic (Simulated for safety)
        # To send real emails, you would use 'smtplib' here with your Gmail App Password.
        print(f"📧 EMAIL SENT: Appointment confirmed with {doc_name} on {date_str} for User {uid}")
        
        return jsonify({"message": "Booking Confirmed", "status": "success"})

    except Exception as e:
        logger.error(f"Booking Error: {e}")
        return jsonify({"error": "Booking failed"}), 500

# --- GET APPOINTMENTS (For History Page - Optional Bonus) ---
@app.route("/appointments", methods=["GET"])
def get_appointments():
    uid = request.args.get('user_id')
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT doctor_name, DATE_FORMAT(appointment_date, '%d %b %Y, %h:%i %p') as fmt_date, status FROM appointments WHERE user_id = %s ORDER BY appointment_date DESC", (uid,))
        rows = cursor.fetchall()
        conn.close()
        return jsonify(rows)
    except: return jsonify([])    
    
@app.route("/vision")
def vision_page():
    return render_template("vision.html", active_page='vision')


# --- DIET PLANNER PAGE ---
@app.route("/diet")
def diet_page():
    return render_template("diet.html", active_page='diet')

# --- DIET GENERATOR API ---
@app.route("/generate_diet", methods=["POST"])
def generate_diet():
    d = request.json
    cuisine = d.get("cuisine", "Indian")
    type_diet = d.get("type", "Vegetarian")
    goal = d.get("goal", "Healthy Living")
    age = d.get("age", 30)
    
    sys_prompt = "You are an expert Nutritionist. Return purely valid JSON."
    
    user_prompt = f"""
    Create a 7-Day Meal Plan.
    User Profile: {age} years old.
    Cuisine: {cuisine}.
    Diet Type: {type_diet}.
    Health Goal/Condition: {goal}.
    
    OUTPUT FORMAT:
    Return a raw JSON array of 7 objects (one for each day). No markdown.
    
    [
        {{
            "day": "Day 1",
            "breakfast": "Food item",
            "lunch": "Food item",
            "snack": "Food item",
            "dinner": "Food item",
            "calories": "Approx Total Calories"
        }},
        ... (repeat for 7 days)
    ]
    """
    
    ai_text = generate_ai_content(sys_prompt, user_prompt)
    
    if ai_text:
        try:
            clean_text = ai_text.replace("```json", "").replace("```", "").strip()
            # Ensure we only parse the array part
            if "[" in clean_text:
                clean_text = clean_text[clean_text.find("["):clean_text.rfind("]")+1]
            return jsonify({"plan": json.loads(clean_text)})
        except Exception as e:
            print(f"Diet JSON Error: {e}")
            return jsonify({"error": "Failed to parse diet plan"}), 500
            
    return jsonify({"error": "AI Failed"}), 500

# --- SAFETY CHECKER PAGE ---
@app.route("/safety")
def safety_page():
    return render_template("safety.html", active_page='safety')

# --- INTERACTION API (FIXED ROUTE NAME) ---
@app.route("/check_safety", methods=["POST"])  # <--- This was likely "/check_interaction" before
def check_safety():
    d = request.json
    drug1 = d.get("drug1")
    drug2 = d.get("drug2")
    
    if not drug1 or not drug2: return jsonify({"error": "Missing drugs"}), 400

    sys_prompt = "You are a Pharmacist. Return strict JSON."
    
    user_prompt = f"""
    Analyze the interaction between these two medicines: "{drug1}" and "{drug2}".
    
    RETURN JSON FORMAT:
    {{
        "status": "Safe" OR "Caution" OR "Danger",
        "color": "green" OR "yellow" OR "red",
        "interaction": "Brief explanation of biological interaction.",
        "recommendation": "Advice (e.g., 'Take 2 hours apart' or 'Do not mix')."
    }}
    """
    
    ai_text = generate_ai_content(sys_prompt, user_prompt)
    
    if ai_text:
        try:
            clean = ai_text.replace("```json", "").replace("```", "").strip()
            if "{" in clean: clean = clean[clean.find("{"):clean.rfind("}")+1]
            return jsonify(json.loads(clean))
        except Exception as e:
            print(f"Safety JSON Error: {e}")
            
    return jsonify({"error": "Analysis failed"}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)