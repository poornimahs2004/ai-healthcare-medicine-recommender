# medical_engine.py
class MedicalEngine:
    def __init__(self):
        self.emergency_keywords = {
            'critical': ['chest pain', 'heart attack', 'cardiac', 'stroke', 'paralysis', 'unconscious', 'seizure', 'severe bleeding', 'vomiting blood'],
            'urgent': ['difficulty breathing', 'shortness of breath', 'severe headache', 'suicide', 'kill myself']
        }
        
        self.herbal_db = {
            'fever': 'Ginger tea with Tulsi (Holy Basil) and honey.',
            'cold': 'Warm turmeric milk (Golden Milk) before bed.',
            'cough': 'Mixture of honey and black pepper powder.',
            'headache': 'Apply peppermint oil to temples or drink ginger tea.',
            'stomach': 'Chew Ajwain (Carom seeds) with warm water.',
            'acidity': 'Chew fennel seeds (Saunf) after meals.',
            'stress': 'Ashwagandha powder in warm milk.',
            'insomnia': 'Chamomile tea or warm milk with nutmeg.'
        }

    def detect_emergency(self, symptoms_list):
        # Convert list to string for searching
        text = " ".join(symptoms_list).lower() if isinstance(symptoms_list, list) else str(symptoms_list).lower()
        
        for severity, keywords in self.emergency_keywords.items():
            for k in keywords:
                if k in text:
                    return True, k, severity
        return False, None, None

    def analyze_vitals(self, vitals):
        warnings = []
        try:
            temp = float(vitals.get('temperature', 0))
            bp_sys = int(vitals.get('systolic_bp', 0))
            hr = int(vitals.get('heart_rate', 0))
            spo2 = int(vitals.get('spo2', 0))

            # Temperature Logic (Assume Celsius if < 50, else F)
            if temp > 0:
                if temp < 50: temp = (temp * 9/5) + 32 
                if temp > 102: warnings.append("High Fever (>102°F).")
                elif temp > 100.4: warnings.append("Mild Fever.")

            # BP Logic
            if bp_sys > 0:
                if bp_sys > 160: warnings.append("Hypertensive Crisis (BP > 160).")
                elif bp_sys > 140: warnings.append("High Blood Pressure.")
                elif bp_sys < 90: warnings.append("Low Blood Pressure.")

            # Heart Rate
            if hr > 0:
                if hr > 120: warnings.append("Tachycardia (High Heart Rate).")
                elif hr < 50: warnings.append("Bradycardia (Low Heart Rate).")

            # Oxygen
            if spo2 > 0 and spo2 < 92: warnings.append("Low Oxygen Levels (<92%).")

        except:
            pass 
        return warnings

    def get_herbal_remedy(self, symptoms_list):
        found_remedies = []
        text = " ".join(symptoms_list).lower() if isinstance(symptoms_list, list) else str(symptoms_list).lower()
        
        for key, remedy in self.herbal_db.items():
            if key in text:
                found_remedies.append(f"{key.capitalize()}: {remedy}")
        return found_remedies