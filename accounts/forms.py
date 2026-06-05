from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import MasterProfile


class RegisterForm(UserCreationForm):
    email     = forms.EmailField(required=True)
    specialty = forms.ChoiceField(choices=MasterProfile.SPECIALTY_CHOICES)
    bio       = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False
    )
    instagram = forms.CharField(max_length=100, required=False)

    class Meta:
        model  = User
        fields = ['username', 'email', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            MasterProfile.objects.create(
                user      = user,
                specialty = self.cleaned_data['specialty'],
                bio       = self.cleaned_data.get('bio', ''),
                instagram = self.cleaned_data.get('instagram', ''),
            )
        return user