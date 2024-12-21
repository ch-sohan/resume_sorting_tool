from django.shortcuts import render
import os
import re
import ast
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from pymongo import MongoClient
from PyPDF2 import PdfReader
from docx import Document
import spacy
import google.generativeai as genai
from django.conf import settings
from collections import Counter
import datetime
from django.shortcuts import render,HttpResponse,redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
import json
from bson import ObjectId



@csrf_exempt
def update_resume(request, resume_id):
    if request.method == 'POST':
        try:
            # Parse the data from the request
            data = json.loads(request.body)
            print(data)
            updated_name = data.get('name')
            updated_skills = data.get('skills')
            updated_education = data.get('education')
            updated_work_experience = data.get('workExperience')
            print(resume_id)
            

            # Find the resume by ID (or another unique field like filename)
            resume = collection.find_one({"id": resume_id})

            if resume:
                # Update the fields
                collection.update_one(
                    {"id": resume_id},
                    {
                        "$set": {
                            "personal_details.name": updated_name,
                            "skills": updated_skills.split(','),
                            "education": updated_education,
                            "work_experience": updated_work_experience.split(',')
                        }
                    }
                )

                return JsonResponse({'success': True})

            else:
                return JsonResponse({'success': False, 'error': 'Resume not found'})

        except Exception as e:
            print(str(e)+"****")
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid method'})


# Create your views here.
@login_required(login_url='login')
def HomePage(request):
    resumes = list(collection.find())
    filtered_resumes = [resume for resume in resumes if resume.get('username') == request.user.username]
    context = {
        'resumes': filtered_resumes,
        'username':request.user.username,
    }
    #print("Resumes fetched from database:", resumes)
    return render (request,'main/home.html',context)

def SignupPage(request):
    if request.method=='POST':
        uname=request.POST.get('username')
        email=request.POST.get('email')
        pass1=request.POST.get('password1')
        pass2=request.POST.get('password2')

        if pass1!=pass2:
            return HttpResponse("Your password and confrom password are not Same!!")
        else:
            if User.objects.filter(username=uname).exists():
                return HttpResponse("User already exists!")
            my_user=User.objects.create_user(uname,email,pass1)
            my_user.save()
            return redirect('login')

    return render (request,'main/signup.html')

def LoginPage(request):
    if request.method=='POST':
        username=request.POST.get('username')
        pass1=request.POST.get('pass')
        user=authenticate(request,username=username,password=pass1)
        if user is not None:
            login(request,user)
            return redirect('home')
        else:
            return HttpResponse ("Username or Password is incorrect!!!")

    return render (request,'main/login.html')

def LogoutPage(request):
    logout(request)
    return redirect('login')

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
        job_role = request.POST.get('jobRole')
        file = request.FILES.get('resume')
        employment_type = request.POST.get('employmentType')
        save_path = os.path.join('uploads', job_role+"_"+request.user.username+"_"+file.name)
        file.name = job_role+"_"+request.user.username+"_"+file.name
        with open(save_path, 'wb') as f:
            for chunk in file.chunks():
                f.write(chunk)

        try:
            # Parse and extract information
            resume_text = parse_resume(save_path)
            extracted_data = extract_info(resume_text)
            structured_data = call_gemini_api(resume_text)
            resume_id = str(ObjectId())  # Generate a new ObjectId for this resume
            structured_data['id'] = resume_id 
            structured_data['jobRole'] = job_role
            structured_data['employmentType'] =  employment_type
            structured_data['filename'] = file.name
            structured_data['username'] = request.user.username

            # Save to MongoDB
            collection.insert_one(structured_data)
            return redirect('home') 

        except Exception as e:
            return JsonResponse({'message': 'Resume processing failed.', 'error': str(e)})


