# SYNTHETIC_NAME_LIST_V1 — DO NOT USE REAL PERSONAL DATA (DPDP Act 2023 compliance)
# All names generated from combinations of common Indian given names and explicitly synthetic surname tokens.
# Phone numbers strictly use synthetic range 999990xxxx (never real subscriber numbers).

from __future__ import annotations

SYNTHETIC_HEADER = "SYNTHETIC_NAME_LIST_V1 — DO NOT USE REAL PERSONAL DATA"

FEMALE_FIRST_NAMES: list[tuple[str, str]] = [
    ("Ananya", "अनन्या"),
    ("Aadhya", "आध्या"),
    ("Diya", "दिया"),
    ("Pari", "परी"),
    ("Saanvi", "सान्वी"),
    ("Kavya", "काव्या"),
    ("Nisha", "निशा"),
    ("Riya", "रिया"),
    ("Pooja", "पूजा"),
    ("Neha", "नेहा"),
    ("Sneha", "स्नेहा"),
    ("Kriti", "कृति"),
    ("Shreya", "श्रेया"),
    ("Tanvi", "तन्वी"),
    ("Meera", "मीरा"),
    ("Ishita", "इशिता"),
    ("Divya", "दिव्या"),
    ("Swati", "स्वाति"),
    ("Prachi", "प्राची"),
    ("Aditi", "अदिति"),
    ("Bhavna", "भावना"),
    ("Garima", "गरिमा"),
    ("Jyoti", "ज्योति"),
    ("Komal", "कोमल"),
    ("Mansi", "मानसी"),
    ("Pallavi", "पल्लवी"),
    ("Radhika", "राधिका"),
    ("Sakshi", "साक्षी"),
    ("Trisha", "त्रिशा"),
    ("Vaishnavi", "वैष्णवी"),
]

MALE_FIRST_NAMES: list[tuple[str, str]] = [
    ("Aarav", "आरव"),
    ("Rohan", "रोहन"),
    ("Vivaan", "विवान"),
    ("Aditya", "आदित्य"),
    ("Vihaan", "विहान"),
    ("Arjun", "अर्जुन"),
    ("Reyansh", "रेयांश"),
    ("Ayaan", "अयान"),
    ("Krishna", "कृष्णा"),
    ("Ishaan", "ईशान"),
    ("Shaurya", "शौर्य"),
    ("Atharv", "अथर्व"),
    ("Pranav", "प्रणव"),
    ("Kabir", "कबीर"),
    ("Dhruv", "ध्रुव"),
    ("Harsh", "हर्ष"),
    ("Mayank", "मयंक"),
    ("Nikhil", "निखिल"),
    ("Rahul", "राहुल"),
    ("Saurabh", "सौरभ"),
    ("Gaurav", "गौरव"),
    ("Kunal", "कुणाल"),
    ("Manish", "मनीष"),
    ("Piyush", "पीयूष"),
    ("Rajat", "रजत"),
    ("Siddharth", "सिद्धार्थ"),
    ("Tushar", "तुषार"),
    ("Utkarsh", "उत्कर्ष"),
    ("Varun", "वरुण"),
    ("Yash", "यश"),
]

GUARDIAN_FIRST_NAMES: list[tuple[str, str, str]] = [
    ("Rajesh", "राजेश", "father"),
    ("Suresh", "सुरेश", "father"),
    ("Ramesh", "रमेश", "father"),
    ("Mahesh", "महेश", "father"),
    ("Dinesh", "दिनेश", "father"),
    ("Mukesh", "मुकेश", "father"),
    ("Anil", "अनिल", "father"),
    ("Sunil", "सुनील", "father"),
    ("Manoj", "मनोज", "father"),
    ("Vinod", "विनोद", "father"),
    ("Sunita", "सुनीता", "mother"),
    ("Anita", "अनीता", "mother"),
    ("Geeta", "गीता", "mother"),
    ("Seema", "सीमा", "mother"),
    ("Rekha", "रेखा", "mother"),
    ("Kiran", "किरण", "mother"),
    ("Savita", "सविता", "mother"),
    ("Mamta", "ममता", "mother"),
    ("Usha", "ऊषा", "legal_guardian"),
    ("Prakash", "प्रकाश", "legal_guardian"),
]

SYNTHETIC_SURNAMES: list[tuple[str, str]] = [
    ("Test", "टेस्ट"),
    ("Sample", "सैंपल"),
    ("Demo", "डेमो"),
    ("Synth", "सिंथ"),
    ("Mock", "मॉक"),
    ("Model", "मॉडल"),
    ("Learner", "लर्नर"),
    ("Scholar", "स्कॉलर"),
    ("Example", "एग्जांपल"),
    ("Trial", "ट्रायल"),
]


def make_synthetic_phone(index: int) -> str:
    """Return a 10-digit synthetic phone in the range '999990xxxx'."""
    suffix = index % 10000
    return f"999990{suffix:04d}"
