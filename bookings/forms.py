from django import forms
from .models import Reservation


class ReservationForm(forms.ModelForm):
    datetime = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        input_formats=['%Y-%m-%dT%H:%M'],
    )

    class Meta:
        model   = Reservation
        fields  = ['client_name', 'service', 'datetime', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Special requests, allergies, preferences...'
            }),
        }