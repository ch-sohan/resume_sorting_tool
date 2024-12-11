import requests
import google.generativeai as genai
import os

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

    Resume Text:
    {resume_text}
    """

    # Create the GenerativeModel object for the Gemini model
    model = genai.GenerativeModel("gemini-1.5-flash")

    # Make a call to generate content using the model
    response = model.generate_content(prompt)

    # Parse the response (assuming the response contains the structured data)
    response_text = response.text.strip()

    # Now, we can parse the response_text and convert it into a dictionary format
    # Assuming the model returns a structured response with fields
    structured_data = parse_response(response_text)

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