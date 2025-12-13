# backend/patient_cases.py

import random
from typing import Dict, Any, List, Optional

# Each entry here is one "level" in the game.
# Fields:
# - specialty: one of "neurology", "cardiology", "respiratory", "gastroenterology", "endocrinology"
# - level: 1..5 within that specialty
# - difficulty: "easy" (1–2), "medium" (3), "hard" (4–5)
# - stages: 3 texts, progressively revealing symptoms
# - hints: short hints shown when user presses the Hint button
# - expected_diagnosis / expected_treatment_keywords: used for evaluation and feedback only

PATIENT_CASES: List[Dict[str, Any]] = [
    # -------------------- NEUROLOGY (5 levels) --------------------
    {
        "id": "neuro_1_tension_headache",
        "specialty": "neurology",
        "level": 1,
        "difficulty": "easy",
        "name": "Rohan Verma",
        "age": 25,
        "gender": "M",
        "chief_complaint": "Mild headache after long work days",
        "stages": [
            "You mostly get a mild, band-like headache around your forehead and the back of your head, usually after long days at work.",
            "The pain feels like pressure or tightness, not throbbing, and it improves when you rest or relax.",
            "You do not have nausea, vomiting, vision changes, or sensitivity to light or sound. It mostly comes on with stress.",
        ],
        "hints": [
            "Think about common headache types related to stress and muscle tension.",
            "This type of headache is usually mild, bilateral, and feels like a tight band around the head.",
        ],
        "expected_diagnosis": "tension-type headache",
        "expected_treatment_keywords": [
            "paracetamol", "acetaminophen", "ibuprofen", "NSAID",
            "stress management", "relaxation", "lifestyle"
        ],
    },
    {
        "id": "neuro_2_migraine_easy",
        "specialty": "neurology",
        "level": 2,
        "difficulty": "easy",
        "name": "Priya Sharma",
        "age": 30,
        "gender": "F",
        "chief_complaint": "Severe one-sided headaches",
        "stages": [
            "You get a severe, throbbing headache on one side of your head that can last for several hours.",
            "During the headache, you feel nauseous and prefer to sit in a dark, quiet room because light and sound bother you.",
            "Sometimes before the headache starts, you see flashing lights or zigzag lines in your vision for a short time.",
        ],
        "hints": [
            "Think of headaches that are often one-sided and throbbing, with light and sound sensitivity.",
            "Some patients with this condition can have visual 'aura' before the pain starts.",
        ],
        "expected_diagnosis": "migraine",
        "expected_treatment_keywords": [
            "triptan", "sumatriptan", "rizatriptan", "NSAID",
            "ibuprofen", "paracetamol"
        ],
    },
    {
        "id": "neuro_3_migraine_medium",
        "specialty": "neurology",
        "level": 3,
        "difficulty": "medium",
        "name": "Ananya Gupta",
        "age": 27,
        "gender": "F",
        "chief_complaint": "Recurrent severe headaches",
        "stages": [
            "You have been getting severe headaches on and off for months, usually on one side of your head.",
            "The pain gets worse with movement, and you sometimes feel like you might vomit. You prefer a dark, quiet room.",
            "You notice triggers such as certain foods, lack of sleep, or your periods. Your mother also had similar headaches.",
        ],
        "hints": [
            "Consider primary headache disorders with triggers and family history.",
            "Think of conditions where patients avoid light and movement during attacks.",
        ],
        "expected_diagnosis": "migraine",
        "expected_treatment_keywords": [
            "triptan", "sumatriptan", "propranolol", "preventive",
            "NSAID", "ibuprofen", "paracetamol"
        ],
    },
    {
        "id": "neuro_4_focal_seizure",
        "specialty": "neurology",
        "level": 4,
        "difficulty": "hard",
        "name": "Sandeep Kulkarni",
        "age": 35,
        "gender": "M",
        "chief_complaint": "Strange episodes with staring spells",
        "stages": [
            "You sometimes have brief episodes where you suddenly stop what you’re doing and stare blankly for a short time.",
            "During these episodes, one side of your face or hand may twitch, and you don’t respond properly to people around you.",
            "Afterwards, you feel confused or tired for a few minutes and don’t fully remember what happened.",
        ],
        "hints": [
            "Think beyond headaches and consider paroxysmal neurological events.",
            "These episodes are stereotyped, brief, and followed by confusion.",
        ],
        "expected_diagnosis": "focal seizures",
        "expected_treatment_keywords": [
            "antiepileptic", "levetiracetam", "carbamazepine", "sodium valproate"
        ],
    },
    {
        "id": "neuro_5_stroke",
        "specialty": "neurology",
        "level": 5,
        "difficulty": "hard",
        "name": "Meena Reddy",
        "age": 62,
        "gender": "F",
        "chief_complaint": "Sudden weakness on one side",
        "stages": [
            "A few hours ago, you suddenly noticed weakness in your right arm and leg.",
            "Your family also noticed that your speech became slurred and your mouth seems to droop on one side.",
            "You have a history of high blood pressure and diabetes. You were sitting quietly when this started suddenly.",
        ],
        "hints": [
            "Think of emergency neurological conditions with sudden onset.",
            "Remember the FAST mnemonic: Face drooping, Arm weakness, Speech difficulty, Time to act.",
        ],
        "expected_diagnosis": "acute ischemic stroke",
        "expected_treatment_keywords": [
            "stroke protocol", "thrombolysis", "aspirin", "clopidogrel",
            "blood pressure control", "statin"
        ],
    },

    # -------------------- CARDIOLOGY (5 levels) --------------------
    {
        "id": "cardio_1_stable_angina",
        "specialty": "cardiology",
        "level": 1,
        "difficulty": "easy",
        "name": "Vikas Jain",
        "age": 55,
        "gender": "M",
        "chief_complaint": "Chest discomfort on walking",
        "stages": [
            "You feel a heaviness or tightness in the middle of your chest when you walk fast or climb stairs.",
            "The discomfort goes away in a few minutes when you rest. It does not usually happen at rest.",
            "Sometimes the pain travels to your left arm or jaw. You have diabetes and high cholesterol.",
        ],
        "hints": [
            "Think about exertional chest pain that improves with rest.",
            "Consider chronic, predictable chest pain related to coronary artery disease.",
        ],
        "expected_diagnosis": "stable angina",
        "expected_treatment_keywords": [
            "nitroglycerin", "aspirin", "beta blocker", "statin",
            "lifestyle", "risk factor control"
        ],
    },
    {
        "id": "cardio_2_hypertension",
        "specialty": "cardiology",
        "level": 2,
        "difficulty": "easy",
        "name": "Sunita Menon",
        "age": 48,
        "gender": "F",
        "chief_complaint": "Occasional headaches and high BP readings",
        "stages": [
            "You feel occasional headaches and a sense of heaviness, especially in the mornings.",
            "At a recent check-up, your blood pressure was found to be high on more than one occasion.",
            "You have a sedentary lifestyle, eat salty food, and there is a family history of high blood pressure.",
        ],
        "hints": [
            "Think of a very common chronic condition picked up on regular BP checks.",
            "First-line management often includes lifestyle changes and simple oral medicines.",
        ],
        "expected_diagnosis": "primary hypertension",
        "expected_treatment_keywords": [
            "ACE inhibitor", "amlodipine", "ARB", "blood pressure tablet",
            "lifestyle changes", "salt restriction", "exercise"
        ],
    },
    {
        "id": "cardio_3_heart_failure",
        "specialty": "cardiology",
        "level": 3,
        "difficulty": "medium",
        "name": "Ramesh Patel",
        "age": 65,
        "gender": "M",
        "chief_complaint": "Breathlessness on walking",
        "stages": [
            "You feel short of breath when walking even short distances, which is new for you in the last few weeks.",
            "You notice swelling around your ankles by evening and sometimes wake up at night feeling breathless.",
            "You had a heart attack a few years ago and have not been regular with your medications.",
        ],
        "hints": [
            "Think of chronic heart conditions that cause fluid overload and breathlessness.",
            "Look for history of previous heart attack and ankle swelling.",
        ],
        "expected_diagnosis": "chronic heart failure",
        "expected_treatment_keywords": [
            "diuretic", "furosemide", "ACE inhibitor", "beta blocker",
            "spironolactone", "fluid restriction"
        ],
    },
    {
        "id": "cardio_4_unstable_angina",
        "specialty": "cardiology",
        "level": 4,
        "difficulty": "hard",
        "name": "Iqbal Khan",
        "age": 58,
        "gender": "M",
        "chief_complaint": "Chest pain at rest",
        "stages": [
            "You now get chest pain even at rest, not only on walking. It feels like heavy pressure in the center of your chest.",
            "The pain has become more frequent and severe over the last few days.",
            "You feel sweaty and anxious during these episodes. You are a smoker with diabetes and high cholesterol.",
        ],
        "hints": [
            "This is more serious than stable exertional pain—symptoms at rest are concerning.",
            "Think about acute coronary syndromes and the need for urgent evaluation.",
        ],
        "expected_diagnosis": "unstable angina / acute coronary syndrome",
        "expected_treatment_keywords": [
            "aspirin", "clopidogrel", "heparin", "nitroglycerin",
            "emergency", "admission", "ECG", "reperfusion"
        ],
    },
    {
        "id": "cardio_5_acute_mi",
        "specialty": "cardiology",
        "level": 5,
        "difficulty": "hard",
        "name": "Rita D'Souza",
        "age": 60,
        "gender": "F",
        "chief_complaint": "Severe chest pain with sweating",
        "stages": [
            "You suddenly developed severe, crushing pain in the center of your chest about an hour ago.",
            "The pain is constant, does not improve with rest, and radiates to your left arm and jaw.",
            "You are sweating a lot, feel very anxious, and slightly breathless. This has never happened before.",
        ],
        "hints": [
            "Think of a life-threatening emergency related to the heart.",
            "Immediate hospital-based treatment to open a blocked artery is crucial in this scenario.",
        ],
        "expected_diagnosis": "acute myocardial infarction",
        "expected_treatment_keywords": [
            "aspirin", "clopidogrel", "thrombolysis", "PCI",
            "oxygen", "morphine", "nitrate"
        ],
    },

    # -------------------- RESPIRATORY (5 levels) --------------------
    {
        "id": "resp_1_upper_respiratory_infection",
        "specialty": "respiratory",
        "level": 1,
        "difficulty": "easy",
        "name": "Karan Singh",
        "age": 22,
        "gender": "M",
        "chief_complaint": "Sore throat and runny nose",
        "stages": [
            "You have had a sore throat and runny nose for the last few days.",
            "You have a mild cough with clear mucus, and a low-grade fever.",
            "You feel generally tired but can carry on your daily work. No shortness of breath or chest pain.",
        ],
        "hints": [
            "Think of very common self-limiting infections involving nose and throat.",
            "Usually managed with rest, fluids, and simple medicines rather than strong antibiotics.",
        ],
        "expected_diagnosis": "upper respiratory tract infection",
        "expected_treatment_keywords": [
            "symptomatic", "paracetamol", "rest", "fluids", "steam inhalation"
        ],
    },
    {
        "id": "resp_2_acute_bronchitis",
        "specialty": "respiratory",
        "level": 2,
        "difficulty": "easy",
        "name": "Mehul Shah",
        "age": 35,
        "gender": "M",
        "chief_complaint": "Cough after a viral illness",
        "stages": [
            "You developed a cough after having a cold a week ago.",
            "You now have a persistent cough with some yellowish sputum, but no major breathing difficulty.",
            "You feel chest discomfort when you cough, but your oxygen levels and general activity are okay.",
        ],
        "hints": [
            "Think of a chest infection that often follows a cold but is usually mild.",
            "Treatment is often supportive; antibiotics are not always necessary.",
        ],
        "expected_diagnosis": "acute bronchitis",
        "expected_treatment_keywords": [
            "symptomatic", "cough syrup", "inhaler", "rest",
            "sometimes antibiotic"
        ],
    },
    {
        "id": "resp_3_asthma",
        "specialty": "respiratory",
        "level": 3,
        "difficulty": "medium",
        "name": "Shruti Nair",
        "age": 19,
        "gender": "F",
        "chief_complaint": "Wheezing and breathlessness",
        "stages": [
            "You get episodes of wheezing and shortness of breath, especially at night or with exercise.",
            "Sometimes you feel tightness in your chest and need to sit up to breathe easier.",
            "You have a history of allergies, and these episodes improve after using an inhaler given earlier.",
        ],
        "hints": [
            "Think of chronic airway diseases with episodic wheezing and triggers.",
            "Often treated with inhalers that open the airways and reduce inflammation.",
        ],
        "expected_diagnosis": "bronchial asthma",
        "expected_treatment_keywords": [
            "inhaler", "salbutamol", "bronchodilator", "steroid inhaler",
            "controller", "reliever"
        ],
    },
    {
        "id": "resp_4_copd_exacerbation",
        "specialty": "respiratory",
        "level": 4,
        "difficulty": "hard",
        "name": "Naresh Yadav",
        "age": 68,
        "gender": "M",
        "chief_complaint": "Worsening breathlessness",
        "stages": [
            "You have been a smoker for many years and have had long-standing breathlessness on exertion.",
            "In the last few days, your cough and breathlessness have suddenly worsened.",
            "You now produce more sputum, sometimes yellow or green, and feel breathless even at rest.",
        ],
        "hints": [
            "Think of chronic lung disease in smokers with sudden worsening symptoms.",
            "Treatment often involves bronchodilators, steroids, and sometimes antibiotics and oxygen.",
        ],
        "expected_diagnosis": "COPD exacerbation",
        "expected_treatment_keywords": [
            "bronchodilator", "nebulizer", "inhaler", "steroid",
            "antibiotic", "oxygen"
        ],
    },
    {
        "id": "resp_5_pneumonia",
        "specialty": "respiratory",
        "level": 5,
        "difficulty": "hard",
        "name": "Anil Joshi",
        "age": 50,
        "gender": "M",
        "chief_complaint": "High fever and cough with breathlessness",
        "stages": [
            "You have had high fever and chills for a few days.",
            "You developed a cough with thick, yellowish sputum and pain in your chest when you take a deep breath.",
            "Now you feel breathless even at rest and very weak. You struggle to walk due to breathlessness.",
        ],
        "hints": [
            "Think of a serious lung infection involving air sacs of the lungs.",
            "Management often requires antibiotics and sometimes hospital admission.",
        ],
        "expected_diagnosis": "community-acquired pneumonia",
        "expected_treatment_keywords": [
            "antibiotic", "amoxicillin", "azithromycin", "ceftriaxone",
            "hospital", "oxygen"
        ],
    },

    # -------------------- GASTROENTEROLOGY (5 levels) --------------------
    {
        "id": "gi_1_dyspepsia",
        "specialty": "gastroenterology",
        "level": 1,
        "difficulty": "easy",
        "name": "Rahul Mishra",
        "age": 29,
        "gender": "M",
        "chief_complaint": "Upper abdominal discomfort after meals",
        "stages": [
            "You feel a burning or heavy sensation in the upper part of your abdomen after meals.",
            "The discomfort is worse after spicy or oily food and improves with simple antacid syrup.",
            "You do not have weight loss, vomiting, or blood in stool. It mainly feels like indigestion.",
        ],
        "hints": [
            "Think of common 'acidity' or indigestion-like problems.",
            "Simple lifestyle changes and antacids or acid-suppressing tablets often help.",
        ],
        "expected_diagnosis": "functional dyspepsia / acid peptic symptoms",
        "expected_treatment_keywords": [
            "antacid", "PPI", "omeprazole", "pantoprazole",
            "diet changes", "smaller meals"
        ],
    },
    {
        "id": "gi_2_gerd",
        "specialty": "gastroenterology",
        "level": 2,
        "difficulty": "easy",
        "name": "Neha Sharma",
        "age": 40,
        "gender": "F",
        "chief_complaint": "Burning in chest after meals",
        "stages": [
            "You feel a burning sensation in your chest after meals, especially when lying down.",
            "Sometimes food or sour liquid comes up into your mouth.",
            "Symptoms get worse after spicy or heavy meals and late-night eating.",
        ],
        "hints": [
            "Think of acid from the stomach coming up into the food pipe.",
            "Treatment usually includes PPIs and lifestyle changes like elevating the head of the bed.",
        ],
        "expected_diagnosis": "gastroesophageal reflux disease",
        "expected_treatment_keywords": [
            "PPI", "omeprazole", "pantoprazole", "rabeprazole",
            "H2 blocker", "ranitidine"
        ],
    },
    {
        "id": "gi_3_ibd",
        "specialty": "gastroenterology",
        "level": 3,
        "difficulty": "medium",
        "name": "Sonia Arora",
        "age": 26,
        "gender": "F",
        "chief_complaint": "Recurrent loose stools with pain",
        "stages": [
            "You have had recurrent episodes of loose stools for several months.",
            "Sometimes you notice mucus and small amounts of blood in the stool.",
            "You also have crampy abdominal pain, weight loss, and fatigue between flares.",
        ],
        "hints": [
            "Think of chronic inflammatory conditions of the intestine, not just simple infection.",
            "Management often includes anti-inflammatory medicines and long-term follow-up.",
        ],
        "expected_diagnosis": "inflammatory bowel disease",
        "expected_treatment_keywords": [
            "5-ASA", "mesalamine", "steroid", "immunosuppressant",
            "colon", "gastroenterologist"
        ],
    },
    {
        "id": "gi_4_acute_pancreatitis",
        "specialty": "gastroenterology",
        "level": 4,
        "difficulty": "hard",
        "name": "Deepak Tiwari",
        "age": 38,
        "gender": "M",
        "chief_complaint": "Severe upper abdominal pain",
        "stages": [
            "You suddenly developed severe pain in the upper abdomen that radiates to your back.",
            "The pain is constant, and you feel very nauseous and have vomited several times.",
            "You drink alcohol regularly on weekends or more, and this episode started after a heavy meal and drinking.",
        ],
        "hints": [
            "Think of acute inflammation of an organ behind the stomach, often related to alcohol or gallstones.",
            "Management usually requires hospital admission, IV fluids, and pain control.",
        ],
        "expected_diagnosis": "acute pancreatitis",
        "expected_treatment_keywords": [
            "hospital", "IV fluids", "pain control", "nil by mouth",
            "pancreatitis"
        ],
    },
    {
        "id": "gi_5_upper_gi_bleed",
        "specialty": "gastroenterology",
        "level": 5,
        "difficulty": "hard",
        "name": "Harish Kumar",
        "age": 52,
        "gender": "M",
        "chief_complaint": "Vomiting blood",
        "stages": [
            "You suddenly vomited a large amount of dark red or coffee-colored material.",
            "You felt dizzy and weak afterwards, and your stools have turned black.",
            "You have a history of taking painkillers regularly and sometimes drink alcohol.",
        ],
        "hints": [
            "Think of serious bleeding from the upper digestive tract.",
            "Management often requires urgent endoscopy, IV fluids, and blood transfusion.",
        ],
        "expected_diagnosis": "upper gastrointestinal bleed",
        "expected_treatment_keywords": [
            "endoscopy", "PPI infusion", "IV fluids", "blood transfusion",
            "hospital", "emergency"
        ],
    },

    # -------------------- ENDOCRINOLOGY (5 levels) --------------------
    {
        "id": "endo_1_type2_diabetes",
        "specialty": "endocrinology",
        "level": 1,
        "difficulty": "easy",
        "name": "Anil Kumar",
        "age": 50,
        "gender": "M",
        "chief_complaint": "Increased thirst and urination",
        "stages": [
            "You feel very thirsty and need to drink water frequently.",
            "You also pass urine more often than before, including at night.",
            "You feel more tired and have noticed some weight loss. A recent blood test showed high sugar levels.",
        ],
        "hints": [
            "Think of a very common endocrine condition related to blood sugar.",
            "Initial management often includes lifestyle changes and oral medicines.",
        ],
        "expected_diagnosis": "type 2 diabetes mellitus",
        "expected_treatment_keywords": [
            "metformin", "diet control", "exercise", "oral hypoglycemic",
            "blood sugar"
        ],
    },
    {
        "id": "endo_2_hypothyroidism",
        "specialty": "endocrinology",
        "level": 2,
        "difficulty": "easy",
        "name": "Pooja Rao",
        "age": 35,
        "gender": "F",
        "chief_complaint": "Weight gain and tiredness",
        "stages": [
            "You feel tired most of the time and have gained weight without major changes in diet.",
            "You feel cold more easily than others and your skin is becoming dry.",
            "Your periods have become irregular, and a recent blood test showed abnormal thyroid levels.",
        ],
        "hints": [
            "Think of an underactive gland in the neck controlling metabolism.",
            "Treatment often uses a daily hormone tablet to replace what the body is not making.",
        ],
        "expected_diagnosis": "hypothyroidism",
        "expected_treatment_keywords": [
            "thyroxine", "levothyroxine", "thyroid hormone",
            "TSH", "replacement"
        ],
    },
    {
        "id": "endo_3_hyperthyroidism",
        "specialty": "endocrinology",
        "level": 3,
        "difficulty": "medium",
        "name": "Ritu Malhotra",
        "age": 28,
        "gender": "F",
        "chief_complaint": "Weight loss and palpitations",
        "stages": [
            "You have lost weight despite eating normally or even more than usual.",
            "You feel your heart racing, get sweaty easily, and feel anxious or irritable.",
            "You sometimes notice your hands tremble and find it hard to tolerate heat. A test showed very low TSH.",
        ],
        "hints": [
            "Think of an overactive thyroid gland causing high metabolism.",
            "Treatment may involve tablets to reduce thyroid hormone levels, and sometimes other options.",
        ],
        "expected_diagnosis": "hyperthyroidism",
        "expected_treatment_keywords": [
            "carbimazole", "propylthiouracil", "beta blocker",
            "antithyroid", "thyroid"
        ],
    },
    {
        "id": "endo_4_dka",
        "specialty": "endocrinology",
        "level": 4,
        "difficulty": "hard",
        "name": "Manoj Singh",
        "age": 20,
        "gender": "M",
        "chief_complaint": "Abdominal pain and vomiting in a known diabetic",
        "stages": [
            "You have type 1 diabetes and have missed some insulin doses recently.",
            "You now have severe abdominal pain, nausea, and repeated vomiting.",
            "You feel very weak, drowsy, breathe fast, and your breath smells fruity or like nail polish remover.",
        ],
        "hints": [
            "Think of an acute, life-threatening emergency related to very high blood sugar and ketones.",
            "Management requires hospital admission, IV insulin, and careful fluid and electrolyte correction.",
        ],
        "expected_diagnosis": "diabetic ketoacidosis",
        "expected_treatment_keywords": [
            "IV insulin", "IV fluids", "ICU", "electrolytes",
            "emergency", "DKA"
        ],
    },
    {
        "id": "endo_5_adrenal_crisis",
        "specialty": "endocrinology",
        "level": 5,
        "difficulty": "hard",
        "name": "Farah Ali",
        "age": 45,
        "gender": "F",
        "chief_complaint": "Severe weakness and low blood pressure",
        "stages": [
            "You feel extremely weak, dizzy, and have lost weight over the past few months.",
            "Your blood pressure has been low, and you feel faint when standing up.",
            "Recently, after a minor illness, you became very unwell with vomiting, abdominal pain, and confusion.",
        ],
        "hints": [
            "Think of failure of a gland above the kidneys that makes cortisol.",
            "In emergencies, this is treated with IV steroids and fluids.",
        ],
        "expected_diagnosis": "adrenal crisis in adrenal insufficiency",
        "expected_treatment_keywords": [
            "IV hydrocortisone", "steroid", "IV fluids", "adrenal insufficiency",
            "emergency"
        ],
    },
]


def pick_case(
    specialty: Optional[str] = None,
    level: Optional[int] = None,
    difficulty: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Pick a case based on optional filters:
    - If specialty + level provided: return that exact level (if found).
    - Else if specialty + difficulty provided: random case within that group.
    - Else if only specialty provided: random case in that specialty.
    - Else if only difficulty provided: random case with that difficulty.
    - Else: random case from all.
    """
    cases = PATIENT_CASES

    if specialty:
        cases = [c for c in cases if c["specialty"] == specialty]

    if level is not None:
        exact = [c for c in cases if c["level"] == level]
        if exact:
            return random.choice(exact)

    if difficulty:
        filtered = [c for c in cases if c["difficulty"] == difficulty]
        if filtered:
            return random.choice(filtered)

    if not cases:
        # fallback: if filters removed everything, use all
        cases = PATIENT_CASES

    return random.choice(cases)
