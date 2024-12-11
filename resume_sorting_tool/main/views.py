from django.shortcuts import render
import os
import re
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from pymongo import MongoClient
from PyPDF2 import PdfReader
from docx import Document
import spacy
import google.generativeai as genai
import os


#Mongodb connection
uri = "mongodb+srv://chsohan:X98eXVYMo7hAb2Fy@cluster0.kpff4.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(uri)
db = client["resume_database"]
collection = db["resumes"]


# Load SpaCy NLP Model
nlp = spacy.load("en_core_web_sm")

# Resume Parsing Functions
def parse_resume(file_path):
    file_extension = os.path.splitext(file_path)[1].lower()
    if file_extension == ".pdf":
        return extract_text_from_pdf(file_path)
    elif file_extension == ".docx":
        return extract_text_from_docx(file_path)
    elif file_extension == ".txt":
        return extract_text_from_txt(file_path)
    else:
        raise ValueError("Unsupported file format")

def extract_text_from_pdf(file_path):
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def extract_text_from_docx(file_path):
    doc = Document(file_path)
    return "\n".join([p.text for p in doc.paragraphs])

def extract_text_from_txt(file_path):
    with open(file_path, "r") as file:
        return file.read()

# Information Extraction Function
def extract_info(resume_text):
    doc = nlp(resume_text)
    data = {}

    # Extract Name
    data["name"] = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]

    # Extract Email
    data["email"] = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", resume_text)

    # Extract Phone Number
    data["phone"] = re.findall(r"\b\d{10}\b|\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b", resume_text)

    # Extract Skills (based on keywords)
    skills_keywords = ["Python", "Django", "Machine Learning", "Data Science", "Java", "SQL"]
    data["skills"] = [skill for skill in skills_keywords if skill.lower() in resume_text.lower()]

    return data

# Process Resume View
@csrf_exempt
def process_resume(request):
    if request.method == 'POST':
        file = request.FILES['resume']
        save_path = os.path.join('uploads', file.name)
        with open(save_path, 'wb') as f:
            for chunk in file.chunks():
                f.write(chunk)

        try:
            # Parse and extract information
            resume_text = parse_resume(save_path)
            extracted_data = extract_info(resume_text)
            structured_data = call_gemini_api(resume_text)

            # Save to MongoDB
            collection.insert_one(structured_data)
            return JsonResponse({'message': 'Resume processed successfully!', 'data': structured_data})

        except Exception as e:
            return JsonResponse({'message': 'Resume processing failed.', 'error': str(e)})


def call_gemini_api(resume_text):

    genai.configure(api_key="AIzaSyDlbljcxkhd1ZSFyF10ceVHnEiBcrL19t0")

    # Define the prompt to send to the Gemini model for categorizing the resume
    prompt = f"""
    Extract and categorize the following resume information into the following fields:
    - Personal details (Name, Email, Contact Number, Address)
    - Skills
    - Education
    - Work Experience
    - Certifications
    (Note:  Please give me response in plain text)
    Resume Text:
    {resume_text}

    """

    # Create the GenerativeModel object for the Gemini model
    model = genai.GenerativeModel("gemini-1.5-flash")

    # Make a call to generate content using the model
    response = model.generate_content(prompt)

    # Parse the response (assuming the response contains the structured data)
    response_text = response.text.strip()
    print("Raw response_text from Gemini API:")
    print(response_text)
    # Now, we can parse the response_text and convert it into a dictionary format
    # Assuming the model returns a structured response with fields
    structured_data = updated_parse_response(response_text)

    return structured_data


