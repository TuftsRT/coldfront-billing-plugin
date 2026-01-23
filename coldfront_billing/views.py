from django.http import HttpResponse


def index(request):
    return HttpResponse('<h1>Hello from ColdFront Billing Plugin!</h1>')


def b_link(request):
    return HttpResponse('<h1>This is the B-Link Page</h1>')
