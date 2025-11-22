from django.shortcuts import render
from django.db import models
from django.core.paginator import Paginator
from .models import Book


def list_books(request):
    q = request.GET.get('q', '').strip()
    qs = Book.objects.all().order_by('-created_at')
    if q:
        qs = qs.filter(models.Q(title__icontains=q) | models.Q(author__icontains=q) | models.Q(isbn__icontains=q) | models.Q(category__icontains=q))
    paginator = Paginator(qs, 12)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    return render(request, 'library/list.html', { 'page_obj': page_obj, 'q': q })