def call_gemini_api(resume_text):

    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

    # Define the prompt to send to the Gemini model for categorizing the resume
    prompt = f"""
    Extract and categorize the following resume information into the following fields:
    - Personal details (Name, Email, Contact Number, Address)
    - Skills
    - Education
    - Work Experience
    - Certifications
    - Number of Years of Experience

    (Note:  Please give me response in plain text and list all the skills seperated by commas No sub categories are needed in Skills and for the number of years of experience only give the number of years don't give any other content on your own)
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

# Resume Upload Page
def upload_resume(request):
    return render(request, 'main/upload.html')

# Admin Dashboard
def admin_dashboard(request):
    # Check if the logged-in user is a superuser and their username is "sohan"
    if not request.user.is_superuser or request.user.username != 'sohan':
        return redirect('home')  # Redirect to home page if not superuser or not 'sohan'

    resumes = list(collection.find())
    total_resumes = len(resumes)

    # Calculate the most common skill (Skill Count)
    skill_counts = Counter()
    for resume in resumes:
        skills = resume.get('skills', [])
        for skill in skills:
            skill_counts[skill] += 1

    # Calculate most common skill
    most_common_skill = skill_counts.most_common(1)
    most_common_skill = most_common_skill[0][0] if most_common_skill else "N/A"

    # Calculate average experience (based on work experience length in years)
    total_experience = 0
    for resume in resumes:
        years_of_experience = resume.get('years_of_experience', '')
        #total_experience += int(years_of_experience)  # Assuming each experience is 1 year

    avg_experience = total_experience / total_resumes if total_resumes else 0

    # Pass data to the template
    context = {
        'total_resumes': total_resumes,
        'most_common_skill': most_common_skill,
        'avg_experience': avg_experience,
        'resumes': resumes,
        'skill_counts': skill_counts,
    }

    return render(request, 'main/admin_dashboard.html', context)


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
        'years_of_experience': '',
        'uploaded_date': '',
    }

    current_date = datetime.datetime.now().strftime('%Y-%m-%d')  # Example: '2024-12-12'
    data['uploaded_date'] = current_date

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
            # Split the skills by comma and store them as a list
            skills_str = line.replace("Skills:", "").strip()
            skills = [skill.strip() for skill in skills_str.split(",")]  # Split and strip each skill
            data['skills'].extend(skills)  # Add skills to the list
        elif line.startswith("Education:"):
            current_section = "education"
        elif line.startswith("Work Experience:"):
            current_section = "work_experience"
        elif line.startswith("Certifications:"):
            current_section = "certifications"
        elif line.startswith("Number of Years of Experience:"):
            current_section = "years_of_experience"
            data['years_of_experience'] = line.replace("Number of Years of Experience:", "").strip()
        
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
        
        # Parse Education
        elif current_section == "education":
            data['education'] = line.replace("Bachelor of Science in Computer Science:", "").strip()

        # Parse Work Experience
        elif current_section == "work_experience":
            data['work_experience'].append(line.strip())  # Store each line as an individual item in the list
        
        
        # Parse Certifications
        elif current_section == "certifications":
            data['certifications'].append(line.strip())
    
    return data

def apply_filters(request):
    if request.method == 'POST':
        # Get filter values from the request
        filters = json.loads(request.body)
        print("Hellooooooooooo")
        try:
            # Fetch all resumes from the database
            query = {}

            # Add filters to the query only if they have valid values
            if filters['role'] != "--":
                query["jobRole"] = filters['role']
            
            if filters['employment'] != "--":
                query["employmentType"] = filters['employment']

            # Fetch resumes from the database with the dynamic query
            all_resumes = list(collection.find(query))
            

            # Convert resumes to a format suitable for the Gemini model
            resumes_data = []
            for resume in all_resumes:
                resume_data = {
                    'name': resume.get('personal_details', {}).get('name', ''),
                    'email': resume.get('personal_details', {}).get('email', ''),
                    'phone': resume.get('personal_details', {}).get('phone', ''),
                    'address': resume.get('personal_details', {}).get('address', ''),
                    'skills': ', '.join(resume.get('skills', [])),
                    'jobRole': resume.get('jobRole', ''),
                    'education': resume.get('education', ''),
                    'work_experience': ', '.join(resume.get('work_experience', [])),
                    'certifications': ', '.join(resume.get('certifications', [])),
                    'years_of_experience': resume.get('years_of_experience', ''),
                    'id':resume.get('id',''),
                    'employmentType': resume.get('employmentType', ''),
                    'uploaded_date': resume.get('uploaded_date',''),
                    'username': resume.get('username',''),


                }
                resumes_data.append(resume_data)

            # Prepare the prompt for Gemini API
            prompt = generate_prompt(filters, resumes_data)
            print(prompt)
            # Call the Gemini API to get the filtered resume IDs
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)

            # Parse the response (assuming the response contains the structured data)
            response_text = response.text.strip()
            print(response_text)

            # Assuming response contains a list of resume IDs
            resume_ids = parse_response_for_ids(response)
            print(resume_ids)

            # Send the filtered resume IDs back to the frontend
            return JsonResponse({'success': True, 'resumeIds': resume_ids})

        except Exception as e:
            print(f"Error in filtering process: {e}")
            return JsonResponse({'success': False, 'message': 'Error processing filters'})

def generate_prompt(filters, resumes_data):
    # Convert resumes_data to string format for the prompt
    resumes_str = "\n".join([f"Resume: {resume}" for resume in resumes_data])

    # Generate a prompt based on the filters and resumes
    return f"""
    Given the following filters:
    - Job Role: {filters['role']}
    - Experience Level: {filters['experience']}
    - Skills: {filters['skills']}
    - Education: {filters['education']}
    - Industry: {filters['industry']}
    - Employment Type: {filters['employment']}
    - Job Description: {filters['jobDescription']}

    And the following resumes:
    {resumes_str}

    Provide me with a list of resume IDs that satisfy all the these filters.
    I don't want you to give me resumeids which partially satisfy the filters
    (Note: Strictly give me list of resume Ids in the following format I don't want anything else and perform filtering strictly based on labels)
    Entry level means having 0-3 years of experience, Mid Level means 3-8 years of experience and Senior level means >8 years of experience
    ['id1','id2','id3',....'idn']
    """

def parse_response_for_ids(response):
    return ast.literal_eval(response.text.strip()) 

def apply_category_filters(request):
    if request.method == 'POST':
        # Get filter values from the request
        filters = json.loads(request.body)
        print("Heyyyy")
        try:
            # Fetch all resumes from the database
            query = {}

            
            # Fetch resumes from the database with the dynamic query
            all_resumes = list(collection.find(query))
            

            # Convert resumes to a format suitable for the Gemini model
            resumes_data = []
            for resume in all_resumes:
                resume_data = {
                    'name': resume.get('personal_details', {}).get('name', ''),
                    'email': resume.get('personal_details', {}).get('email', ''),
                    'phone': resume.get('personal_details', {}).get('phone', ''),
                    'address': resume.get('personal_details', {}).get('address', ''),
                    'skills': ', '.join(resume.get('skills', [])),
                    'jobRole': resume.get('jobRole', ''),
                    'education': resume.get('education', ''),
                    'work_experience': ', '.join(resume.get('work_experience', [])),
                    'certifications': ', '.join(resume.get('certifications', [])),
                    'years_of_experience': resume.get('years_of_experience', ''),
                    'id':resume.get('id',''),
                    'employmentType': resume.get('employmentType', ''),
                    'uploaded_date': resume.get('uploaded_date',''),
                    'username': resume.get('username',''),

                }
                resumes_data.append(resume_data)

            # Prepare the prompt for Gemini API
            prompt = generate_category_prompt(filters, resumes_data)
            print(prompt)
            # Call the Gemini API to get the filtered resume IDs
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)

            # Parse the response (assuming the response contains the structured data)
            response_text = response.text.strip()
            print(response_text)

            # Assuming response contains a list of resume IDs
            resume_ids = parse_response_for_ids(response)
            print(resume_ids)

            # Send the filtered resume IDs back to the frontend
            return JsonResponse({'success': True, 'resumeIds': resume_ids})

        except Exception as e:
            print(f"Error in filtering process: {e}")
            return JsonResponse({'success': False, 'message': 'Error processing filters'})
        
def generate_category_prompt(filters,resumes_data):
    resumes_str = "\n".join([f"Resume: {resume}" for resume in resumes_data])

    # Generate a prompt based on the filters and resumes
    return f"""
    {resumes_str}
    From the above resumes which resumes belong to {filters['category']} category?

    Provide me only th list of resumeIDs that satisfy the above mentioned category
    (Note: Strictly give me list of resume Ids in the following format I don't want anything else and perform filtering strictly based on labels)
    Entry level means having 0-3 years of experience, Mid Level means 3-8 years of experience and Senior level means >8 years of experience
    ['id1','id2','id3',....'idn']
    """




