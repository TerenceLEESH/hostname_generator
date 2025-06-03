from django import forms
from .models import Hostname

class HostnameQuestionnaireForm(forms.Form):
    # Question 1
    is_production = forms.BooleanField(
        label="Is this for a production environment?",
        required=False,
        widget=forms.RadioSelect(choices=[(True, 'Yes'), (False, 'No')])
    )
    
    # Question 2 (shown only if Question 1 is No)
    environment_type = forms.ChoiceField(
        label="What type of environment is this?",
        choices=[('dev', 'Development'), ('test', 'Testing'), ('staging', 'Staging')],
        required=False
    )
    
    # Question 3 (shown only if Question 1 is No)
    is_temporary = forms.BooleanField(
        label="Is this a temporary environment?",
        required=False,
        widget=forms.RadioSelect(choices=[(True, 'Yes'), (False, 'No')])
    )
    
    # Questions 4-6 (always shown)
    application_name = forms.CharField(
        label="What is the application name?",
        max_length=100
    )
    
    region = forms.ChoiceField(
        label="Select region",
        choices=[('us', 'United States'), ('eu', 'Europe'), ('asia', 'Asia')]
    )
    
    instance_number = forms.IntegerField(
        label="Instance number",
        min_value=1,
        max_value=999
    )
    
    def clean(self):
        cleaned_data = super().clean()
        is_production = cleaned_data.get('is_production')
        
        # If production is Yes, ensure environment_type and is_temporary aren't required
        if is_production:
            cleaned_data['environment_type'] = None
            cleaned_data['is_temporary'] = None
        else:
            # If production is No, ensure environment_type and is_temporary are provided
            if not cleaned_data.get('environment_type'):
                self.add_error('environment_type', 'This field is required for non-production environments')
            
            if cleaned_data.get('is_temporary') is None:
                self.add_error('is_temporary', 'This field is required for non-production environments')
        
        return cleaned_data
    
    def generate_hostname(self):
        """Generate hostname based on form answers"""
        data = self.cleaned_data
        
        # Start with empty prefix
        prefix = ""
        
        # Add environment type
        if data['is_production']:
            prefix += "prod-"
        else:
            prefix += f"{data['environment_type']}-"
            if data['is_temporary']:
                prefix += "temp-"
        
        # Add application name (abbreviated)
        app_abbr = ''.join(word[0] for word in data['application_name'].split())
        
        # Add region
        region = data['region']
        
        # Add instance number with padding
        instance = str(data['instance_number']).zfill(3)
        
        # Combine all parts
        hostname = f"{prefix}{app_abbr}-{region}-{instance}"
        
        return hostname