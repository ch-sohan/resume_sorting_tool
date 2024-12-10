from django.shortcuts import render

import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .utils import call_gemini_api  # Import the Gemini API utility
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["resume_database"]
collection = db["resumes"]



@csrf_exempt
def process_resume(request):
    if request.method == 'POST':
        file = request.FILES['resume']
        save_path = os.path.join('uploads', file.name)
        with open(save_path, 'wb') as f:
            for chunk in file.chunks():
                f.write(chunk)

        extracted_data = call_gemini_api(save_path)
        if "error" not in extracted_data:
            # Save to MongoDB
            collection.insert_one(extracted_data)
            return JsonResponse({'message': 'Resume processed successfully!', 'data': extracted_data})
        else:
            return JsonResponse({'message': 'Resume processing failed.', 'error': extracted_data['error']})


def upload_resume(request):
    return render(request, 'main/upload.html')

def admin_dashboard(request):
    resumes = collection.find()
    return render(request, 'main/admin_dashboard.html', {'resumes': resumes})