def parse_response(response_text):
    # Function to parse and structure the response from the LLM
    data = {
        'personal_details': {
            'name': '',
            'email': '',
            'phone': '',
            'address': ''
        },
        'skills': [],
        'education': '',
        'work_experience': [],
        'certifications': [],
    }

    # Split the response into lines or use regular expressions to categorize the data
    lines = response_text.split("\n")
    
    # Example parsing logic
    for line in lines:
        if "Name:" in line:
            data['personal_details']['name'] = line.replace("Name:", "").strip()
        elif "Email:" in line:
            data['personal_details']['email'] = line.replace("Email:", "").strip()
        elif "Phone:" in line:
            data['personal_details']['phone'] = line.replace("Phone:", "").strip()
        elif "Address:" in line:
            data['personal_details']['address'] = line.replace("Address:", "").strip()
        elif "Skills:" in line:
            skills = line.replace("Skills:", "").strip()
            data['skills'] = [skill.strip() for skill in skills.split(',')] if skills else []
        elif "Education:" in line:
            data['education'] = line.replace("Education:", "").strip()
        elif "Work Experience:" in line:
            work_exp = line.replace("Work Experience:", "").strip()
            if work_exp:
                data['work_experience'].append(work_exp)
        elif "Certifications:" in line:
            certs = line.replace("Certifications:", "").strip()
            data['certifications'] = [cert.strip() for cert in certs.split(',')] if certs else []

    return data

# Resume Upload Page
def upload_resume(request):
    return render(request, 'main/upload.html')

# Admin Dashboard
def admin_dashboard(request):
    resumes = collection.find()
    return render(request, 'main/admin_dashboard.html', {'resumes': resumes})



def updated_parse_response(response_text):
    # Initialize a dictionary to store the parsed data
    data = {
        'personal_details': {
            'name': '',
            'email': '',
            'phone': '',
            'address': ''
        },
        'skills': [],
        'education': '',
        'work_experience': [],
        'certifications': [],
    }

    # Split the response into lines and iterate over them
    lines = response_text.split("\n")
    
    # Variables to keep track of the current section
    current_section = None
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue

        # Identify and process each section based on the response format
        if line.startswith("Personal details:"):
            current_section = "personal_details"
        elif line.startswith("Skills:"):
            current_section = "skills"
        elif line.startswith("Education:"):
            current_section = "education"
        elif line.startswith("Work Experience:"):
            current_section = "work_experience"
        elif line.startswith("Certifications:"):
            current_section = "certifications"
        
        # Parse Personal Details
        elif current_section == "personal_details":
            if line.startswith("Name:"):
                data['personal_details']['name'] = line.replace("Name:", "").strip()
            elif line.startswith("Email:"):
                data['personal_details']['email'] = line.replace("Email:", "").strip()
            elif line.startswith("Contact Number:"):
                data['personal_details']['phone'] = line.replace("Contact Number:", "").strip()
            elif line.startswith("Address:"):
                data['personal_details']['address'] = line.replace("Address:", "").strip()
        
        # Parse Skills
        elif current_section == "skills":
            if line.startswith("Programming Languages:"):
                data['skills'].append("Programming Languages: " + line.replace("Programming Languages:", "").strip())
            elif line.startswith("Web Development:"):
                data['skills'].append("Web Development: " + line.replace("Web Development:", "").strip())
            elif line.startswith("Database Management:"):
                data['skills'].append("Database Management: " + line.replace("Database Management:", "").strip())
            elif line.startswith("Tools:"):
                data['skills'].append("Tools: " + line.replace("Tools:", "").strip())
            elif line.startswith("Cloud Platforms:"):
                data['skills'].append("Cloud Platforms: " + line.replace("Cloud Platforms:", "").strip())
        
        # Parse Education
        elif current_section == "education":
            data['education'] = line.replace("Bachelor of Science in Computer Science:", "").strip()

        # Parse Work Experience
        elif current_section == "work_experience":
            if line.startswith("Software Engineer"):
                data['work_experience'].append(line.strip())
            elif line.startswith("Intern - Software Developer"):
                data['work_experience'].append(line.strip())
        
        # Parse Certifications
        elif current_section == "certifications":
            data['certifications'].append(line.strip())
    
    return data
