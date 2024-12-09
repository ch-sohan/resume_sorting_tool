from django.shortcuts import render

def upload_resume(request):
    return render(request, 'main/upload.html')
