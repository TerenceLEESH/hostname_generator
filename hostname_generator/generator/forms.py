from django import forms
import csv
import os
from django.conf import settings

def get_datacenter_choices():
    """Load datacenter choices from the CSV file"""
    datacenters = []
    csv_path = os.path.join(settings.DATA_DIR, 'datacenters.csv')
    
    # Check if CSV file exists, if not, create with header and sample data
    if not os.path.exists(csv_path):
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['DC', 'site_code'])
            writer.writerow(['Datacenter 1', 'dc1'])
            writer.writerow(['Datacenter 2', 'dc2'])
            writer.writerow(['Datacenter 3', 'dc3'])
    
    # Read datacenters from CSV
    try:
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                datacenters.append((row['site_code'], row['DC']))
    except Exception as e:
        # Default values if file read fails
        datacenters = [('dc1', 'Datacenter 1'), ('dc2', 'Datacenter 2'), ('dc3', 'Datacenter 3')]
    
    return datacenters

class InitialForm(forms.Form):
    hostname_count = forms.IntegerField(
        min_value=1, 
        max_value=50, 
        initial=1,
        label="How many ESXi hostnames do you need to generate?",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

class EsxiHostnameForm(forms.Form):
    # Step 1
    is_dmz = forms.ChoiceField(
        choices=[('', 'Select...'), ('yes', 'Yes'), ('no', 'No')],
        label="Is the host in DMZ?",
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Step 2
    datacenter = forms.ChoiceField(
        choices=[],  # Will be populated from CSV in __init__
        label="Which datacenter does the host belong to?",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control', 'disabled': 'disabled'})
    )
    
    # Step 3 (only if not DMZ)
    hardware_type = forms.ChoiceField(
        choices=[('', 'Select...'), ('dell', 'Dell'), ('hp', 'HP')],
        label="Which hardware type is it?",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control', 'disabled': 'disabled'})
    )
    
    # Step 4 (only if not DMZ)
    zone_type = forms.ChoiceField(
        choices=[
            ('', 'Select...'), 
            ('zone_a', 'Zone A - Custom Input'), 
            ('zone_b', 'Zone B - Custom Input'), 
            ('zone_c', 'Zone C - Automatic "ppp"')
        ],
        label="Which zone is it?",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control', 'disabled': 'disabled'})
    )
    
    # Custom input for Zone A or B
    custom_zone = forms.CharField(
        max_length=10,
        label="Enter custom zone value:",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'disabled': 'disabled'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate datacenter choices from CSV
        self.fields['datacenter'].choices = [('', 'Select...')] + get_datacenter_choices()