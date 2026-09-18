from django.http import Http404
from django.shortcuts import render
from .content import filter_tours, public_tours, present, viewer_data

def home(request):
    tours = public_tours(request)
    return render(request, "tours/home.html", {"places": [present(t) for t in tours if t.featured and t.status != "demo"][:3]})

def explore(request):
    query = request.GET.get("q", "").strip()[:200]
    category = request.GET.get("categoria", "")
    tours = public_tours(request)
    categories = {t.category.slug: t.category.name for t in sorted(tours, key=lambda t: t.category_id)}
    if category not in categories:
        category = ""
    results = [present(t) for t in filter_tours(tours, query, category)]
    return render(request, "tours/explore.html", {"tours": results, "query": query, "category": category, "categories": categories.items(), "result_count": len(results)})

def viewer(request, slug):
    tour = next((t for t in public_tours(request) if t.slug == slug and t.published), None)
    if tour is None:
        raise Http404("Este recorrido todavía no está disponible.")
    data = viewer_data(tour)
    return render(request, "tours/viewer.html", {"tour": {**present(tour), "scenes": data["scenes"]}, "tour_data": data})

def not_found(request, exception):
    return render(request, "404.html", status=404)
