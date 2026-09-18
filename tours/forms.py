from django import forms
from .models import Tour, Scene, NavigationPoint

class TourForm(forms.ModelForm):
    class Meta:
        model = Tour
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "initial_scene" in self.fields:
            self.fields["initial_scene"].queryset = Scene.objects.filter(tour=self.instance).select_related("tour") if self.instance.pk else Scene.objects.none()

class NavigationPointForm(forms.ModelForm):
    class Meta:
        model = NavigationPoint
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        origin_id = self.data.get(self.add_prefix("origin")) if self.is_bound else self.initial.get("origin", self.instance.origin_id)
        try:
            origin = Scene.objects.filter(pk=origin_id).first() if origin_id else None
        except (ValueError, TypeError):
            origin = None
        if origin and "destination" in self.fields:
            self.fields["destination"].queryset = Scene.objects.filter(tour_id=origin.tour_id).exclude(pk=origin.pk).select_related("tour")
