from django.http import Http404
from django.shortcuts import render
from .content import CATEGORIES, filter_tours, load_tours, present, viewer_data

def home(request):
    tours = load_tours()
    return render(request, "tours/home.html", {"places": [present(t) for t in tours if t["status"] == "upcoming"], "demo": next(present(t) for t in tours if t["status"] == "demo")})

def explore(request):
    query = request.GET.get("q", "").strip()[:200]
    category = request.GET.get("categoria", "")
    if category not in CATEGORIES:
        category = ""
    results = [present(t) for t in filter_tours(load_tours(), query, category)]
    return render(request, "tours/explore.html", {"tours": results, "query": query, "category": category, "categories": CATEGORIES.items(), "result_count": len(results)})

def viewer(request, slug):
    tour = next((t for t in load_tours() if t["slug"] == slug and t["status"] != "upcoming"), None)
    if tour is None:
        raise Http404("Este recorrido todavía no está disponible.")
    return render(request, "tours/viewer.html", {"tour": present(tour), "tour_data": viewer_data(tour)})

def not_found(request, exception):
    return render(request, "404.html", status=404)
